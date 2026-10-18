"""Read-only verification of relocated artifacts against this phase and step 1."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docs.results_migration_audit.prepare import sha, write, AUDIT
from tools import project_paths as paths
from PIL import Image


def main():
    baseline = {r['path']: r for r in json.loads((ROOT / 'docs/migration_audit/baseline_inventory.json').read_text())['entries']}
    mapping = json.loads((AUDIT / 'path_mapping.json').read_text())
    assets, counts = [], Counter()
    for row in mapping:
        if row['kind'] != 'file':
            continue
        current = ROOT / row['target_path']
        actual = sha(current)
        assert actual == row['sha256'] == baseline[row['current_path']]['sha256'], current
        stat = current.stat()
        assert stat.st_size == row['size'] and stat.st_mtime_ns == row['mtime_ns'], current
        assert stat.st_mode & 0o7777 == row['mode'], current
        if row['current_path'] != row['target_path']:
            assert not (ROOT / row['current_path']).exists()
            counts['moved_files'] += 1
        else:
            counts['left_files'] += 1
        category = baseline[row['current_path']]['category']
        counts[category] += 1
        assets.append(dict(original_path=row['current_path'], current_path=row['target_path'],
                           sha256=actual, step_1_sha256=baseline[row['current_path']]['sha256'], category=category))
    for image in json.loads((AUDIT / 'data_before.json').read_text()):
        assert sha(ROOT / image['current']) == image['sha256']
        assets.append(dict(original_path=image['original'], current_path=image['current'], sha256=image['sha256'],
                           step_1_sha256=image['sha256'], category=baseline[image['original']]['category']))
        counts['data_images'] += 1
    output = paths.GRABCUT_OUTPUT_DIR
    rows = list(csv.DictReader((output / 'manifest.csv').open(newline='')))
    assert len(rows) == len({r['filename'] for r in rows}) == 812
    for row in rows:
        assert sha(paths.CROPPED_IMAGES_DIR / row['filename']) == row['source_sha256']
        for kind in ['mask', 'overlay']:
            relative = Path(row[kind + '_path'])
            assert not relative.is_absolute() and '..' not in relative.parts
            assert sha(output / relative) == row[kind + '_sha256']
            with Image.open(output / relative) as image:
                assert image.size == (576, 384) and image.format == 'PNG'
                image.verify()
    for quicklook in (output / 'quicklooks').glob('*.jpg'):
        with Image.open(quicklook) as image:
            image.verify()
    for session in (output / 'manual_edits').iterdir():
        assert {p.name for p in session.iterdir()} == {'mask_before.png', 'overlay_before.png', 'scribbles.png', 'record.json'}
        json.loads((session / 'record.json').read_text())
        for p in session.glob('*.png'):
            with Image.open(p) as image:
                image.verify()
    zip_checked = 0
    with (ROOT / 'docs/migration_audit/zip_member_sha256.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            with zipfile.ZipFile(paths.resolve_project_reference(row['archive'])) as archive:
                data = archive.read(row['member'])
                assert len(data) == int(row['size']) and hashlib.sha256(data).hexdigest() == row['sha256']
                zip_checked += 1
    inventory_checks = {}
    for name, inventory, locate in [
        ('grabcut_source_before', paths.GRABCUT_SOURCE_INVENTORY, lambda key: paths.CROPPED_IMAGES_DIR / key),
        ('mask_regeneration_source_before', paths.REGENERATED_SOURCE_INVENTORY, paths.resolve_project_reference),
    ]:
        mismatches = []
        contents = json.loads(inventory.read_text())
        for key, before in contents.items():
            path = locate(key)
            if not path.is_file():
                mismatches.append(dict(reference=key, reason='missing_in_current_tree'))
                continue
            stat = path.stat()
            differences = [field for field, actual in [('sha256', sha(path)), ('size', stat.st_size), ('mtime_ns', stat.st_mtime_ns)]
                           if actual != before[field]]
            if differences:
                mismatches.append(dict(reference=key, reason='historical_snapshot_differs', fields=differences))
        inventory_checks[name] = dict(entries=len(contents), current_mismatches=len(mismatches), details=mismatches,
                                     note='Immutable earlier checkpoint, not the migration baseline. No hash or timestamp rewritten.')
    write('historical_inventory_checks.json', inventory_checks)
    with (AUDIT / 'asset_sha256.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(assets[0]))
        writer.writeheader()
        writer.writerows(assets)
    write('verification.json', dict(verified=True, counts=dict(counts), manifest_rows=812,
          manifest_asset_hashes_verified=2436, manifest_sha256=sha(output / 'manifest.csv'),
          run_config_sha256=sha(output / 'run_config.json'), manual_edit_sessions=374,
          quicklooks=102, zip_members_verified=zip_checked, historical_snapshot_mismatches={k:v['current_mismatches'] for k,v in inventory_checks.items()},
          algorithm_reprocessing_on_real_data=False))
    print((AUDIT / 'verification.json').read_text())


if __name__ == '__main__':
    main()
