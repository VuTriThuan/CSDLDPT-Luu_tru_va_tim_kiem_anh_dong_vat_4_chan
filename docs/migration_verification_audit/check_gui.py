"""Exercise real Tk windows on prepared fixture copies only; no production writes."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import AUDIT,sha,write
from docs.migration_verification_audit.workflow import fixture


def prepare():
    from tools.segmentation import run_grabcut as gc
    base=fixture()
    for name in ['gui_mask_editor','gui_overlay_review']:
        assert not (base/name).exists()
        shutil.copytree(base/'grabcut',base/name)
    output=base/'gui_mask_editor'
    row=next(csv.DictReader((output/'manifest.csv').open()))
    old=output/row['overlay_path']
    new=output/'overlays/needs_revision'/old.name
    old.rename(new)
    row.update(overlay_path=str(new.relative_to(output)),review_status='can_sua',review_result='can_sua')
    gc.write_csv(output/'manifest.csv',[row])
    assert not (base/'gui_images').exists()
    shutil.copytree(base/'data',base/'gui_images/data')
    state_path=base/'gui_images/data/cropped_images_576x384/_cat_tu_dong.json'
    state=json.loads(state_path.read_text())
    state['source']=str(base/'gui_images/data/source_images')
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    write('gui_preparation.json',dict(prepared=True,fixture=str(base),real_data_used_directly=False))
    print('GUI copies prepared under '+str(base))


def pump(root,seconds=.3):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        root.update()
        time.sleep(.015)


def image_review():
    import tkinter as tk
    from tools.image_processing import review_images as review
    folder=fixture()/'gui_images/data/cropped_images_576x384'
    root=tk.Tk()
    errors=[]
    root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
    viewer=review.Viewer(root,folder,review.ReviewStore(folder))
    try:
        pump(root,.5)
        assert root.winfo_ismapped() and viewer.image is not None and viewer.canvas.find_all()
        path=viewer.current()
        before=path.read_bytes()
        viewer.flip()
        pump(root,.45)
        assert viewer.store.state['images'][path.name]['review_flip_count']==1
        viewer.delete()
        pump(root,.45)
        assert not path.exists()
        viewer.undo()
        pump(root,.45)
        viewer.undo()
        pump(root,.45)
        assert path.read_bytes()==before and not errors,errors
        write('gui_image_review.json',dict(verified=True,interpreter=sys.executable,rendered=True,
              flip_delete_undo_verified=True,fixture_only=True))
    finally:
        root.destroy()


def mask_editor():
    import tkinter as tk
    import numpy as np
    from tools.segmentation import edit_masks,sync_overlays
    base=fixture()
    output=base/'gui_mask_editor'
    source=base/'data/cropped_images_576x384'
    source_hashes={p:sha(p) for p in source.iterdir() if p.is_file()}
    root=tk.Tk()
    errors=[]
    root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
    repository=edit_masks.MaskRepository(output,source)
    editor=edit_masks.MaskEditor(root,repository)
    try:
        with patch.object(edit_masks.messagebox,'showerror',side_effect=lambda *a,**k:errors.append(str(a))):
            pump(root,.5)
            assert root.winfo_ismapped() and editor.document is not None
            assert editor.left.find_all() and editor.right.find_all()
            original_mask=editor.document.mask.copy()
            ys,xs=np.nonzero(original_mask)
            points=[('keep',int(xs[len(xs)//2]),int(ys[len(ys)//2])),
                    ('remove',int(xs[len(xs)//5]),int(ys[len(ys)//5]))]
            for mode,x,y in points:
                editor.mode.set(mode)
                left,top,width,height=editor.transform
                event_x=int(left+(x+.5)*width/original_mask.shape[1])
                event_y=int(top+(y+.5)*height/original_mask.shape[0])
                editor.left.event_generate('<ButtonPress-1>',x=event_x,y=event_y)
                editor.left.event_generate('<ButtonRelease-1>',x=event_x,y=event_y)
                pump(root,.1)
            assert np.any(editor.document.strokes==edit_masks.KEEP)
            assert np.any(editor.document.strokes==edit_masks.REMOVE)
            editor.run_grabcut()
            deadline=time.monotonic()+30
            while editor.busy and time.monotonic()<deadline:
                pump(root,.05)
            assert not editor.busy and editor.document.ready and not errors,errors
            changed=int(np.count_nonzero(editor.document.mask!=original_mask))
            assert changed>0
            editor.save_button.invoke()
            pump(root)
            assert editor.document is None and not editor.files and not repository.pending()
            row=next(csv.DictReader((output/'manifest.csv').open()))
            assert row['overlay_path'].startswith('overlays/accepted/')
            assert sha(output/row['mask_path'])==row['mask_sha256']
            assert sha(output/row['overlay_path'])==row['overlay_sha256']
            assert not sync_overlays.sync(output,source,apply=True)['errors']
            assert {p:sha(p) for p in source_hashes}==source_hashes
            assert not errors,errors
            write('gui_mask_editor.json',dict(verified=True,interpreter=sys.executable,rendered_both_canvases=True,
                  synthetic_mouse_strokes=True,async_grabcut_completed=True,save_button_verified=True,
                  changed_mask_pixels=changed,fixture_only=True))
    finally:
        editor.executor.shutdown(wait=True)
        root.destroy()


def overlay_review():
    import tkinter as tk
    from tools.segmentation import review_overlays as review
    folder=fixture()/'gui_overlay_review/overlays'
    root=tk.Tk()
    errors=[]
    root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
    session=review.ReviewSession(folder,review_all=True)
    viewer=review.Viewer(root,session)
    try:
        pump(root,.4)
        assert root.winfo_ismapped() and viewer.image is not None and viewer.canvas.find_all()
        before=session.current()
        digest=sha(before)
        viewer.classify('s')
        pump(root)
        viewer.undo()
        pump(root)
        assert session.current()==before and sha(before)==digest and not errors,errors
        write('gui_overlay_review.json',dict(verified=True,interpreter=sys.executable,rendered=True,
                  category_and_undo_verified=True,fixture_only=True))
    finally:
        root.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','image_review'])
    action=parser.parse_args().action
    if action=='prepare':
        prepare()
    elif action=='image_review':
        image_review()
    else:
        assert json.loads((AUDIT/'gui_preparation.json').read_text())['prepared']
        mask_editor()
        overlay_review()
        child=subprocess.run([str(ROOT/'.venv-image-tools/bin/python'),'-B',str(Path(__file__)),'image_review'],cwd=ROOT,timeout=30)
        assert child.returncode==0
        write('gui_verification.json',dict(verified=True,windows_checked=3,fixture_only=True,
                  physical_user_keyboard_and_mouse_not_tested=True))
        print(json.dumps(dict(verified=True,windows_checked=3,fixture_only=True)))
