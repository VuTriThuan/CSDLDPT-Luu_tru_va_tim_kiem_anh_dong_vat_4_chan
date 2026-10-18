"""Rehash every canonical checkpoint and restore representative original assets."""
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import AUDIT,sha,digest,write


def main():
    original=json.loads((ROOT/'docs/migration_audit/backup_verification.json').read_text())
    checkpoints=[(Path(original['archive']),original['archive_sha256'])]
    for name in ['data_migration_audit','results_migration_audit','environment_migration_audit']:
        data=json.loads((ROOT/'docs'/name/'preflight.json').read_text())
        checkpoints.append((Path(data['backup']),data['backup_sha256']))
    current=json.loads((AUDIT/'preflight.json').read_text())
    checkpoints.append((Path(current['backup']),current['backup_sha256']))
    checkpoints.extend([(ROOT/'docs/source_migration_audit/source_before.tar','64dafb5ee43e6c4ab3459c9701f35835778207a4e824619593469ddc6a67ee6a'),
                        (ROOT/'docs/documentation_migration_audit/documents_before.tar','fb0707220706b8fa9939d86fbd1337280b0a45003f8c6254359d28a6dec438e2')])
    verified=[]
    for path,expected in checkpoints:
        actual=sha(path)
        assert actual==expected,path
        verified.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=actual,verified=True))
    baseline=json.loads((ROOT/'docs/migration_audit/baseline_inventory.json').read_text())['entries']
    chosen=[]
    for prefix in ['data/anh-chua-loc/','data/anh-da-cat-576x384/','data/anh-da-cat-576x384-da-xoa/',
                   'reports/yeu_cau_2/grabcut_output/masks/','reports/yeu_cau_2/grabcut_output/overlays/',
                   'reports/yeu_cau_2/grabcut_output/quicklooks/','reports/yeu_cau_2/grabcut_output/manual_edits/']:
        entries=[r for r in baseline if r['kind']=='file' and r['path'].startswith(prefix)]
        chosen.extend(entries[:4] if 'manual_edits' in prefix else entries[:1])
    for name in ['reports/yeu_cau_2/grabcut_output/manifest.csv','reports/yeu_cau_2/grabcut_output/run_config.json',
                 'data/anh-da-cat-576x384/_cat_tu_dong.json']:
        chosen.append(next(r for r in baseline if r['path']==name))
    restored=[]
    with tarfile.open(checkpoints[0][0]) as archive,tempfile.TemporaryDirectory(prefix='btl_final_restore_') as tmp:
        members={m.name:m for m in archive.getmembers()}
        for record in chosen:
            member=members[record['path']]
            assert digest(archive.extractfile(member))==record['sha256']
            target=Path(tmp)/record['path']
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            os.chmod(target,record['mode'])
            os.utime(target,ns=(record['mtime_ns'],record['mtime_ns']))
            assert sha(target)==record['sha256']
            restored.append(dict(path=record['path'],sha256=record['sha256'],bytes=target.stat().st_size))
    seals={}
    for name in ['source_migration_audit','documentation_migration_audit','data_migration_audit','results_migration_audit','environment_migration_audit']:
        folder=ROOT/'docs'/name
        rows=(folder/'artifacts.sha256').read_text().splitlines()
        for line in rows:
            expected,filename=line.split('  ',1)
            assert sha(folder/filename)==expected,(name,filename)
        seals[name]=len(rows)
    supplemental=[]
    for record in json.loads((ROOT/'docs/migration_audit/external_dependencies.json').read_text()):
        if record.get('supplemental_backup_copy'):
            path=Path(record['supplemental_backup_copy'])
            assert sha(path)==record['sha256'],path
            supplemental.append(dict(path=str(path.relative_to(ROOT)),sha256=record['sha256'],verified=True))
    wheelhouse=ROOT/'outputs/backups/pre_environment_migration_20261017_105624/wheels'
    wheel_lines=(wheelhouse/'wheels.sha256').read_text().splitlines()
    for line in wheel_lines:
        expected,name=line.split('  ',1)
        assert sha(wheelhouse/name)==expected
    write('backup_verification.json',dict(verified=True,checkpoints=verified,restored_samples=restored,
          temporary_restore_removed=True,previous_audit_seals=seals,supplemental_assets=supplemental,
          dependency_wheels_verified=len(wheel_lines)))
    print(json.dumps(dict(verified=True,checkpoints=len(verified),restored_samples=len(restored),previous_audit_seals=seals)))


if __name__=='__main__':
    main()
