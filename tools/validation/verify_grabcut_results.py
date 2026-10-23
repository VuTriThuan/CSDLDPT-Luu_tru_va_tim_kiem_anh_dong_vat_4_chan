"""Audit generated artifacts and prove that the recorded source files are unchanged."""
import argparse
import csv
import json
from pathlib import Path
import sys

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import GRABCUT_SOURCE_INVENTORY

import numpy as np
from PIL import Image

from tools.segmentation import run_grabcut as gc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=gc.DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=gc.DEFAULT_OUTPUT)
    parser.add_argument('--inventory', type=Path, default=GRABCUT_SOURCE_INVENTORY)
    args = parser.parse_args(argv)
    source_dir, output = args.source_dir, args.output_dir
    with (output / 'manifest.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    source_files = {p.name for p in source_dir.iterdir() if p.is_file()}
    image_names = {name for name in source_files if Path(name).suffix.lower() in gc.EXTENSIONS}
    assert len(rows) == len(image_names), (len(rows), len(image_names))
    assert {row['filename'] for row in rows} == image_names
    assert len({row['filename'] for row in rows}) == len(rows)
    before = json.loads(args.inventory.read_text(encoding='utf-8'))
    assert set(before) == source_files, 'Source file list changed'
    for name, record in before.items():
        path = source_dir / name
        assert gc.sha256(path) == record['sha256'], f'Source content changed: {name}'
        assert path.stat().st_size == record['size'], f'Source size changed: {name}'
        assert path.stat().st_mtime_ns == record['mtime_ns'], f'Source mtime changed: {name}'
    quicklooks = set()
    for row in rows:
        assert row['status'] == 'success', (row['filename'], row['status'], row['error'])
        assert row['review_status'] == 'chua_duyet'
        width, height = int(row['width']), int(row['height'])
        assert (width, height) == (576, 384)
        with Image.open(output / row['mask_path']) as image:
            assert image.format == 'PNG' and image.mode == 'L'
            mask = np.asarray(image)
            assert image.size == (width, height)
            assert set(np.unique(mask)).issubset({0, 255})
            pixels = int(np.count_nonzero(mask))
        assert int(row['mask_pixels']) == pixels
        assert int(row['total_pixels']) == width * height
        assert abs(float(row['mask_ratio']) - pixels / (width * height)) < 1e-12
        source, sw, sh = gc.read_image(source_dir / row['filename'])
        assert (sw, sh) == (int(row['source_width']), int(row['source_height']))
        with Image.open(output / row['overlay_path']) as image:
            assert image.format == 'PNG' and image.size == (width, height)
            assert np.array_equal(np.asarray(image), gc.make_overlay(source, mask)), row['filename']
        for artifact in ('mask', 'overlay'):
            assert gc.sha256(output / row[f'{artifact}_path']) == row[f'{artifact}_sha256']
        quicklooks.add(row['quicklook_path'])
    for path in quicklooks:
        with Image.open(output / path) as image:
            image.verify()
    with (output / 'errors.csv').open(newline='') as stream:
        errors = list(csv.DictReader(stream))
    result = dict(images_verified=len(rows), masks_verified=len(rows), overlays_verified=len(rows),
                  quicklooks_verified=len(quicklooks), source_files_unchanged=len(before),
                  source_image_files_unchanged=len(image_names), logged_errors=len(errors),
                  all_review_status='chua_duyet', processing_size='576x384', verified_at=gc.now(), note=gc.NOTE)
    gc.write_json(output / 'verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
