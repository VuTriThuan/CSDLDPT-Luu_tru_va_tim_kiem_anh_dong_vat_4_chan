"""Snapshot both original environments and current source/docs before replacement."""
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from docs.results_migration_audit.prepare import sha, digest
sys.path.insert(0, str(ROOT / 'docs/migration_audit'))
from restore_extended_attributes import attributes, restore


def write(name, value):
    (AUDIT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    starts = ['.venv', 'bo_tool_anh_576x384', 'tools', 'tests', 'docs', 'README.md']
    records = []
    for start in starts:
        base = ROOT / start
        for path in [base, *sorted(base.rglob('*'))] if base.is_dir() else [base]:
            if path == AUDIT or AUDIT in path.parents:
                continue
            stat = path.lstat()
            entry = dict(path=str(path.relative_to(ROOT)), size=stat.st_size,
                         kind='symlink' if path.is_symlink() else 'directory' if path.is_dir() else 'file',
                         mode=stat.st_mode & 0o7777, mtime_ns=stat.st_mtime_ns,
                         xattrs={k:base64.b64encode(v).decode() for k,v in attributes(path).items()})
            if entry['kind'] == 'file':
                entry['sha256'] = sha(path)
            elif entry['kind'] == 'symlink':
                entry['target'] = os.readlink(path)
            records.append(entry)
    required = 2 * sum(e['size'] + 4096 for e in records) + 1024**3
    free = shutil.disk_usage(ROOT).free
    assert free >= required, f'Insufficient safe backup/restore space: {free} < {required}'
    protected = []
    for start in ['data', 'outputs/segmentation', 'outputs/inventory']:
        for path in sorted((ROOT / start).rglob('*')):
            if path.is_file():
                protected.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                                      size=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns))
    original = ROOT / 'outputs/backups/pre_migration_20261017_100229/project_snapshot.tar'
    assert sha(original) == '2917b8e027a090fdb7564ac71336e4a82e7ce6e1dc9e038658a2c468e37bdbf7'
    backup = ROOT / 'outputs/backups' / ('pre_environment_migration_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True)
    target = backup / 'before_environment_migration.tar'
    with tarfile.open(target, 'w', format=tarfile.PAX_FORMAT) as archive:
        for entry in records:
            path = ROOT / entry['path']
            info = archive.gettarinfo(str(path), arcname=entry['path'])
            info.pax_headers.update({'BTL.xattr.' + k: v for k,v in entry['xattrs'].items()})
            if entry['kind'] == 'file':
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
            else:
                archive.addfile(info)
    samples = []
    with tarfile.open(target) as archive, tempfile.TemporaryDirectory(prefix='btl_env_restore_') as tmp:
        for entry in records:
            member = archive.getmember(entry['path'])
            if entry['kind'] == 'file':
                assert digest(archive.extractfile(member)) == entry['sha256'], entry['path']
                assert sha(ROOT / entry['path']) == entry['sha256'], 'Concurrent change: ' + entry['path']
            elif entry['kind'] == 'symlink':
                assert member.issym() and member.linkname == entry['target']
        for prefix in ['.venv/', 'bo_tool_anh_576x384/.venv/']:
            chosen = [prefix + 'pyvenv.cfg', prefix + 'bin/pip', prefix + 'bin/python3']
            for package in ['numpy/__init__.py', 'PIL/__init__.py', 'onnxruntime/__init__.py']:
                chosen.append(prefix + 'lib/python3.10/site-packages/' + package)
            for name in chosen:
                entry = next(e for e in records if e['path'] == name)
                path = Path(tmp) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if entry['kind'] == 'symlink':
                    path.symlink_to(entry['target'])
                    assert os.readlink(path) == entry['target']
                else:
                    path.write_bytes(archive.extractfile(name).read())
                    os.chmod(path, entry['mode'])
                    restore(Path(tmp), {name:entry['xattrs']})
                    os.utime(path, ns=(entry['mtime_ns'], entry['mtime_ns']))
                    assert sha(path) == entry['sha256']
                samples.append(name)
    archive_hash = sha(target)
    (backup / 'snapshot_inventory.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    (backup / 'archive.sha256').write_text(archive_hash + '  ' + target.name + '\n')
    write('before_inventory.json', records)
    write('protected_before.json', protected)
    write('preflight.json', dict(verified=True, backup=str(target), backup_sha256=archive_hash,
          original_full_backup_sha256_verified=True, free_bytes=free, required_bytes_with_reserve=required,
          archive_bytes=target.stat().st_size, entries=len(records),
          files=sum(e['kind']=='file' for e in records), restored_samples=samples,
          protected_data_and_result_files=len(protected)))
    print((AUDIT / 'preflight.json').read_text())


if __name__ == '__main__':
    main()
