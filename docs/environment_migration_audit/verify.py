"""Check pinned packages, unchanged shared environment and protected real artifacts."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.environment_migration_audit.prepare import AUDIT,sha,write


def main():
    before=json.loads((AUDIT/'before_inventory.json').read_text())
    shared=[r for r in before if r['path']=='.venv' or r['path'].startswith('.venv/')]
    for record in shared:
        path=ROOT/record['path']
        if record['kind']=='file':
            assert sha(path)==record['sha256'],path
            assert path.stat().st_mtime_ns==record['mtime_ns'],path
            assert path.stat().st_mode&0o7777==record['mode'],path
        elif record['kind']=='symlink':
            assert os.readlink(path)==record['target']
    assert {str(p.relative_to(ROOT)) for p in [ROOT/'.venv',*(ROOT/'.venv').rglob('*')]}=={r['path'] for r in shared}
    protected=json.loads((AUDIT/'protected_before.json').read_text())
    for record in protected:
        path=ROOT/record['path']
        assert sha(path)==record['sha256'] and path.stat().st_size==record['size'],path
        assert path.stat().st_mtime_ns==record['mtime_ns'],path
    actual={str(p.relative_to(ROOT)) for start in ['data','outputs/segmentation','outputs/inventory']
            for p in (ROOT/start).rglob('*') if p.is_file()}
    assert actual=={r['path'] for r in protected}
    locks=[]
    for req,metadata,environment in [('requirements.txt','root_after.json','.venv'),
                                    ('requirements_image_tools.txt','image_tools_after.json','.venv-image-tools')]:
        installed=json.loads((AUDIT/metadata).read_text())
        packages={k.lower().replace('_','-'):v['version'] for k,v in installed['packages'].items()}
        count=0
        for line in (ROOT/req).read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            name,version=line.split('==')
            assert packages[name.lower().replace('_','-')]==version,(req,line)
            count+=1
        assert count==11
        assert installed['python']=='3.10.11' and Path(installed['prefix'])==ROOT/environment
        assert Path(installed['resolved_executable']).is_relative_to(Path(installed['base_prefix']))
        locks.append(dict(environment=environment,requirements=req,runtime_pins_verified=count))
    seals={}
    for name in ['source_migration_audit','documentation_migration_audit','data_migration_audit','results_migration_audit']:
        base=ROOT/'docs'/name
        rows=(base/'artifacts.sha256').read_text().splitlines()
        for row in rows:
            expected,filename=row.split('  ',1)
            assert sha(base/filename)==expected,(name,filename)
        seals[name]=len(rows)
    for record in before:
        if record['path'].startswith('docs/reports/') and record['kind']=='file':
            assert sha(ROOT/record['path'])==record['sha256']
    assert not (ROOT/'bo_tool_anh_576x384/.venv').exists()
    new=[]
    base=ROOT/'.venv-image-tools'
    for p in [base,*sorted(base.rglob('*'))]:
        stat=p.lstat()
        record=dict(path=str(p.relative_to(ROOT)),kind='symlink' if p.is_symlink() else 'directory' if p.is_dir() else 'file',
                    size=stat.st_size,mode=stat.st_mode&0o7777,mtime_ns=stat.st_mtime_ns)
        if record['kind']=='file':
            record['sha256']=sha(p)
        elif record['kind']=='symlink':
            record['target']=os.readlink(p)
        new.append(record)
    write('new_environment_inventory.json',new)
    result=dict(verified=True,shared_environment_entries_unchanged=len(shared),
                protected_data_result_and_state_files_unchanged=len(protected),requirements=locks,
                older_audit_seals_verified=seals,analysis_reports_unchanged=True,
                legacy_environment_removed=True,new_environment_entries=len(new),real_data_processed=False)
    write('verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
