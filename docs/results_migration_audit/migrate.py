"""Apply only the authorized result/inventory moves after snapshot verification."""
import csv
import fcntl
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docs.results_migration_audit.prepare import sha, write, AUDIT
from tools.project_paths import LEGACY_RESULT_PATHS, LEGACY_OVERLAY_CATEGORIES


def destination(name):
    relative = Path(name)
    for before, after in LEGACY_RESULT_PATHS.items():
        try:
            return str(Path(after) / relative.relative_to(before))
        except ValueError:
            pass
    return name


def main():
    preflight = json.loads((AUDIT / 'preflight.json').read_text())
    assert preflight['verified'] and sha(Path(preflight['backup'])) == preflight['backup_sha256']
    before = [r for r in json.loads((AUDIT / 'before_inventory.json').read_text())
              if r['path'] == 'reports' or r['path'].startswith('reports/')]
    mappings = [dict(current_path=r['path'], target_path=destination(r['path']), **{k: v for k, v in r.items() if k != 'path'})
                for r in before]
    for row in mappings:
        if row['kind'] == 'file':
            assert sha(ROOT / row['current_path']) == row['sha256'], 'Concurrent modification: ' + row['current_path']
    actual = {str(p.relative_to(ROOT)) for p in (ROOT / 'reports').rglob('*') if p.is_file()}
    assert actual == {r['current_path'] for r in mappings if r['kind'] == 'file'}
    for old, new in LEGACY_RESULT_PATHS.items():
        source, target = ROOT / old, ROOT / new
        if not source.exists():
            assert old.endswith('/mask_moi_can_sua'), old
            continue
        assert not target.exists(), target
    old_result = ROOT / 'reports/yeu_cau_2/grabcut_output'
    new_result = ROOT / 'outputs/segmentation/grabcut'
    original_manifest = (old_result / 'manifest.csv').read_bytes()
    # All live overlays at this phase are flat. Refuse unexpected category state
    # rather than silently rewriting history or inventing a new classification.
    categories = [p for p in (old_result / 'overlays').iterdir() if p.is_dir()]
    assert not categories, 'Reinspect category directories and their manifest rows before moving'
    rows = list(csv.DictReader(io.StringIO(original_manifest.decode())))
    assert all(Path(r['overlay_path']).parent == Path('overlays') for r in rows)
    write('path_mapping.json', mappings)
    with (AUDIT / 'path_mapping.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['current_path', 'target_path', 'kind', 'sha256'])
        writer.writeheader()
        writer.writerows({k: r.get(k, '') for k in writer.fieldnames} for r in mappings)
    for old, new in LEGACY_RESULT_PATHS.items():
        source, target = ROOT / old, ROOT / new
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
    assert (new_result / 'manifest.csv').read_bytes() == original_manifest
    write('manifest_conversion.json', dict(rows=len(rows), converted_rows=0,
          before_sha256=sha(new_result / 'manifest.csv'), after_sha256=sha(new_result / 'manifest.csv'),
          reason='All overlay paths already relative and flat; moving the entire result tree needs no CSV rewrite.',
          category_mapping=LEGACY_OVERLAY_CATEGORIES, live_category_directories_before=[]))
    print(json.dumps(dict(moved_files=sum(r['kind']=='file' and r['current_path']!=r['target_path'] for r in mappings),
                         left_files=[r['current_path'] for r in mappings if r['kind']=='file' and r['current_path']==r['target_path']],
                         manifest_converted_rows=0), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    with (ROOT / 'reports/yeu_cau_2/grabcut_output/.run.lock').open('rb') as result_lock, \
            (ROOT / 'data/cropped_images_576x384/.tool_anh.lock').open('rb') as data_lock:
        for lock in [result_lock, data_lock]:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
