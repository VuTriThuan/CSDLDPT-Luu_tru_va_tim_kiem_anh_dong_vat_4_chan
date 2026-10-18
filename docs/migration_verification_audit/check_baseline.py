"""Account for every step-1 entry; validate real artifact paths and edit history."""
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import AUDIT,sha,write
from tools import project_paths as paths


def authorized_changes():
    changes={}
    for record in json.loads((ROOT/'docs/source_migration_audit/source_changes.json').read_text()):
        changes[record['new_path']]=record['new_sha256']
    for folder in ['data_migration_audit','results_migration_audit','environment_migration_audit']:
        for record in json.loads((ROOT/'docs'/folder/'source_document_changes.json').read_text()):
            changes[record['path']]=record.get('after_sha256',record.get('sha256_after'))
    for record in json.loads((ROOT/'docs/data_migration_audit/state_conversions.json').read_text()):
        if record['converted']:
            changes[record['new_path']]=record['sha256_after']
    for record in json.loads((AUDIT/'controls_before.json').read_text()):
        if record['path'].startswith('docs/') or record['path']=='README.md':
            changes[record['path']]=record['sha256']
    after=AUDIT/'controls_after.json'
    if after.exists():
        for record in json.loads(after.read_text()):
            changes[record['path']]=record['sha256']
    return changes


def main():
    baseline=json.loads((ROOT/'docs/migration_audit/baseline_inventory.json').read_text())['entries']
    moved={**json.loads((ROOT/'docs/source_migration_audit/source_mapping.json').read_text()),
           **json.loads((ROOT/'docs/documentation_migration_audit/document_mapping.json').read_text())}
    authorized=authorized_changes()
    current_hashes={}

    def current_sha(path):
        key=str(path)
        if key not in current_hashes:
            current_hashes[key]=sha(path)
        return current_hashes[key]

    def location(relative):
        if relative in moved:
            return ROOT/moved[relative]
        path=Path(relative)
        if len(path.parts)>1 and path.parts[0]=='data' and path.parts[1] in paths.LEGACY_DATA_FOLDERS:
            return ROOT/'data'/paths.LEGACY_DATA_FOLDERS[path.parts[1]]/Path(*path.parts[2:])
        for before,after in paths.LEGACY_RESULT_PATHS.items():
            try:
                return ROOT/after/path.relative_to(before)
            except ValueError:
                pass
        # Retain the link itself here; dereferencing a Python launcher would
        # incorrectly compare the external base interpreter with a symlink.
        return ROOT/path

    rows=[]
    problems=[]
    for record in baseline:
        original=record['path']
        target=location(original)
        retired=original=='bo_tool_anh_576x384/.venv' or original.startswith('bo_tool_anh_576x384/.venv/')
        git=original=='.git' or original.startswith('.git/')
        row=dict(original_path=original,current_path=str(target.relative_to(ROOT)),kind=record['kind'],
                 category=record['category'],before_sha256=record.get('sha256',''),current_sha256='')
        if retired:
            row['status']='retired_environment_in_verified_backup'
        elif git:
            row['status']='mutable_git_metadata'
            if record['kind']=='file' and target.is_file():
                row['current_sha256']=current_sha(target)
                row['git_bytes_unchanged']=row['current_sha256']==record['sha256']
        elif record['kind']=='directory':
            row['status']='directory_preserved' if target.is_dir() else 'unexpected_missing'
        elif record['kind']=='symlink':
            expected=record.get('link_target',record.get('target'))
            row['status']='symlink_unchanged' if target.is_symlink() and os.readlink(target)==expected else 'unexpected_symlink_change'
        elif not target.is_file():
            row['status']='unexpected_missing'
        else:
            actual=current_sha(target)
            row['current_sha256']=actual
            if actual==record['sha256']:
                row['status']='relocated_unchanged' if original!=row['current_path'] else 'unchanged'
            elif authorized.get(row['current_path'])==actual:
                row['status']='documented_content_update'
            else:
                row['status']='unexpected_content_change'
        if row['status'].startswith('unexpected'):
            problems.append(row)
        rows.append(row)
    write('baseline_accounting.json',rows)
    write('baseline_problems.json',problems)
    assert not problems,problems[:10]
    assets=[r for r in rows if r['kind']=='file' and (r['original_path'].startswith('data/') or r['original_path'].startswith('reports/yeu_cau_2/grabcut_output/'))]
    with (AUDIT/'asset_sha256.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['original_path','current_path','category','status','before_sha256','current_sha256'])
        writer.writeheader()
        writer.writerows({k:r[k] for k in writer.fieldnames} for r in assets)
    data_folders=[paths.SOURCE_IMAGES_DIR,paths.CROPPED_IMAGES_DIR,paths.REJECTED_CROPS_DIR]
    image_counts={str(p.relative_to(ROOT)):sum(f.is_file() and f.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'} for f in p.iterdir()) for p in data_folders}
    original_archive=ROOT/'outputs/backups/pre_migration_20261017_100229/project_snapshot.tar'
    with tarfile.open(original_archive) as archive:
        old_state=json.loads(archive.extractfile('data/anh-da-cat-576x384/_cat_tu_dong.json').read())
    current_state=json.loads((paths.CROPPED_IMAGES_DIR/'_cat_tu_dong.json').read_text())
    expected=dict(old_state,source=str(paths.SOURCE_IMAGES_DIR),source_relative='../source_images')
    assert current_state==expected,'Crop state changed beyond the documented source fields'
    output=paths.GRABCUT_OUTPUT_DIR
    manifests=list(csv.DictReader((output/'manifest.csv').open(newline='')))
    assert len(manifests)==len({r['filename'] for r in manifests})==812
    for row in manifests:
        assert current_sha(paths.CROPPED_IMAGES_DIR/row['filename'])==row['source_sha256']
        for kind in ['mask','overlay','quicklook']:
            relative=Path(row[kind+'_path'])
            target=output/relative
            assert not relative.is_absolute() and '..' not in relative.parts and target.is_file()
            assert target.resolve().is_relative_to(output)
            if kind!='quicklook':
                assert current_sha(target)==row[kind+'_sha256']
    referenced_quicklooks={r['quicklook_path'] for r in manifests}
    assert len(referenced_quicklooks)==102
    assert {str(p.relative_to(output)) for p in (output/'masks').glob('*.png')}=={r['mask_path'] for r in manifests}
    assert {str(p.relative_to(output)) for p in (output/'overlays').rglob('*.png')}=={r['overlay_path'] for r in manifests}
    assert {str(p.relative_to(output)) for p in (output/'quicklooks').glob('*.jpg')}==referenced_quicklooks
    manifest_by_name={r['filename']:r for r in manifests}
    history=[]
    historical_differences=[]
    for folder in sorted((output/'manual_edits').iterdir()):
        assert {p.name for p in folder.iterdir()}=={'record.json','mask_before.png','overlay_before.png','scribbles.png'}
        record=json.loads((folder/'record.json').read_text())
        assert record['filename'] in manifest_by_name
        current=manifest_by_name[record['filename']]
        details=dict(session=folder.name,filename=record['filename'],state=record['state'],
              mask_before_hash_matches_record=current_sha(folder/'mask_before.png')==record['manifest_before'].get('mask_sha256'),
              overlay_before_hash_matches_record=current_sha(folder/'overlay_before.png')==record['manifest_before'].get('overlay_sha256'),
              current_mask_matches_saved_after=current['mask_sha256']==record['manifest_after'].get('mask_sha256'),
              current_overlay_matches_saved_after=current['overlay_sha256']==record['manifest_after'].get('overlay_sha256'))
        history.append(details)
        if not details['overlay_before_hash_matches_record']:
            historical_differences.append(dict(session=folder.name,filename=record['filename'],
                 stored_overlay_before_sha256=current_sha(folder/'overlay_before.png'),
                 manifest_before_overlay_sha256=record['manifest_before'].get('overlay_sha256'),
                 unchanged_since_step_1=True,current_saved_after_hashes_match=details['current_mask_matches_saved_after'] and details['current_overlay_matches_saved_after'],
                 action='preserved_without_hash_rewrite'))
    zip_members=0
    with (ROOT/'docs/migration_audit/zip_member_sha256.csv').open(newline='') as stream:
        for record in csv.DictReader(stream):
            with zipfile.ZipFile(paths.resolve_project_reference(record['archive'])) as archive:
                payload=archive.read(record['member'])
                assert hashlib.sha256(payload).hexdigest()==record['sha256']
                zip_members+=1
    write('history_relationships.json',history)
    write('historical_overlay_hash_differences.json',historical_differences)
    protected=json.loads((AUDIT/'protected_before.json').read_text())
    for record in protected:
        path=ROOT/record['path']
        assert current_sha(path)==record['sha256'] and path.stat().st_mtime_ns==record['mtime_ns']
    actual_protected={str(p.relative_to(ROOT)) for base in ['data','outputs/segmentation','outputs/inventory'] for p in (ROOT/base).rglob('*') if p.is_file()}
    assert actual_protected=={r['path'] for r in protected}
    legacy=[]
    for base in ['bo_tool_anh_576x384','reports']:
        files=[p for p in (ROOT/base).rglob('*') if p.is_file()]
        legacy.append(dict(path=base,decision='retain',reason='Historical requirements/bytecode, including tests whose source is absent; not empty.',
                           files=[dict(path=str(p.relative_to(ROOT)),sha256=current_sha(p),bytes=p.stat().st_size) for p in sorted(files)],
                           contains_python_environment=any(p.name=='pyvenv.cfg' for p in files)))
    write('legacy_directories.json',legacy)
    result=dict(verified=True,baseline_entries=len(rows),baseline_files=sum(r['kind']=='file' for r in rows),
                statuses=dict(Counter(r['status'] for r in rows)),unexpected_changes=0,image_counts=image_counts,
                mask_pngs=812,overlay_pngs=812,quicklooks=102,manifest_rows=812,manifest_columns=len(manifests[0]),
                manifest_asset_hashes_verified=2436,manual_edit_sessions=len(history),history_files=4*len(history),
                history_consistency_counts={key:sum(r[key] for r in history) for key in list(history[0])[3:]},
                zip_members_verified=zip_members,crop_state_fields_changed_since_step_1=['source','source_relative'],
                crop_state_records_unchanged=current_state['images']==old_state['images'],
                protected_real_files_unchanged=len(protected),legacy_files_retained=sum(len(r['files']) for r in legacy),
                directories_deleted=[],manifest_sha256=current_sha(output/'manifest.csv'))
    write('baseline_verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
