"""Pre-verification checkpoint; all real data/results are read-only."""
from datetime import datetime
import fcntl
import json
from pathlib import Path
import shutil
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from docs.results_migration_audit.prepare import sha,digest


def write(name,value):
    (AUDIT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    protected=[]
    for start in ['data','outputs/segmentation','outputs/inventory']:
        for p in sorted((ROOT/start).rglob('*')):
            if p.is_file():
                s=p.stat()
                protected.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),size=s.st_size,mtime_ns=s.st_mtime_ns))
    write('protected_before.json',protected)
    selected=[ROOT/'README.md',ROOT/'.python-version',ROOT/'.gitignore',ROOT/'requirements.txt',ROOT/'requirements_image_tools.txt']
    selected.extend(sorted((ROOT/'docs').glob('*.md')))
    for start in ['tools','tests','docs/guides','docs/reports','bo_tool_anh_576x384','reports']:
        base=ROOT/start
        if base.exists():
            selected.extend([base,*sorted(base.rglob('*'))])
    files=[p for p in selected if p.is_file()]
    free=shutil.disk_usage(ROOT).free
    required=sum(p.stat().st_size+4096 for p in selected)*2+1024**3
    assert free>required, f'Insufficient backup/restore reserve: {free} < {required}'
    backup=ROOT/'outputs/backups'/('pre_verification_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True)
    archive_path=backup/'project_controls_before.tar'
    records=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in files]
    with tarfile.open(archive_path,'w',format=tarfile.PAX_FORMAT) as archive:
        for p in selected:
            archive.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
    with tarfile.open(archive_path) as archive:
        for r in records:
            assert digest(archive.extractfile(r['path']))==r['sha256']
    write('controls_before.json',records)
    (backup/'archive.sha256').write_text(sha(archive_path)+'  '+archive_path.name+'\n')
    write('preflight.json',dict(verified=True,backup=str(archive_path),backup_sha256=sha(archive_path),
          bytes=archive_path.stat().st_size,files=len(files),protected_real_files=len(protected),free_bytes=free,
          required_bytes_with_reserve=required))
    fixture=ROOT/'outputs/validation'/('migration_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    fixture.mkdir(parents=True)
    write('fixture.json',dict(root=str(fixture),separate_from_real_data=True))
    print(json.dumps(dict(verified=True,backup=str(archive_path),fixture=str(fixture),protected_files=len(protected))))


if __name__=='__main__':
    with (ROOT/'data/cropped_images_576x384/.tool_anh.lock').open('rb') as crop_lock, \
            (ROOT/'outputs/segmentation/grabcut/.run.lock').open('rb') as mask_lock:
        for lock in [crop_lock,mask_lock]:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        main()
