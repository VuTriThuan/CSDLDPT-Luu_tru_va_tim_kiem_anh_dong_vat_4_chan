"""Generate candidate masks for manual review; never extract feature vectors.

python3 tools/segmentation/run_grabcut.py --limit 8
python3 tools/segmentation/run_grabcut.py --all --resume
Only filenames/CSV metadata are retained; images are decoded one at a time.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from datetime import datetime, timezone

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import PROJECT_ROOT, DATA_DIR, GRABCUT_OUTPUT_DIR

import cv2
import numpy as np
from PIL import Image, ImageDraw, __version__ as pillow_version

ROOT = PROJECT_ROOT
DEFAULT_INPUT = DATA_DIR / 'cropped_images_576x384'
DEFAULT_OUTPUT = GRABCUT_OUTPUT_DIR
SAMPLE_NAMES = [
    'Equus_asinus_0587.jpg', 'equus-quagga_0779.jpg', 'cervidae_0568.jpg',
    'Bos_taurus_1254.jpg', 'Canis_familiaris_0052.jpg',
    'Canis_lupus_familiaris_doberman_0953.jpg', 'Camelus_bactrianus_0303.jpg',
    'ursus-americanus_0649.jpg',
]
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
FIELDS = [
    'filename', 'source_sha256', 'mask_path', 'overlay_path',
    'source_width', 'source_height', 'width', 'height', 'total_pixels',
    'mask_pixels', 'mask_ratio', 'status', 'review_status', 'review_result', 'suspicious',
    'review_flags', 'component_count', 'bbox_fill_ratio', 'init_border_ratio',
    'quicklook_path', 'mask_sha256', 'overlay_sha256', 'error', 'processed_at',
]
ERROR_FIELDS = ['timestamp', 'filename', 'stage', 'error']
NOTE = (
    'Candidate masks require human review. mask_ratio is foreground pixel fraction, '
    'not segmentation accuracy. No ground truth evaluation or 400-dimensional '
    'feature extraction is performed (feature implementation belongs to requirement 3).'
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def atomic_text(path, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                     dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_csv(path, rows, fields=FIELDS):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    atomic_text(path, stream.getvalue())


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def save_image(path, image):
    # Temp files stay in the output directory, never beside source images.
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=path.suffix, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        image.save(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def create_foreground_mask(image, iterations=5, seed=0):
    """Reference rectangle GrabCut + morphology, without hidden fallbacks.

    Based on create_foreground_mask in the report's feature_extractors.py.
    Errors propagate; an empty mask stays empty for review. The reference's
    margin (10 px), kernel (5x5), opening/closing (2 each) use processing pixels.
    """
    height, width = image.shape[:2]
    if min(height, width) <= 20:
        raise ValueError('Image must be larger than 20 pixels on both axes')
    labels = np.zeros((height, width), dtype=np.uint8)
    cv2.setRNGSeed(seed)
    cv2.grabCut(image, labels, (10, 10, width - 20, height - 20),
                np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64),
                iterations, cv2.GC_INIT_WITH_RECT)
    mask = np.where((labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD),
                    255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)


def read_image(path, max_side=0):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is None:
        raise ValueError('Cannot decode image')
    height, width = image.shape[:2]
    if max_side and max(height, width) > max_side:
        scale = max_side / max(height, width)
        image = cv2.resize(image, (max(1, round(width * scale)),
                                   max(1, round(height * scale))),
                           interpolation=cv2.INTER_AREA)
    return image, width, height


def mask_statistics(mask):
    pixels = int(np.count_nonzero(mask))
    ratio = pixels / mask.size
    flags = []
    if pixels == 0:
        flags.append('empty_mask')
    if ratio < 0.05:
        flags.append('area_below_5pct')
    if ratio > 0.85:
        flags.append('area_above_85pct')
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    significant = int(np.count_nonzero(stats[1:, cv2.CC_STAT_AREA] >= mask.size * 0.001))
    if significant >= 8:
        flags.append('many_components')
    bbox_fill = border_ratio = 0.0
    if pixels:
        _, _, width, height = cv2.boundingRect(mask)
        bbox_fill = pixels / (width * height)
        if bbox_fill > 0.95:
            flags.append('almost_filled_rectangle')
        # Image edges are forced background; inspect the init rectangle instead.
        ring = np.zeros_like(mask, dtype=bool)
        ring[10:13, 10:-10] = True
        ring[-13:-10, 10:-10] = True
        ring[10:-10, 10:13] = True
        ring[10:-10, -13:-10] = True
        border_ratio = float(np.count_nonzero(mask[ring])) / max(1, np.count_nonzero(ring))
        if border_ratio > 0.15:
            flags.append('near_initial_rectangle_border')
    return dict(mask_pixels=pixels, mask_ratio=ratio, total_pixels=mask.size,
                suspicious='yes' if flags else 'no', review_flags=';'.join(flags),
                component_count=count - 1, bbox_fill_ratio=bbox_fill,
                init_border_ratio=border_ratio)


def make_overlay(image, mask):
    overlay = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    background = mask == 0
    overlay[background] = (0.35 * overlay[background] +
                           0.65 * np.array([255, 0, 0])).astype(np.uint8)
    return overlay


def new_row(name, index, batch_size):
    row = dict.fromkeys(FIELDS, '')
    row.update(filename=name, status='pending', review_status='chua_duyet', review_result='',
               mask_path=f'masks/{name}.png', overlay_path=f'overlays/{name}.png',
               quicklook_path=f'quicklooks/batch_{index // batch_size + 1:03d}.jpg')
    return row


def reusable(row, source, output):
    """Reuse committed outputs only when both source and artifacts still match."""
    if row.get('status') != 'success' or row.get('source_sha256') != sha256(source):
        return False
    for field in ('mask', 'overlay'):
        relative = Path(row.get(f'{field}_path', ''))
        if relative.is_absolute() or '..' in relative.parts:
            return False
        artifact = output / relative
        if artifact.is_symlink() or not artifact.is_file():
            return False
        if row.get(f'{field}_sha256') != sha256(artifact):
            return False
    return True


def draw_fitted(canvas, path, box):
    with Image.open(path) as image:
        image = image.convert('RGB')
        image.thumbnail((box[2], box[3]), Image.Resampling.LANCZOS)
        canvas.paste(image, (box[0] + (box[2] - image.width) // 2,
                            box[1] + (box[3] - image.height) // 2))


def quicklook(output, source, rows):
    # One bounded batch canvas plus one decoded thumbnail.
    cell_w, cell_h, row_h = 288, 192, 254
    canvas = Image.new('RGB', (cell_w * 3, 30 + row_h * len(rows)), 'white')
    draw = ImageDraw.Draw(canvas)
    draw.text((5, 5), 'SOURCE | MASK | OVERLAY (red = background); ALL REQUIRE REVIEW', fill='black')
    for index, row in enumerate(rows):
        y = 30 + row_h * index
        if row['status'] == 'success':
            for column, path in enumerate((source / row['filename'],
                                            output / row['mask_path'],
                                            output / row['overlay_path'])):
                draw_fitted(canvas, path, (column * cell_w, y, cell_w, cell_h))
        color = '#b00020' if row['suspicious'] == 'yes' or row['status'] != 'success' else 'black'
        draw.text((5, y + cell_h + 2), row['filename'], fill=color)
        draw.text((5, y + cell_h + 18),
                  f'{row["width"]}x{row["height"]} | status={row["status"]} | '
                  f'ratio={float(row["mask_ratio"]):.4f}' if row['mask_ratio'] != '' else row['status'],
                  fill=color)
        draw.text((5, y + cell_h + 34),
                  (row['review_flags'] or row['error'] or 'No heuristic flags; manual review still required')[:130],
                  fill=color)
        draw.text((5, y + cell_h + 48), f'review={row["review_status"]}', fill=color)
    save_image(output / rows[0]['quicklook_path'], canvas)


def progress(done, total, success, failed, skipped, start):
    fraction = done / total if total else 1
    bar = '#' * int(fraction * 25) + '-' * (25 - int(fraction * 25))
    print(f'\r[{bar}] {done}/{total} success={success} failed={failed} '
          f'resumed={skipped} elapsed={time.monotonic() - start:.0f}s',
          end='', file=sys.stderr, flush=True)


def log_error(output, filename, stage, error):
    with (output / 'errors.csv').open('a', encoding='utf-8', newline='') as stream:
        csv.DictWriter(stream, fieldnames=ERROR_FIELDS).writerow(
            dict(timestamp=now(), filename=filename, stage=stage, error=str(error)))
        stream.flush()
        os.fsync(stream.fileno())


def run(args):
    source, output = args.input_dir.resolve(), args.output_dir.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Input and output must be separate, non-nested directories')
    if not source.is_dir():
        raise ValueError(f'Input directory does not exist: {source}')
    found = sorted(path.name for path in source.iterdir()
                   if path.is_file() and path.suffix.lower() in EXTENSIONS)
    # --limit 8 reproduces exactly the eight historical samples when present.
    names = [name for name in SAMPLE_NAMES if name in found]
    names += [name for name in found if name not in SAMPLE_NAMES]
    if not args.all:
        names = names[:args.limit]
    if not names:
        raise ValueError('No input images selected')
    output.mkdir(parents=True, exist_ok=True)
    # flock releases on interruption/kill; no stale lock to remove on resume.
    with (output / '.run.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another process is using this output directory') from exc
        return run_locked(args, source, output, names, len(found))


def run_locked(args, source, output, names, discovered):
    config = dict(schema_version=1, input_dir=str(source), max_side=args.max_side,
                  iterations=args.iterations, seed=args.seed, margin=10,
                  morphology_kernel=[5, 5], morphology_iterations=2,
                  opencv=cv2.__version__, numpy=np.__version__, pillow=pillow_version,
                  script_sha256=sha256(Path(__file__)), batch_size=args.batch_size,
                  resize='native' if not args.max_side else 'aspect_preserving_downscale',
                  note=NOTE)
    config_path = output / 'run_config.json'
    manifest_path = output / 'manifest.csv'
    previous = {}
    existing = [path for path in output.iterdir() if path.name != '.run.lock']
    if existing and not args.resume:
        raise ValueError('Output is not empty. Use --resume or choose a new --output-dir')
    if config_path.exists():
        if json.loads(config_path.read_text(encoding='utf-8')) != config:
            raise ValueError('Resume configuration/code differs. Choose a new --output-dir')
    elif existing:
        raise ValueError('Missing run_config.json; use a new --output-dir')
    if manifest_path.exists():
        with manifest_path.open(encoding='utf-8', newline='') as stream:
            previous = {row['filename']: row for row in csv.DictReader(stream)}
        if not set(previous).issubset(names):
            raise ValueError('Selection would discard previous manifest rows; use --all --resume')
    # Prevent output symlinks from redirecting writes into source/other directories.
    for directory in ('masks', 'overlays', 'quicklooks'):
        path = output / directory
        if path.is_symlink():
            raise ValueError(f'Output subdirectory must not be a symlink: {path}')
        path.mkdir(exist_ok=True)
    for name in ('manifest.csv', 'run_config.json', 'errors.csv', 'summary.json', 'review_priority.csv'):
        if (output / name).is_symlink():
            raise ValueError(f'Output metadata must not be a symlink: {name}')
    write_json(config_path, config)
    if not (output / 'errors.csv').exists():
        write_csv(output / 'errors.csv', [], ERROR_FIELDS)
    rows = []
    for index, name in enumerate(names):
        row = new_row(name, index, args.batch_size)
        if name in previous:
            row.update(previous[name])
            # Regenerate derived paths, retaining review status for intact outputs.
            for field in ('mask_path', 'overlay_path', 'quicklook_path'):
                row[field] = new_row(name, index, args.batch_size)[field]
        rows.append(row)
    write_csv(manifest_path, rows)
    start = time.monotonic()
    attempted = succeeded = failed = skipped = 0
    interrupted = False
    quicklook_failed = 0
    try:
        for index, row in enumerate(rows):
            stage = 'resume_validation'
            try:
                if args.resume and reusable(row, source / row['filename'], output):
                    skipped += 1
                else:
                    attempted += 1
                    row.update(new_row(row['filename'], index, args.batch_size))
                    stage = 'decode'
                    image, sw, sh = read_image(source / row['filename'], args.max_side)
                    row.update(source_width=sw, source_height=sh,
                               width=image.shape[1], height=image.shape[0],
                               source_sha256=sha256(source / row['filename']))
                    stage = 'grabcut'
                    mask = create_foreground_mask(image, args.iterations, args.seed)
                    row.update(mask_statistics(mask))
                    stage = 'write_artifacts'
                    save_image(output / row['mask_path'], Image.fromarray(mask))
                    save_image(output / row['overlay_path'], Image.fromarray(make_overlay(image, mask)))
                    row.update(status='success', processed_at=now(),
                               mask_sha256=sha256(output / row['mask_path']),
                               overlay_sha256=sha256(output / row['overlay_path']))
                    succeeded += 1
                    del image, mask
            except Exception as exc:
                failed += 1
                row.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                           processed_at=now(), review_status='chua_duyet', review_result='')
                log_error(output, row['filename'], stage, row['error'])
            # Commit every image, including failures. SIGKILL can lose at most one row.
            write_csv(manifest_path, rows)
            progress(index + 1, len(rows), succeeded + skipped, failed, skipped, start)
            if (index + 1) % args.batch_size == 0 or index + 1 == len(rows):
                batch_start = index - index % args.batch_size
                try:
                    quicklook(output, source, rows[batch_start:index + 1])
                except Exception as exc:
                    quicklook_failed += 1
                    log_error(output, row['quicklook_path'], 'quicklook', f'{type(exc).__name__}: {exc}')
    except KeyboardInterrupt:
        interrupted = True
        print('\nInterrupted; committed rows can be resumed.', file=sys.stderr)
    finally:
        write_csv(manifest_path, rows)
        priority = sorted((row for row in rows if row['suspicious'] == 'yes' or row['status'] == 'failed'),
                          key=lambda row: (row['status'] != 'failed', -len(row['review_flags'].split(';')), row['filename']))
        write_csv(output / 'review_priority.csv', priority)
        summary = dict(selected=len(rows), discovered=discovered,
                       success=sum(row['status'] == 'success' for row in rows),
                       failed=sum(row['status'] == 'failed' for row in rows),
                       pending=sum(row['status'] == 'pending' for row in rows),
                       attempted_this_run=attempted, succeeded_this_run=succeeded,
                       failed_this_run=failed, resumed_this_run=skipped,
                       quicklook_failed_this_run=quicklook_failed,
                       suspicious=sum(row['suspicious'] == 'yes' for row in rows),
                       review_status_counts={state: sum(row['review_status'] == state for row in rows)
                                             for state in sorted({row['review_status'] for row in rows})},
                       review_result_counts={state: sum((row['review_result'] or 'chua_co_ket_luan') == state
                                                         for row in rows)
                                             for state in sorted({row['review_result'] or 'chua_co_ket_luan'
                                                                  for row in rows})},
                       processing_sizes=sorted({f'{row["width"]}x{row["height"]}' for row in rows if row['width']}),
                       interrupted=interrupted, elapsed_seconds=round(time.monotonic() - start, 2),
                       output_dir=str(output), updated_at=now(), note=NOTE)
        write_json(output / 'summary.json', summary)
        print(file=sys.stderr)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 130 if interrupted else (1 if summary['failed'] or quicklook_failed else 0)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--limit', type=int, default=8, help='Number of images (default: 8 historical samples first)')
    selection.add_argument('--all', action='store_true', help='Process all images')
    parser.add_argument('--resume', action='store_true', help='Reuse intact outputs; retry failed/missing/corrupt outputs')
    parser.add_argument('--input-dir', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--max-side', type=int, default=0, help='Maximum side, preserving aspect ratio; 0 = native size')
    parser.add_argument('--batch-size', type=int, default=8, help='Images per review contact sheet')
    parser.add_argument('--iterations', type=int, default=5)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.batch_size < 1 or args.iterations < 1 or args.max_side < 0:
        parser.error('limit, batch-size, iterations must be positive; max-side must be >= 0')
    return args


def main(argv=None):
    cv2.setNumThreads(1)
    try:
        return run(parse_args(argv))
    except (ValueError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
