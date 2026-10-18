"""Run the final workflow on an explicitly isolated, retained one-image fixture."""
import argparse
from collections import Counter
from contextlib import redirect_stdout,redirect_stderr
import csv
import io
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import sha,write


def fixture():
    path=Path(json.loads((AUDIT/'fixture.json').read_text())['root']).resolve()
    assert path.parent==ROOT/'outputs/validation' and path.name.startswith('migration_')
    return path


def image_phase():
    from PIL import Image
    from tools.image_processing import auto_crop as crop,rename_images as rename,review_images as review
    root=fixture()
    source=root/'data/source_images'
    cropped=root/'data/cropped_images_576x384'
    rejected=root/'data/rejected_crops'
    source.mkdir(parents=True)
    rejected.mkdir()
    original=next(p for p in sorted((ROOT/'data/source_images').iterdir()) if p.suffix.lower()=='.jpg')
    copied=source/original.name
    shutil.copy2(original,copied)
    original_hash=sha(original)
    model=Path.home()/'.cache/animal-crop/u2net.onnx'
    assert sha(model)=='8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491'
    assert crop.file_md5(model)==crop.MODELS['u2net'][1]

    def run_crop():
        with patch.object(sys,'argv',['auto_crop.py','--input',str(source),'--output',str(cropped),'--threads','1']), \
                patch.object(crop.urllib.request,'urlopen',side_effect=AssertionError('Downloads forbidden in verification')):
            crop.main()

    run_crop()
    state=json.loads((cropped/'_cat_tu_dong.json').read_text())
    record=state['images'][copied.name]
    assert record['status']=='saved',record
    artifact=cropped/record['output']
    with Image.open(artifact) as image:
        assert image.size==(576,384) and image.format=='JPEG'
    result_hash=sha(artifact)
    modified_at=artifact.stat().st_mtime_ns
    run_crop()
    assert sha(artifact)==result_hash and artifact.stat().st_mtime_ns==modified_at
    initial_images=Counter(sha(p) for base in [source,cropped,rejected] for p in base.iterdir() if p.suffix.lower() in crop.EXTENSIONS)
    state_bytes=(cropped/'_cat_tu_dong.json').read_bytes()
    # Rename CLI has fixed project defaults; redirect only its path constants to
    # this fixture, leaving validation, matching and file operations unmodified.
    with patch.multiple(rename,SOURCE=source,CROPPED=cropped,DELETED=rejected,DATA=root/'data'):
        with patch.object(sys,'argv',['rename_images.py']):
            rename.main()
        assert (cropped/'_cat_tu_dong.json').read_bytes()==state_bytes
        with patch.object(sys,'argv',['rename_images.py','--apply']):
            rename.main()
    assert initial_images==Counter(sha(p) for base in [source,cropped,rejected] for p in base.iterdir() if p.suffix.lower() in crop.EXTENSIONS)
    state=json.loads((cropped/'_cat_tu_dong.json').read_text())
    name=next(iter(state['images']))
    artifact=cropped/state['images'][name]['output']
    assert name!=original.name and name.endswith('_0001.jpg')
    store=review.ReviewStore(cropped)
    before=artifact.read_bytes()
    store.flip(artifact)
    flipped_hash=sha(artifact)
    run_crop()
    assert sha(artifact)==flipped_hash
    store.delete(artifact)
    assert not artifact.exists() and (rejected/artifact.name).is_file()
    run_crop()
    assert not artifact.exists(), 'Resume undid a deletion decision'
    store.undo()
    store.undo()
    store.sync_report()
    assert artifact.read_bytes()==before
    run_crop()
    assert sha(artifact)==result_hash
    assert sha(source/name)==original_hash and sha(original)==original_hash
    result=dict(verified=True,fixture=str(root),copied_from=str(original.relative_to(ROOT)),
                original_sha256=original_hash,fixture_source=name,crop=artifact.name,
                crop_sha256=result_hash,real_source_unchanged=True,model_sha256=sha(model),
                checks=['actual_u2net_crop','crop_resume_without_rewrite','rename_preview_read_only',
                        'rename_apply_preserves_image_bytes','review_flip','resume_preserves_flip',
                        'review_delete','resume_preserves_delete','undo_delete_and_flip'])
    write('image_workflow.json',result)
    print(json.dumps(result,ensure_ascii=False))


def mask_phase():
    import numpy as np
    from PIL import Image
    from tools.segmentation import run_grabcut as gc,review_overlays,edit_masks,sync_overlays
    gc.cv2.setNumThreads(1)
    root=fixture()
    source=root/'data/cropped_images_576x384'
    output=root/'grabcut'
    args=['--all','--input-dir',str(source),'--output-dir',str(output)]
    assert gc.main(args)==0
    assert gc.main(args+['--resume'])==0
    assert json.loads((output/'summary.json').read_text())['resumed_this_run']==1
    row=next(csv.DictReader((output/'manifest.csv').open()))
    clone=root/'corrupt_flat_resume_case'
    shutil.copytree(output,clone)
    (clone/row['mask_path']).write_bytes(b'corrupted fixture mask')
    assert gc.main(['--all','--input-dir',str(source),'--output-dir',str(clone),'--resume'])==0
    summary=json.loads((clone/'summary.json').read_text())
    assert summary['attempted_this_run']==1 and summary['resumed_this_run']==0
    session=review_overlays.ReviewSession(output/'overlays')
    previous,pending=session.classify('s')
    assert pending.parent.name=='needs_revision'
    session.undo()
    assert previous.is_file() and not pending.exists()
    session.classify('s')
    assert not sync_overlays.sync(output,source,apply=True)['errors']
    repository=edit_masks.MaskRepository(output,source)
    document=repository.load(repository.pending()[0])
    ys,xs=np.nonzero(document.mask)
    assert len(xs)>100
    keep=(int(xs[len(xs)//2]),int(ys[len(ys)//2]))
    remove=(int(xs[len(xs)//5]),int(ys[len(ys)//5]))
    if abs(keep[0]-remove[0])+abs(keep[1]-remove[1])<20:
        remove=(int(xs[0]),int(ys[0]))
    document.paint(keep,keep,3,edit_masks.KEEP)
    document.paint(remove,remove,3,edit_masks.REMOVE)
    updated=edit_masks.refine_mask(document.image,document.mask,document.strokes)
    assert updated[keep[1],keep[0]]==255 and updated[remove[1],remove[0]]==0
    changed=int(np.count_nonzero(updated!=document.mask))
    assert changed>0
    document.apply_result(updated)
    document.undo()
    assert not document.ready
    document.apply_result(updated)
    protected={p:p.read_bytes() for p in [document.overlay_path,document.mask_path,output/'manifest.csv']}
    real_atomic=edit_masks.atomic_bytes
    failed=False

    def fail_manifest_once(path,data):
        nonlocal failed
        if path==output/'manifest.csv' and not failed:
            failed=True
            raise OSError('Injected failure on fixture manifest write')
        return real_atomic(path,data)

    with patch.object(edit_masks,'atomic_bytes',side_effect=fail_manifest_once):
        try:
            repository.save(document)
        except OSError:
            pass
        else:
            raise AssertionError('Injected write failure did not propagate')
    assert failed and {p:p.read_bytes() for p in protected}==protected
    assert not (output/'overlays/accepted'/document.overlay_path.name).exists()
    accepted,history=repository.save(document)
    record=json.loads((history/'record.json').read_text())
    assert record['state']=='saved' and accepted.parent.name=='accepted'
    assert sha(document.mask_path)==record['manifest_after']['mask_sha256']
    assert sha(accepted)==record['manifest_after']['overlay_sha256']
    assert not sync_overlays.sync(output,source,apply=True)['errors']
    readonly_before={p:p.read_bytes() for p in output.rglob('*') if p.is_file()}
    report=sync_overlays.sync(output,source,apply=False,verify=True)
    assert not report['errors'],report
    assert {p:p.read_bytes() for p in readonly_before}==readonly_before
    payload={p:p.read_bytes() for p in [accepted,document.mask_path,*history.iterdir()]}
    assert gc.main(args+['--resume'])==0
    resumed=json.loads((output/'summary.json').read_text())
    assert resumed['attempted_this_run']==0 and resumed['resumed_this_run']==1
    assert {p:p.read_bytes() for p in payload}==payload
    row=next(csv.DictReader((output/'manifest.csv').open()))
    assert row['overlay_path'].startswith('overlays/accepted/') and row['review_result']=='dat'
    for field in ['mask','overlay','quicklook']:
        path=output/row[field+'_path']
        assert path.is_file()
        with Image.open(path) as image:
            image.verify()
    histories=[json.loads(p.read_text()) for p in (output/'manual_edits').glob('*/record.json')]
    assert Counter(r['state'] for r in histories)==Counter(saved=1,rolled_back=1)
    # A separate queue is retained for U2Net, leaving the edited GrabCut result intact.
    regeneration_previous=root/'regeneration_previous'
    shutil.copytree(output,regeneration_previous)
    moved=regeneration_previous/row['overlay_path']
    queue=regeneration_previous/'overlays/needs_revision'/moved.name
    moved.rename(queue)
    rows=[dict(row,overlay_path=queue.relative_to(regeneration_previous).as_posix())]
    gc.write_csv(regeneration_previous/'manifest.csv',rows)
    result=dict(verified=True,fixture=str(root),changed_mask_pixels=changed,history_states=dict(Counter(r['state'] for r in histories)),
                source_sha256=sha(source/row['filename']),mask_sha256=sha(output/row['mask_path']),
                overlay_sha256=sha(accepted),readonly_sync_verified=True,
                checks=['grabcut_create','grabcut_resume','corrupt_flat_mask_retry','classify_and_undo',
                        'manifest_sync','mask_open','paint_keep_remove','real_grabcut_refinement','undo_refinement',
                        'atomic_save_failure_rollback','mask_save_with_history','overlay_sync_and_quicklook_verify',
                        'resume_retains_edited_classified_mask','manifest_artifact_paths'])
    write('mask_workflow.json',result)
    print(json.dumps(result,ensure_ascii=False))


def regeneration_phase():
    import numpy as np
    from PIL import Image
    from tools.segmentation import regenerate_masks as batch
    root=fixture()
    previous=root/'regeneration_previous'
    source=root/'data/cropped_images_576x384'
    output=root/'regenerated_masks'
    protected={p:p.read_bytes() for base in [previous,source] for p in base.rglob('*') if p.is_file()}
    args=batch.parse_args(['--source-dir',str(source),'--previous-dir',str(previous),
                          '--queue-dir',str(previous/'overlays/needs_revision'),'--output-dir',str(output),'--threads','1'])
    assert batch.run(args)==0
    args.resume=True
    assert batch.run(args)==0
    summary=json.loads((output/'summary.json').read_text())
    assert summary['reused_this_run']==1 and summary['processed_this_run']==0
    row=next(csv.DictReader((output/'manifest.csv').open()))
    assert batch.reusable(row,output)
    for field in ['mask','overlay','quicklook']:
        with Image.open(output/row[field+'_path']) as image:
            image.verify()
    with Image.open(output/row['mask_path']) as image:
        assert image.size==(576,384) and set(np.unique(np.asarray(image))).issubset({0,255})
    assert {p:p.read_bytes() for p in protected}==protected
    result=dict(verified=True,fixture=str(root),regenerated_images=1,resumed_without_processing=1,
                previous_results_and_source_unchanged=True,manifest_artifact_paths_verified=True)
    write('regeneration_workflow.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['images','masks','regeneration'])
    phase=parser.parse_args().phase
    {'images':image_phase,'masks':mask_phase,'regeneration':regeneration_phase}[phase]()
