"""Restore the legacy image environment into a temporary tree and import its packages."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docs.environment_migration_audit.prepare import AUDIT, sha, write


def main():
    preflight = json.loads((AUDIT / 'preflight.json').read_text())
    archive_path = Path(preflight['backup'])
    assert sha(archive_path) == preflight['backup_sha256']
    records = [r for r in json.loads((AUDIT / 'before_inventory.json').read_text())
               if r['path'].startswith('bo_tool_anh_576x384/.venv/') or r['path']=='bo_tool_anh_576x384/.venv']
    with tempfile.TemporaryDirectory(prefix='btl_restore_legacy_venv_') as tmp, tarfile.open(archive_path) as archive:
        members = {m.name:m for m in archive.getmembers()}
        for record in records:
            relative = Path(record['path'])
            assert not relative.is_absolute() and '..' not in relative.parts
            target = Path(tmp) / relative
            if record['kind']=='directory':
                target.mkdir(parents=True, exist_ok=True)
            elif record['kind']=='symlink':
                target.symlink_to(record['target'])
                assert os.readlink(target) == record['target']
            else:
                target.write_bytes(archive.extractfile(members[record['path']]).read())
                os.chmod(target, record['mode'])
                os.utime(target, ns=(record['mtime_ns'],record['mtime_ns']))
                assert sha(target)==record['sha256'], record['path']
        python = Path(tmp) / 'bo_tool_anh_576x384/.venv/bin/python'
        result = subprocess.run([str(python), '-B', '-c',
             'import sys,json,numpy,PIL,onnxruntime,certifi;'
             'print(json.dumps(dict(prefix=sys.prefix,numpy=numpy.__version__,pillow=PIL.__version__,'
             'onnxruntime=onnxruntime.__version__,certifi=certifi.__version__,numpy_file=numpy.__file__,'
             'onnxruntime_file=onnxruntime.__file__)))'],
             capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=60)
        assert result.returncode==0,result.stderr
        packages=json.loads(result.stdout)
        assert Path(packages['prefix']).resolve()==python.parent.parent.resolve(), packages
        for name in ['numpy_file', 'onnxruntime_file']:
            assert Path(packages[name]).resolve().is_relative_to(python.parent.parent.resolve()), packages
        write('legacy_restore_verification.json',dict(verified=True,archive_sha256=preflight['backup_sha256'],
              restored_entries=len(records), restored_packages=packages, temporary_tree_removed_on_exit=True,
              note='Restored interpreter executed directly; original pip/activation absolute paths are historical. Recreate environments at final paths.'))
        print(json.dumps(dict(verified=True,restored_entries=len(records),restored_packages=packages)))


if __name__ == '__main__':
    main()
