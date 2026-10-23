#!/usr/bin/env python3
"""Verify the new queue results and confirm old/source files were preserved."""
import argparse
import csv
import json
from pathlib import Path
import sys

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import REGENERATED_OUTPUT_DIR, REGENERATED_SOURCE_INVENTORY, PROJECT_ROOT, resolve_project_reference

import numpy as np
from PIL import Image

from tools.segmentation import regenerate_masks as batch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=REGENERATED_OUTPUT_DIR)
    parser.add_argument('--previous-dir', type=Path, default=batch.PREVIOUS)
    parser.add_argument('--inventory', type=Path, default=REGENERATED_SOURCE_INVENTORY)
    parser.add_argument('--project-root', type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    output = args.output_dir
    inventory = json.loads(args.inventory.read_text(encoding='utf-8'))
    changed = []
    for relative, before in inventory.items():
        path = resolve_project_reference(relative, args.project_root)
        if not path.is_file():
            changed.append(relative)
            continue
        stat = path.stat()
        if stat.st_size != before['size'] or stat.st_mtime_ns != before['mtime_ns'] or batch.sha256(path) != before['sha256']:
            changed.append(relative)
    assert not changed, f'Protected files changed: {changed[:10]}'
    with (output / 'manifest.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {p.name for p in (args.previous_dir / 'overlays/needs_revision').iterdir() if p.is_file() and p.suffix.lower() == '.png'}
    assert len(rows) == len(expected) == len({r['filename'] for r in rows})
    assert {r['filename'] + '.png' for r in rows} == expected
    sheets = set()
    for row in rows:
        assert row['status'] == 'success', (row['filename'], row['error'])
        assert row['review_status'] == 'chua_duyet'
        assert (int(row['width']), int(row['height'])) == (576, 384)
        with Image.open(output / row['mask_path']) as image:
            assert image.format == 'PNG' and image.mode == 'L' and image.size == (576, 384)
            mask = np.asarray(image)
        assert set(np.unique(mask)).issubset({0, 255})
        pixels = int(np.count_nonzero(mask))
        assert pixels == int(row['mask_pixels'])
        assert int(row['total_pixels']) == mask.size
        assert abs(float(row['mask_ratio']) - pixels / mask.size) < 1e-12
        assert batch.sha256(resolve_project_reference(row['source_path'], args.project_root)) == row['source_sha256']
        with Image.open(resolve_project_reference(row['source_path'], args.project_root)) as image:
            source = image.convert('RGB')
        with Image.open(output / row['overlay_path']) as image:
            assert image.format == 'PNG' and image.size == (576, 384)
            assert np.array_equal(np.asarray(image), np.asarray(batch.overlay(source, mask)))
        for artifact in ('mask', 'overlay'):
            assert batch.sha256(output / row[artifact + '_path']) == row[artifact + '_sha256']
        for artifact in ('previous_mask', 'previous_overlay'):
            assert batch.sha256(resolve_project_reference(row[artifact + '_path'], args.project_root)) == row[artifact + '_sha256']
        with Image.open(resolve_project_reference(row['previous_mask_path'], args.project_root)) as image:
            previous = np.asarray(image)
        assert abs(float(row['changed_pixel_fraction']) - float(np.mean((mask != 0) != (previous != 0)))) < 1e-12
        sheets.add(row['quicklook_path'])
    for sheet in sheets:
        with Image.open(output / sheet) as image:
            image.verify()
    with (output / 'errors.csv').open(newline='') as stream:
        errors = list(csv.DictReader(stream))
    result = dict(images_verified=len(rows), mask_pngs=len(rows), overlay_pngs=len(rows),
                  contact_sheets=len(sheets), protected_files_unchanged=len(inventory),
                  logged_errors=len(errors), processing_size='576x384',
                  all_review_status='chua_duyet', verified_at=batch.now(), note=batch.NOTE)
    batch.write_json(output / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
