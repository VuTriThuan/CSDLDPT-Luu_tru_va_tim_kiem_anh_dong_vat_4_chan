"""Explicit macOS GUI integration check; not part of headless unittest discovery.

Uses existing source read-only, writes only outputs/search. Opens a real Tk
window, exercises callbacks, and writes a JSON check report. No quality scores.
"""
import json
from pathlib import Path
import sys
import time
import tkinter as tk
from unittest import mock

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np

from tools.features.b400 import validate_arrays
from tools.project_paths import PROJECT_ROOT
from tools.search.gui import SearchApp, fit
from tools.search.query import load_image, write_json


def main():
    cv2.setNumThreads(1)
    root = tk.Tk()
    app = SearchApp(root)
    checks, errors = {}, []
    out = PROJECT_ROOT/'outputs/search/verification'
    out.mkdir(parents=True, exist_ok=True)

    def settle():
        deadline = time.monotonic()+90
        while app.busy():
            root.update()
            if time.monotonic() > deadline: raise TimeoutError('GUI worker timeout')
            time.sleep(.02)
        root.update()
        if errors: raise AssertionError(errors)

    try:
        with mock.patch('tools.search.gui.messagebox.showerror', side_effect=lambda *a, **kw: errors.append(a)):
            settle()
            assert app.index is not None
            checks['real_tk_window_and_sqlite_worker'] = True
            image = PROJECT_ROOT/'data/cropped_images_576x384/Equus_asinus_0587.jpg'
            mask = PROJECT_ROOT/'outputs/segmentation/grabcut/masks/Equus_asinus_0587.jpg.png'
            with mock.patch('tools.search.gui.filedialog.askopenfilename', return_value=str(image)):
                app.choose_image()
            settle()
            assert app.query.rgb.shape == (384, 576, 3)
            np.testing.assert_array_equal(app.mask, cv2.imread(str(mask), cv2.IMREAD_GRAYSCALE))
            assert app.mask_info['method'] == 'stored_mask_for_identical_source_sha256'
            checks['choose_image_automatically_uses_exact_database_mask'] = True
            def event(x, y, name):
                h, w = app.query.rgb.shape[:2]
                rw, rh, ox, oy = fit(app.canvas.winfo_width(), app.canvas.winfo_height(), w, h)
                app.canvas.event_generate(name, x=int(ox+x*rw/w), y=int(oy+y*rh/h))
                root.update()
            app.generate_mask(); settle()
            validate_arrays(app.query.rgb, app.mask)
            assert app.mask_info['automatic_bbox'] and app.bbox == (10, 10, 556, 364)
            checks['automatic_bbox_grabcut_without_dragging'] = True
            assert not hasattr(app, 'choose_mask')
            assert all(control.cget('text') != 'Nạp mask PNG' for control in app.controls if 'text' in control.keys())
            assert all(control.cget('text') != 'Kéo bbox' for control in app.controls if 'text' in control.keys())
            checks['gui_has_no_manual_mask_loader_or_bbox_mode'] = True
            before_mask = app.mask.copy()
            with mock.patch('tools.search.gui.messagebox.showinfo') as unpainted:
                app.refine_mask()
                assert unpainted.called and not app.busy()
            np.testing.assert_array_equal(app.mask, before_mask)
            checks['unpainted_apply_does_not_rerun_grabcut'] = True
            app.reference_mask_button.invoke(); settle()
            np.testing.assert_array_equal(app.mask, cv2.imread(str(mask), cv2.IMREAD_GRAYSCALE))
            assert app.mask_info['method'] == 'stored_mask_for_identical_source_sha256'
            assert 'không xác nhận' in app.mask_review.get()
            checks['reuse_mask_by_exact_source_hash_and_show_review_cues'] = True
            app.radius.set(3)
            ys, xs = np.nonzero(app.mask)
            point = (int(xs[len(xs)//2]), int(ys[len(ys)//2]))
            app.mode.set('keep'); event(*point, '<ButtonPress-1>'); event(*point, '<ButtonRelease-1>')
            app.mode.set('remove'); event(4, 4, '<ButtonPress-1>'); event(4, 4, '<ButtonRelease-1>')
            assert not np.array_equal(app.strokes, app.applied_strokes)
            with mock.patch('tools.search.gui.messagebox.showinfo') as pending:
                app.search()
                assert pending.called and not app.busy()
            checks['pending_strokes_block_search'] = True
            app.refine_mask(); settle()
            validate_arrays(app.query.rgb, app.mask)
            checks['keep_remove_strokes_and_refine_worker'] = True
            app.undo()
            app.refine_mask(); settle()
            checks['undo_and_reapply'] = True
            app.search()
            active = app.future
            app.search()
            assert active is app.future
            settle()
            checks['single_inflight_search'] = True
            assert app.result['returned'] == 5 and app.result['excluded_self_files'] == 1
            assert all(label.cget('text').startswith('#'+str(i+1)) and label.cget('text') != f'#{i+1} —'
                       for i, (_, label) in enumerate(app.cards))
            checks['top5_images_labels_and_distances'] = True
            app.show_hit(4)
            details = json.loads(app.detail.get('1.0', 'end'))
            assert abs(sum(details['group_distances'].values())-details['distance']) < 1e-12
            app.variant.set('flipped'); app.block.set('S3'); app.show_vector()
            assert 'S3_mask_r5_c7' in app.vector_text.get('1.0', 'end')
            checks['contributions_validity_automatic_region_vector_blocks'] = True
            with mock.patch('tools.search.gui.filedialog.askdirectory', return_value=str(PROJECT_ROOT/'outputs/search/gui_exports')):
                app.export()
            settle()
            checks['export_callback'] = True
            app.include_self_button.invoke()
            assert app.include_self.get() and app.result is None
            app.search(); settle()
            assert app.result['excluded_self_files'] == 0
            assert app.result['policies']['self_match'] == 'include self matches'
            checks['include_identical_query_files_on_request'] = True
            # Verify a user-visible error reaches the main-thread error handler.
            with mock.patch('tools.search.gui.filedialog.askopenfilename', return_value=str(out/'missing.png')):
                app.choose_image()
            while app.busy():
                root.update(); time.sleep(.02)
            assert errors and app.query is not None
            checks['worker_error_display_keeps_current_query'] = True
            errors.clear()
            app.show_result(app.result)
            root.update()
            query_result = app.result['output_directory']
            current_query = app.query
            current_result = app.result
            with mock.patch('tools.search.gui.filedialog.askopenfilename', return_value=''):
                app.other_image_button.invoke()
            assert app.query is current_query and app.result is current_result
            replacement = PROJECT_ROOT/'outputs/search/functional_inputs/donkey_864x576.png'
            app.mode.set('remove')
            with mock.patch('tools.search.gui.filedialog.askopenfilename', return_value=str(replacement)):
                app.other_image_button.invoke()
            settle()
            assert app.query.path == replacement and app.mask is not None and app.result is None
            assert app.mask_info['automatic_bbox'] and app.bbox == (10, 10, 844, 556)
            assert app.mode.get() == 'keep' and not app.include_self.get()
            assert np.all(app.strokes == 255) and np.array_equal(app.strokes, app.applied_strokes)
            assert all(label.cget('text') == f'#{i+1} —' and picture.cget('image') == ''
                       for i, (picture, label) in enumerate(app.cards))
            assert app.detail.get('1.0', 'end').strip() == ''
            assert app.vector_text.get('1.0', 'end').strip() == ''
            checks['choose_another_image_cancels_safely_and_automatically_segments_new_source'] = True
            result = dict(passed=True, checks=checks, tkinter_version=tk.TkVersion,
                          query_result=query_result,
                          manual_visual_review=False, screenshot=False,
                          note='Automated callbacks/events on real macOS Tk; no claim of manual UI review or retrieval quality.')
            write_json(out/'gui_smoke.json', result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        write_json(out/'gui_smoke.json', dict(passed=False, checks=checks, error=f'{type(exc).__name__}: {exc}'))
        raise
    finally:
        # No worker may outlive its Tk resources after a failed assertion.
        if app.busy():
            app.future.result(timeout=90)
            app.future = None
        app.close()


if __name__ == '__main__':
    main()
