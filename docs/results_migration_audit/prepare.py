"""Read-only baseline, verified incremental snapshot and sample restore for this phase."""
import base64
from collections import Counter
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'docs/migration_audit'))
from restore_extended_attributes import attributes, restore


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else digest(stream)


def digest(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def write(name, value):
    (AUDIT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    records = []
    for base in ['reports', 'tools', 'tests', 'docs', 'README.md']:
        start = ROOT / base
        candidates = [start, *sorted(start.rglob('*'))] if start.is_dir() else [start]
        for path in candidates:
            if path == AUDIT or AUDIT in path.parents:
                continue
            stat = path.lstat()
            entry = dict(path=path.relative_to(ROOT).as_posix(), size=stat.st_size,
                         mode=stat.st_mode & 0o7777, mtime_ns=stat.st_mtime_ns,
                         kind='symlink' if path.is_symlink() else 'directory' if path.is_dir() else 'file',
                         xattrs={key: base64.b64encode(value).decode()
                                 for key, value in attributes(path).items()})
            if entry['kind'] == 'file':
                entry['sha256'] = sha(path)
            elif entry['kind'] == 'symlink':
                entry['target'] = os.readlink(path)
            records.append(entry)
    required = sum(r['size'] + 4096 for r in records)
    free = shutil.disk_usage(ROOT).free
    if free < required * 2 + 1024**3:
        raise SystemExit(f'Insufficient space: free={free}, snapshot plus restore reserve={required*2+1024**3}')
    baseline = json.loads((ROOT / 'docs/migration_audit/baseline_inventory.json').read_text())['entries']
    folder_map = {'anh-chua-loc': 'source_images', 'anh-da-cat-576x384': 'cropped_images_576x384',
                  'anh-da-cat-576x384-da-xoa': 'rejected_crops'}
    protected = []
    for entry in baseline:
        p = Path(entry['path'])
        if entry['kind'] != 'file' or len(p.parts) < 3 or p.parts[0] != 'data' or p.parts[1] not in folder_map:
            continue
        if p.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}:
            continue
        current = Path('data') / folder_map[p.parts[1]] / Path(*p.parts[2:])
        assert sha(ROOT / current) == entry['sha256'], current
        protected.append(dict(original=entry['path'], current=str(current), sha256=entry['sha256']))
    assert len(protected) == 2594
    write('data_before.json', protected)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = ROOT / 'outputs/backups' / ('pre_results_migration_' + stamp)
    backup.mkdir(parents=True)
    archive_path = backup / 'before_results_migration.tar'
    with tarfile.open(archive_path, 'w', format=tarfile.PAX_FORMAT) as archive:
        for entry in records:
            path = ROOT / entry['path']
            info = archive.gettarinfo(str(path), arcname=entry['path'])
            info.pax_headers.update({'BTL.xattr.' + k: v for k, v in entry['xattrs'].items()})
            if entry['kind'] == 'file':
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
            else:
                archive.addfile(info)
    samples = []
    with tarfile.open(archive_path) as archive, tempfile.TemporaryDirectory(prefix='btl_restore_results_') as tmp:
        for entry in records:
            member = archive.getmember(entry['path'])
            if entry['kind'] == 'file':
                assert digest(archive.extractfile(member)) == entry['sha256'], entry['path']
                assert sha(ROOT / entry['path']) == entry['sha256'], 'Concurrent change: ' + entry['path']
        output = 'reports/yeu_cau_2/grabcut_output/'
        wanted = ['README.md', output + 'manifest.csv', output + 'run_config.json', output + '.run.lock']
        for prefix in ['masks/', 'overlays/', 'quicklooks/', 'manual_edits/', 'overlay_sync_backups/']:
            matches = [e['path'] for e in records if e['kind'] == 'file' and e['path'].startswith(output + prefix)]
            wanted.extend(matches[:4] if prefix == 'manual_edits/' else matches[:1])
        for name in wanted:
            entry = next(e for e in records if e['path'] == name)
            target = Path(tmp) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(name).read())
            os.chmod(target, entry['mode'])
            restore(Path(tmp), {name: entry['xattrs']})
            os.utime(target, ns=(entry['mtime_ns'], entry['mtime_ns']))
            assert sha(target) == entry['sha256']
            assert target.stat().st_mtime_ns == entry['mtime_ns']
            samples.append(name)
    archive_hash = sha(archive_path)
    (backup / 'archive.sha256').write_text(f'{archive_hash}  {archive_path.name}\n')
    (backup / 'snapshot_inventory.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    write('before_inventory.json', records)
    write('preflight.json', dict(verified=True, backup=str(archive_path), backup_sha256=archive_hash,
          archive_bytes=archive_path.stat().st_size, free_bytes=free, required_bytes_with_reserve=required*2+1024**3,
          entries=len(records), files=sum(e['kind']=='file' for e in records), restored_samples=samples,
          data_images_match_step_1=len(protected), kind_counts=dict(Counter(e['kind'] for e in records))))
    print((AUDIT / 'preflight.json').read_text())


if __name__ == '__main__':
    with (ROOT / 'reports/yeu_cau_2/grabcut_output/.run.lock').open('rb') as result_lock, \
            (ROOT / 'data/cropped_images_576x384/.tool_anh.lock').open('rb') as data_lock:
        for lock in [result_lock, data_lock]:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
