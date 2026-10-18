"""Recheck both runtime inventories, pinned versions and pip consistency."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import AUDIT,sha,write


def main():
    environments=[]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_NO_CACHE_DIR='1')
    for folder,req,tag in [('.venv','requirements.txt','shared'),('.venv-image-tools','requirements_image_tools.txt','image_tools')]:
        python=ROOT/folder/'bin/python'
        inspected=subprocess.run([str(python),'-B',str(ROOT/'docs/environment_migration_audit/inspect_environment.py')],capture_output=True,text=True,env=env,check=True)
        metadata=json.loads(inspected.stdout)
        assert metadata['python']=='3.10.11' and Path(metadata['prefix'])==ROOT/folder
        packages={k.lower():v['version'] for k,v in metadata['packages'].items()}
        for line in (ROOT/req).read_text().splitlines():
            if line and not line.startswith('#'):
                name,version=line.split('==')
                assert packages[name.lower()]==version
        checked=subprocess.run([str(python),'-B','-m','pip','check'],capture_output=True,text=True,env=env)
        assert checked.returncode==0 and 'No broken requirements found.' in checked.stdout
        (AUDIT/(tag+'_pip_check.log')).write_text(checked.stdout+checked.stderr)
        write(tag+'_environment.json',metadata)
        environments.append(dict(path=folder,python=metadata['python'],runtime_requirements=req,pip_check=True))
    inventory=json.loads((ROOT/'docs/environment_migration_audit/new_environment_inventory.json').read_text())
    for record in inventory:
        path=ROOT/record['path']
        if record['kind']=='file':
            assert sha(path)==record['sha256'],path
        elif record['kind']=='symlink':
            assert os.readlink(path)==record['target']
        else:
            assert path.is_dir()
    assert not (ROOT/'bo_tool_anh_576x384/.venv').exists()
    write('environment_verification.json',dict(verified=True,environments=environments,
              recreated_image_environment_entries_verified=len(inventory),shared_environment_matches_step_1='baseline_accounting.json',
              legacy_image_environment_absent=True))
    print(json.dumps(dict(verified=True,environments=environments,new_environment_entries=len(inventory))))


if __name__=='__main__':
    main()
