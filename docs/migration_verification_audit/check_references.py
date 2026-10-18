"""Classify legacy path matches; reject obsolete paths in current CLI instructions."""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from docs.migration_verification_audit.prepare import write

PATTERN=r'bo_tool_anh_576x384|anh-chua-loc|anh-da-cat-576x384|reports/yeu_cau_2|grabcut_output|mask_moi_can_sua|overlays/(đạt|cần sửa|làm lại)|\.venv-windows|cat_tu_dong\.py|doi_ten_anh\.py|duyet_anh\.py|chinh_mask\.py|dong_bo_overlays\.py'


def main():
    command=['rg','--json','--hidden','-n','-e',PATTERN]
    for pattern in ['*.py','*.md','*.json','*.csv','*.log','*.txt']:
        command.extend(['--glob',pattern])
    command.extend(['--glob','!docs/*_audit/**'])
    scopes=['tools','tests','README.md','docs','data','outputs/segmentation','outputs/inventory','bo_tool_anh_576x384','reports']
    command.extend(scopes)
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode in [0,1],result.stderr
    matches=[]
    errors=[]
    for line in result.stdout.splitlines():
        event=json.loads(line)
        if event['type']!='match':
            continue
        data=event['data']
        path=data['path']['text']
        text=data['lines']['text'].strip()
        if path=='tools/project_paths.py':
            category='scoped_legacy_alias_or_constant'
        elif path=='tools/segmentation/sync_overlays.py':
            category='legacy_manual_edit_record_reader'
        elif path.startswith('tools/'):
            category='unexpected_production_reference'
        elif path.startswith('tests/'):
            category='compatibility_test_fixture_or_archive_mapping'
        elif path=='README.md' and 'bo_tool_anh_576x384/' in text and 'lịch sử' in text:
            category='retained_legacy_directory'
        elif path.startswith('docs/guides/'):
            if re.match(r'^(python\S* |py |\.venv|bo_tool_anh_576x384.*python)',text):
                category='obsolete_current_guide_command'
            else:
                category='explicit_historical_guide_context'
        elif path.startswith('docs/reports/'):
            category='historical_analysis_reference'
        elif path.startswith('docs/'):
            category='phase_record_or_restore_instructions'
        elif path in ['data/cropped_images_576x384/_cat_tu_dong.json','outputs/segmentation/grabcut/manifest.csv']:
            category='obsolete_active_state_or_manifest'
        elif path.startswith(('data/','outputs/segmentation/','outputs/inventory/')):
            category='immutable_historical_state_config_inventory_log_or_edit_record'
        else:
            category='legacy_material'
        row=dict(path=path,line=data['line_number'],category=category,text=text[:800])
        matches.append(row)
        if category in {'unexpected_production_reference','obsolete_current_guide_command','obsolete_active_state_or_manifest'}:
            errors.append(row)
    write('legacy_path_matches.json',matches)
    counts=Counter(r['category'] for r in matches)
    write('reference_verification.json',dict(verified=not errors,legacy_matching_lines=len(matches),categories=dict(counts),
        errors=errors,scan_roots=scopes,excluded=['.git/','third-party virtualenv packages','binary images and bytecode','backup archives','sealed historical audit directories'],
        excluded_material_verified_by='baseline_accounting.json, backup_verification.json and environment metadata checks'))
    assert not errors,errors
    print(json.dumps(dict(verified=True,legacy_matching_lines=len(matches),categories=dict(counts)),ensure_ascii=False))


if __name__=='__main__':
    main()
