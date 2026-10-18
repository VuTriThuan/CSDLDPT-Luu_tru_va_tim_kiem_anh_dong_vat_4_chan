"""Remove only the replaced legacy environment after verification gates pass."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.environment_migration_audit.prepare import AUDIT,sha,write


def main():
    pre=json.loads((AUDIT/'preflight.json').read_text())
    assert pre['verified'] and sha(Path(pre['backup']))==pre['backup_sha256']
    for name in ['smoke_checks.json','legacy_restore_verification.json','image_inference_check.json']:
        assert json.loads((AUDIT/name).read_text())['verified'],name
    for name,count in [('image_tests.log',24),('validation_tests.log',14)]:
        log=(AUDIT/name).read_text()
        assert f'Ran {count} tests' in log and log.rstrip().endswith('OK'),name
    for name in ['image_pip_check.log','shared_pip_check.log']:
        assert 'No broken requirements found.' in (AUDIT/name).read_text()
    before=json.loads((AUDIT/'image_tools_before.json').read_text())
    after=json.loads((AUDIT/'image_tools_after.json').read_text())
    assert before['python']==after['python']=='3.10.11'
    assert {k.lower():v['version'] for k,v in before['packages'].items()} == {k.lower():v['version'] for k,v in after['packages'].items()}
    old=ROOT/'bo_tool_anh_576x384/.venv'
    assert old.is_dir() and not old.is_symlink()
    new=ROOT/'.venv-image-tools'
    assert new.is_dir() and not new.is_symlink()
    assert Path(after['prefix'])==new
    for relative in ['pyvenv.cfg','bin/pip','bin/activate','bin/activate.csh','bin/activate.fish']:
        content=(new/relative).read_text()
        assert str(old) not in content and str(ROOT/'.venv/bin') not in content
    records=[r for r in json.loads((AUDIT/'before_inventory.json').read_text())
             if r['path']=='bo_tool_anh_576x384/.venv' or r['path'].startswith('bo_tool_anh_576x384/.venv/')]
    assert {str(p.relative_to(ROOT)) for p in [old,*old.rglob('*')]}=={r['path'] for r in records}
    for record in records:
        path=ROOT/record['path']
        if record['kind']=='file':
            assert sha(path)==record['sha256'],path
        elif record['kind']=='symlink':
            assert os.readlink(path)==record['target'],path
    # Guard against an active crop/review process using the real image dataset.
    with (ROOT/'data/cropped_images_576x384/.tool_anh.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        shutil.rmtree(old)
    assert not old.exists()
    write('legacy_environment_removal.json',dict(removed=True,path=str(old),entries=len(records),
          replacement=str(new),replacement_verified_before_removal=True,
          archive_verified_before_removal=True,legacy_environment_restored_and_imported_before_removal=True,
          shared_environment_removed_or_recreated=False,backup=pre['backup'],backup_sha256=pre['backup_sha256']))
    print((AUDIT/'legacy_environment_removal.json').read_text())


if __name__=='__main__':
    main()
