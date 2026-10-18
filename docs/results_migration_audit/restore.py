"""Restore the verified pre-results snapshot into a NEW staging directory only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docs.results_migration_audit.prepare import sha, digest
sys.path.insert(0, str(ROOT / 'docs/migration_audit'))
from restore_extended_attributes import restore, attributes
import base64


def verify_tree(target, records):
    restore(target, {r['path']: r['xattrs'] for r in records})
    generated = []
    for r in sorted(records, key=lambda e: len(Path(e['path']).parts), reverse=True):
        path = target / r['path']
        os.utime(path, ns=(r['mtime_ns'], r['mtime_ns']))
        assert path.stat().st_mtime_ns == r['mtime_ns']
        assert path.stat().st_mode & 0o7777 == r['mode']
        actual = {k:base64.b64encode(v).decode() for k,v in attributes(path).items()}
        assert all(actual.get(k) == v for k,v in r['xattrs'].items()), r['path']
        extra = sorted(set(actual) - set(r['xattrs']))
        # macOS automatically attaches provenance to freshly created files.
        assert set(extra).issubset({'com.apple.provenance'}), (r['path'], extra)
        if extra:
            generated.append(dict(path=r['path'], attributes=extra))
        if r['kind'] == 'file':
            assert sha(path) == r['sha256']
    return dict(verified=True, staging=str(target), entries=len(records), active_project_replaced=False,
                original_extended_attributes_verified=True, os_generated_attributes=generated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    target = args.output_dir.resolve()
    if target.exists() or not target.is_relative_to(ROOT / 'outputs'):
        raise ValueError('Choose a new staging directory under this project/outputs')
    preflight = json.loads(Path(__file__).with_name('preflight.json').read_text())
    archive_path = Path(preflight['backup'])
    assert sha(archive_path) == preflight['backup_sha256'], 'Backup SHA-256 mismatch'
    records = json.loads(archive_path.with_name('snapshot_inventory.json').read_text())
    if shutil.disk_usage(ROOT).free < sum(r['size'] for r in records if r['kind']=='file') + 1024**3:
        raise ValueError('Insufficient space for staging and 1 GiB reserve')
    # Validate every member before creating or writing the restore tree.
    with tarfile.open(archive_path) as archive:
        for r in records:
            p = Path(r['path'])
            assert not p.is_absolute() and '..' not in p.parts
            assert r['kind'] in {'file', 'directory'}
            if r['kind']=='file':
                assert digest(archive.extractfile(r['path'])) == r['sha256']
        target.mkdir(parents=True)
        for r in records:
            path = target / r['path']
            if r['kind']=='directory':
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream:
                    shutil.copyfileobj(archive.extractfile(r['path']), stream)
                assert sha(path) == r['sha256']
            os.chmod(path, r['mode'])
    print(json.dumps(verify_tree(target, records)))


if __name__ == '__main__':
    main()
