#!/usr/bin/env python3
"""Create fresh U2-Net candidate masks for a queue of rejected overlays.

Run with .venv-image-tools/bin/python. Sources and existing masks are read
only. Output is a separate, editor-compatible dataset, never automatically approved.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import PROJECT_ROOT, SEGMENTATION_DIR, GRABCUT_OUTPUT_DIR

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, __version__ as pillow_version

ROOT = PROJECT_ROOT
BASE = SEGMENTATION_DIR
PREVIOUS = GRABCUT_OUTPUT_DIR
FIELDS = ['filename', 'source_sha256', 'source_path', 'mask_path', 'overlay_path',
          'source_width', 'source_height', 'width', 'height', 'total_pixels',
          'mask_pixels', 'mask_ratio', 'status', 'review_status', 'review_result', 'suspicious',
          'review_flags', 'quicklook_path', 'mask_sha256', 'overlay_sha256',
          'previous_mask_path', 'previous_overlay_path', 'previous_mask_sha256',
          'previous_overlay_sha256', 'previous_mask_ratio', 'changed_pixel_fraction',
          'method', 'error', 'processed_at']
NOTE = ('Candidate masks for manual review. Pixel fractions and change from old masks '
        'are inspection statistics, not segmentation accuracy. No feature vectors extracted.')


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def atomic_bytes(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.new-mask-')
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def write_csv(path, rows, fields=FIELDS):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, stream.getvalue().encode())


def save_image(path, image):
    stream = io.BytesIO()
    image.save(stream, format='JPEG' if path.suffix == '.jpg' else 'PNG')
    atomic_bytes(path, stream.getvalue())


def letterbox(image):
    """Scale uniformly, pad to the model's 320x320 input; never stretch geometry."""
    width, height = image.size
    scale = 320 / max(width, height)
    rw, rh = max(1, round(width * scale)), max(1, round(height * scale))
    left, top = (320 - rw) // 2, (320 - rh) // 2
    canvas = Image.new('RGB', (320, 320), (124, 116, 104))
    canvas.paste(image.resize((rw, rh), Image.Resampling.LANCZOS), (left, top))
    return canvas, (left, top, left + rw, top + rh)


def make_tensor(image):
    canvas, box = letterbox(image)
    values = np.asarray(canvas, dtype=np.float32)
    values /= max(float(values.max()), 1e-6)
    values = (values - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    return np.ascontiguousarray(values.transpose(2, 0, 1)[None]), box


def predict_mask(session, image, threshold=0.5):
    tensor, box = make_tensor(image)
    prediction = np.asarray(session.run(None, {session.get_inputs()[0].name: tensor})[0])[0, 0]
    if prediction.shape != (320, 320) or not np.isfinite(prediction).all():
        raise ValueError('Invalid model output')
    left, top, right, bottom = box
    prediction = prediction[top:bottom, left:right]
    low, high = float(prediction.min()), float(prediction.max())
    if high - low < 1e-6:
        raise ValueError('Flat model response; no usable foreground signal')
    probability = np.clip((prediction - low) / (high - low), 0, 1)
    # Remove padding and restore native dimensions before thresholding.
    restored = np.asarray(Image.fromarray(probability.astype(np.float32)).resize(image.size, Image.Resampling.BILINEAR))
    return np.where(restored >= threshold, 255, 0).astype(np.uint8)


def overlay(image, mask):
    result = np.array(image)
    background = mask == 0
    result[background] = (0.35 * result[background] + 0.65 * np.array([255, 0, 0])).astype(np.uint8)
    return Image.fromarray(result)


def statistics(mask, previous):
    count = int(np.count_nonzero(mask))
    ratio = count / mask.size
    changed = float(np.mean((mask != 0) != (previous != 0)))
    flags = []
    if count == 0:
        flags.append('empty_mask')
    if ratio < 0.05:
        flags.append('area_below_5pct')
    if ratio > 0.85:
        flags.append('area_above_85pct')
    if changed > 0.20:
        flags.append('large_change_from_previous')
    if np.any(mask[0]) or np.any(mask[-1]) or np.any(mask[:, 0]) or np.any(mask[:, -1]):
        flags.append('foreground_at_image_edge')
    return dict(mask_pixels=count, mask_ratio=ratio, total_pixels=mask.size,
                previous_mask_ratio=int(np.count_nonzero(previous)) / previous.size,
                changed_pixel_fraction=changed, suspicious='yes' if flags else 'no',
                review_flags=';'.join(flags))


def reusable(row, output):
    if row['status'] != 'success':
        return False
    for name in ('source', 'previous_mask', 'previous_overlay'):
        path = Path(row[name + '_path'])
        if not path.is_file() or sha256(path) != row[name + '_sha256']:
            return False
    for name in ('mask', 'overlay'):
        path = output / row[name + '_path']
        if not path.is_file() or sha256(path) != row[name + '_sha256']:
            return False
    return True


def quicklook(output, rows):
    canvas = Image.new('RGB', (1152, 34 + 246 * len(rows)), 'white')
    draw = ImageDraw.Draw(canvas)
    draw.text((4, 7), 'SOURCE | PREVIOUS OVERLAY | NEW MASK | NEW OVERLAY (red = removed background); ALL REQUIRE REVIEW', fill='black')
    for index, row in enumerate(rows):
        y = 34 + 246 * index
        paths = [Path(row['source_path']), Path(row['previous_overlay_path']),
                 output / row['mask_path'], output / row['overlay_path']]
        if row['status'] == 'success':
            for column, path in enumerate(paths):
                with Image.open(path) as opened:
                    image = opened.convert('RGB')
                    image.thumbnail((288, 192), Image.Resampling.LANCZOS)
                    canvas.paste(image, (column * 288 + (288 - image.width) // 2, y + (192 - image.height) // 2))
        color = '#b00020' if row['suspicious'] == 'yes' or row['status'] != 'success' else 'black'
        draw.text((4, y + 194), f'{row["filename"]} | {row["width"]}x{row["height"]} | {row["review_status"]}', fill=color)
        draw.text((4, y + 210), f'processing={row["status"]} | {row["review_flags"] or "No heuristic flags; manual review required"}', fill=color)
        if row['error']:
            draw.text((4, y + 226), row['error'][:160], fill=color)
    save_image(output / rows[0]['quicklook_path'], canvas)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-dir', type=Path, default=PREVIOUS / 'overlays/needs_revision')
    parser.add_argument('--previous-dir', type=Path, default=PREVIOUS)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data/cropped_images_576x384')
    parser.add_argument('--output-dir', type=Path, default=BASE / 'mask_regeneration')
    parser.add_argument('--model', type=Path, default=Path.home() / '.cache/animal-crop/u2net.onnx')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--threshold', type=float, default=0.5)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args(argv)
    if not 0 < args.threshold < 1 or args.threads < 1 or (args.limit is not None and args.limit < 1):
        parser.error('Invalid threshold, threads or limit')
    return args


def run(args):
    source, previous, queue, output = (path.resolve() for path in (args.source_dir, args.previous_dir, args.queue_dir, args.output_dir))
    for protected in (source, previous):
        if output == protected or output in protected.parents or protected in output.parents:
            raise ValueError('New output must be separate from source and previous results')
    if not args.model.is_file():
        raise ValueError(f'Local model missing: {args.model}')
    with (previous / 'manifest.csv').open(encoding='utf-8-sig', newline='') as stream:
        original_rows = {row['filename'] + '.png': row for row in csv.DictReader(stream)}
    files = sorted((p for p in queue.iterdir() if p.is_file() and p.suffix.lower() == '.png'), key=lambda p: p.name.casefold())
    if args.limit:
        files = files[:args.limit]
    if not files or any(path.name not in original_rows for path in files):
        raise ValueError('Empty queue or queue image missing from original manifest')
    output.mkdir(parents=True, exist_ok=True)
    with (output / '.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existing = [p for p in output.iterdir() if p.name != '.run.lock']
        if existing and not args.resume:
            raise ValueError('Output exists; use --resume or a new output directory')
        config = dict(model=str(args.model.resolve()), model_sha256=sha256(args.model),
                      script_sha256=sha256(Path(__file__)), input_size=[320, 320],
                      geometry='aspect_preserving_resize_then_padding; unpad; restore_native_size',
                      threshold=args.threshold, threads=args.threads, queue_dir=str(queue),
                      source_dir=str(source), previous_dir=str(previous), method='u2net_onnx_cpu',
                      numpy=np.__version__, onnxruntime=ort.__version__, pillow=pillow_version, note=NOTE)
        config_path = output / 'run_config.json'
        if config_path.exists() and json.loads(config_path.read_text()) != config:
            raise ValueError('Configuration changed; use a new output directory')
        if existing and not config_path.exists():
            raise ValueError('Missing run configuration; use a new output directory')
        for directory in ('masks', 'overlays/needs_revision', 'overlays/accepted', 'quicklooks'):
            path = output / directory
            if path.is_symlink():
                raise ValueError('Output subdirectory is a symlink')
            path.mkdir(parents=True, exist_ok=True)
        write_json(config_path, config)
        old_rows = {}
        manifest = output / 'manifest.csv'
        if manifest.exists():
            with manifest.open(newline='') as stream:
                old_rows = {row['filename']: row for row in csv.DictReader(stream)}
        names = {original_rows[path.name]['filename'] for path in files}
        if not set(old_rows).issubset(names):
            raise ValueError('Selection would discard existing manifest rows')
        rows = []
        for index, path in enumerate(files):
            original = original_rows[path.name]
            name = original['filename']
            if Path(name).name != name:
                raise ValueError('Invalid source filename')
            mask_path = (previous / original['mask_path']).resolve()
            if not mask_path.is_relative_to(previous):
                raise ValueError('Previous mask escapes its dataset')
            row = dict.fromkeys(FIELDS, '')
            row.update(filename=name, source_path=str(source / name),
                       mask_path=f'masks/{name}.png', overlay_path=f'overlays/needs_revision/{name}.png',
                       previous_mask_path=str(mask_path), previous_overlay_path=str(path),
                       quicklook_path=f'quicklooks/batch_{index // 8 + 1:03d}.jpg',
                       status='pending', review_status='chua_duyet', review_result='',
                       method=config['method'])
            if name in old_rows:
                row.update(old_rows[name])
                row['quicklook_path'] = f'quicklooks/batch_{index // 8 + 1:03d}.jpg'
            rows.append(row)
        write_csv(manifest, rows)
        error_path = output / 'errors.csv'
        error_fields = ['timestamp', 'filename', 'error']
        if not error_path.exists():
            write_csv(error_path, [], error_fields)
        options = ort.SessionOptions()
        options.intra_op_num_threads = args.threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.log_severity_level = 3
        session = ort.InferenceSession(str(args.model), sess_options=options, providers=['CPUExecutionProvider'])
        start = time.monotonic()
        processed = skipped = 0
        interrupted = False
        try:
            for index, row in enumerate(rows):
                try:
                    if args.resume and reusable(row, output):
                        skipped += 1
                    else:
                        row.update(status='pending', error='', review_status='chua_duyet',
                                   review_result='')
                        source_path = Path(row['source_path'])
                        row['source_sha256'] = sha256(source_path)
                        original = original_rows[row['filename'] + '.png']
                        if original.get('source_sha256') and row['source_sha256'] != original['source_sha256']:
                            raise ValueError('Source image differs from original manifest')
                        with Image.open(source_path) as opened:
                            image = opened.convert('RGB')
                        row.update(width=image.width, height=image.height, source_width=image.width, source_height=image.height)
                        with Image.open(row['previous_mask_path']) as opened:
                            old_mask = np.array(opened.convert('L'))
                        if old_mask.shape != (image.height, image.width) or not set(np.unique(old_mask)).issubset({0, 255}):
                            raise ValueError('Previous mask has invalid dimensions or values')
                        row['previous_mask_sha256'] = sha256(Path(row['previous_mask_path']))
                        row['previous_overlay_sha256'] = sha256(Path(row['previous_overlay_path']))
                        mask = predict_mask(session, image, args.threshold)
                        row.update(statistics(mask, old_mask))
                        save_image(output / row['mask_path'], Image.fromarray(mask))
                        save_image(output / row['overlay_path'], overlay(image, mask))
                        if sha256(source_path) != row['source_sha256']:
                            raise ValueError('Source image changed during inference')
                        row.update(status='success', mask_sha256=sha256(output / row['mask_path']),
                                   overlay_sha256=sha256(output / row['overlay_path']), processed_at=now())
                        processed += 1
                        del image, mask, old_mask
                except Exception as exc:
                    row.update(status='failed', error=f'{type(exc).__name__}: {exc}', processed_at=now())
                    with error_path.open('a', encoding='utf-8', newline='') as stream:
                        csv.DictWriter(stream, fieldnames=error_fields).writerow(dict(timestamp=now(), filename=row['filename'], error=row['error']))
                write_csv(manifest, rows)
                done = index + 1
                print(f'{done}/{len(rows)} status={row["status"]} reused={skipped} elapsed={time.monotonic() - start:.1f}s {row["filename"]}', flush=True)
                if done % 8 == 0 or done == len(rows):
                    quicklook(output, rows[index - index % 8:index + 1])
        except KeyboardInterrupt:
            interrupted = True
        finally:
            write_csv(manifest, rows)
            write_csv(output / 'review_priority.csv', [row for row in rows if row['suspicious'] == 'yes' or row['status'] == 'failed'])
            summary = dict(selected=len(rows), success=sum(r['status'] == 'success' for r in rows),
                           failed=sum(r['status'] == 'failed' for r in rows), pending=sum(r['status'] == 'pending' for r in rows),
                           processed_this_run=processed, reused_this_run=skipped,
                           suspicious=sum(r['suspicious'] == 'yes' for r in rows),
                           processing_sizes=sorted({f'{r["width"]}x{r["height"]}' for r in rows if r['width']}),
                           elapsed_seconds=round(time.monotonic() - start, 2), interrupted=interrupted,
                           review_status_counts={s:sum(r['review_status'] == s for r in rows) for s in sorted({r['review_status'] for r in rows})},
                           review_result_counts={s:sum((r['review_result'] or 'chua_co_ket_luan') == s for r in rows)
                                                 for s in sorted({r['review_result'] or 'chua_co_ket_luan' for r in rows})},
                           updated_at=now(), note=NOTE)
            write_json(output / 'summary.json', summary)
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return 130 if interrupted else int(summary['failed'] > 0)


if __name__ == '__main__':
    try:
        sys.exit(run(parse_args()))
    except (ValueError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(2)
