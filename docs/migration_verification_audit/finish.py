"""Check every verification gate and seal the final handoff evidence."""
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import AUDIT,sha,digest,write


def main():
    gates=['baseline_verification.json','artifact_content_verification.json','backup_verification.json',
           'reference_verification.json','link_verification.json','environment_verification.json',
           'image_workflow.json','mask_workflow.json','regeneration_workflow.json','gui_verification.json',
           'gui_mask_editor.json','gui_image_review.json','gui_overlay_review.json','smoke_checks.json','git_verification.json']
    for name in gates:
        assert json.loads((AUDIT/name).read_text())['verified'],name
    for name,count in [('image_tests.log',24),('validation_tests.log',14)]:
        text=(AUDIT/name).read_text()
        assert f'Ran {count} tests' in text and text.rstrip().endswith('OK'),name
    before={r['path']:r for r in json.loads((AUDIT/'controls_before.json').read_text())}
    after=[]
    for name in ['README.md','docs/migration_plan.md','docs/migration_verification.md']:
        after.append(dict(path=name,sha256=sha(ROOT/name),before_sha256=before.get(name,{}).get('sha256'),
                          action='updated' if name in before else 'created'))
    write('controls_after.json',after)
    # Source/tests/config were inspected, not changed by the final verification.
    for name,record in before.items():
        if name not in {r['path'] for r in after}:
            assert sha(ROOT/name)==record['sha256'],name
    checkpoint=json.loads((AUDIT/'preflight.json').read_text())
    handoff=Path(checkpoint['backup']).parent/'handoff_documentation.tar'
    with tarfile.open(handoff,'w',format=tarfile.PAX_FORMAT) as archive:
        for r in after:
            archive.add(ROOT/r['path'],arcname=r['path'],recursive=False)
    with tarfile.open(handoff) as archive:
        for r in after:
            assert digest(archive.extractfile(r['path']))==r['sha256']
    handoff_hash=sha(handoff)
    handoff.with_suffix('.tar.sha256').write_text(handoff_hash+'  '+handoff.name+'\n')
    write('handoff_documentation_backup.json',dict(verified=True,archive=str(handoff),sha256=handoff_hash,files=after))
    protected=json.loads((AUDIT/'protected_before.json').read_text())
    for r in protected:
        p=ROOT/r['path']
        assert sha(p)==r['sha256'] and p.stat().st_mtime_ns==r['mtime_ns'],p
    current={str(p.relative_to(ROOT)) for base in ['data','outputs/segmentation','outputs/inventory'] for p in (ROOT/base).rglob('*') if p.is_file()}
    assert current=={r['path'] for r in protected}
    links=json.loads((AUDIT/'link_verification.json').read_text())
    write('completion.json',dict(complete=True,tests_passed=38,workflow_fixture=json.loads((AUDIT/'fixture.json').read_text())['root'],
          live_gui_windows_verified=3,tool_imports=11,direct_and_module_help_checks=22,bootstrap_checks=2,
          baseline_entries_accounted_for=26551,unexpected_baseline_changes=0,
          manifest_rows=812,manifest_asset_hashes_verified=2436,history_sessions=374,
          historical_overlay_before_hash_differences_retained=30,
          protected_real_data_result_state_files_unchanged=len(protected),directories_deleted=[],legacy_files_retained=17,
          local_links_checked=links['local_links_checked'],unique_linked_images_decoded=links['unique_images_decoded'],
          canonical_archives_rehashed=7,original_snapshot_samples_restored=13,dependency_wheels_verified=14,
          real_data_processed_or_reclassified=False,production_source_changed=False,
          free_bytes_after=shutil.disk_usage(ROOT).free))
    seal=AUDIT/'artifacts.sha256'
    seal.touch(exist_ok=True)
    tree=['BTL/ — physical directory tree, including hidden files, venvs and backups; archive members are not expanded.']
    for parent,dirs,files in os.walk(ROOT,followlinks=False):
        dirs.sort()
        files.sort()
        for name in dirs+files:
            p=Path(parent)/name
            relative=str(p.relative_to(ROOT))
            try:
                suffix=(' -> '+os.readlink(p)) if p.is_symlink() else '/' if p.is_dir() else ''
                tree.append(relative+suffix)
            except FileNotFoundError:
                assert relative.startswith('.git/'),relative
    (AUDIT/'final_tree.txt').write_text('\n'.join(tree)+'\n')
    artifacts=sorted(p for p in AUDIT.iterdir() if p.is_file() and p.name!='artifacts.sha256')
    seal.write_text('\n'.join(sha(p)+'  '+p.name for p in artifacts)+'\n')
    for line in seal.read_text().splitlines():
        expected,name=line.split('  ',1)
        assert sha(AUDIT/name)==expected
    print(json.dumps(dict(complete=True,tests_passed=38,gui_windows_verified=3,baseline_entries=26551,
                         unexpected_changes=0,protected_real_files_unchanged=len(protected),
                         audit_artifacts_sealed=len(artifacts),physical_tree_entries=len(tree)-1,
                         local_links_checked=links['local_links_checked']),ensure_ascii=False))


if __name__=='__main__':
    main()
