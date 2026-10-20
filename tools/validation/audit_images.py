"""Audit every input file and measure full-frame image descriptors, read-only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import sys
import csv

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np
from PIL import Image, __version__ as pillow_version
from tools.project_paths import PROJECT_ROOT, DATA_DIR, INVENTORY_DIR

ROOT = PROJECT_ROOT
DATA = DATA_DIR / 'cropped_images_576x384'
OUT = INVENTORY_DIR
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif', '.avif'}
RECORD_FIELDS = ['filename', 'basename', 'label', 'is_image_candidate', 'sha256',
                 'technical_status', 'technical_error', 'width', 'height', 'format',
                 'mode', 'frame_count', 'feature_status', 'feature_error']
METRICS = ['saturation_mean', 'value_mean', 'gray_mean', 'gray_std', 'dark_fraction',
           'bright_fraction', 'gray_entropy_bits', 'sobel_mean',
           'sobel_strong_fraction', 'laplacian_variance']


def label_for(filename):
    name = re.sub(r'_\d+$', '', Path(filename).stem.lower().replace('-', '_'))
    if name.startswith(('canis_lupus_familiaris', 'canis_familiaris')):
        return 'canis_familiaris'
    if name.startswith('felis_catus'):
        return 'felis_catus'
    return name


def histogram(channel, bins, upper, weights=None):
    counts = np.histogram(channel, bins=bins, range=(0, upper), weights=weights)[0].astype(np.float64)
    total = counts.sum()
    return counts / total if total else counts


def hsv_histogram(hsv, bins):
    return np.concatenate([histogram(hsv[:, :, i], b, 180 if i == 0 else 256,
                                    hsv[:, :, 1].astype(np.float64) / 255 if i == 0 else None)
                           for i, b in enumerate(bins)])


def feature_names():
    names = [f'global_{c}_{i:02d}' for c, n in [('h', 16), ('s', 8), ('v', 8), ('a', 8), ('b', 8)]
             for i in range(n)]
    names += [f'grid_r{r}_c{c}_{channel}_{i:02d}' for r in range(2) for c in range(4)
              for channel, n in [('h', 8), ('s', 4), ('v', 4)] for i in range(n)]
    return names


def measure_features(rgb):
    """No mask, resizing, label-dependent branches or retrieval normalization."""
    height, width = rgb.shape[:2]
    if height < 2 or width < 4:
        raise ValueError('Image too small for nonempty 2x4 grid')
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    blocks = [hsv_histogram(hsv, (16, 8, 8)), histogram(lab[:, :, 1], 8, 256),
              histogram(lab[:, :, 2], 8, 256)]
    for band in np.array_split(hsv, 2, axis=0):
        for cell in np.array_split(band, 4, axis=1):
            blocks.append(hsv_histogram(cell, (8, 4, 4)))
    vector = np.concatenate(blocks).astype(np.float32)
    gray_u8 = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = gray_u8.astype(np.float64) / 255
    probability = histogram(gray_u8, 256, 256)
    nonzero = probability[probability > 0]
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3, borderType=cv2.BORDER_REFLECT_101)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3, borderType=cv2.BORDER_REFLECT_101)
    magnitude = np.hypot(gx, gy)
    metrics = dict(zip(METRICS, map(float, [
        hsv[:, :, 1].mean() / 255, hsv[:, :, 2].mean() / 255, gray.mean(), gray.std(),
        (gray_u8 < 64).mean(), (gray_u8 >= 192).mean(), -(nonzero * np.log2(nonzero)).sum(),
        magnitude.mean(), (magnitude > 0.5).mean(),
        cv2.Laplacian(gray, cv2.CV_64F, ksize=3, borderType=cv2.BORDER_REFLECT_101).var()
    ])))
    if vector.shape != (176,) or not np.isfinite(vector).all() or not all(np.isfinite(list(metrics.values()))):
        raise ValueError('Invalid descriptor dimension or non-finite value')
    return metrics, vector


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def statistics(rows):
    result = {}
    for key in METRICS:
        if not rows:
            result[key] = {'count': 0}
            continue
        values = np.array([r[key] for r in rows], dtype=np.float64)
        result[key] = dict(count=len(rows), mean=float(values.mean()), std=float(values.std()),
                           min=float(values.min()), q25=float(np.quantile(values, .25)),
                           median=float(np.median(values)), q75=float(np.quantile(values, .75)),
                           max=float(values.max()))
    return result


def audit(data, output):
    data, output = data.expanduser().resolve(), output.expanduser().resolve()
    if not data.is_dir():
        raise ValueError(f'Input directory does not exist: {data}')
    if output.is_relative_to(data) or data.is_relative_to(output):
        raise ValueError('Input and output directories must not overlap')
    records, measurements, vectors = [], [], []
    # Enumerate all files, including unsupported files; never follow symlinks.
    paths = sorted(p for p in data.rglob('*') if p.is_file() or p.is_symlink())
    for path in paths:
        name = path.relative_to(data).as_posix()
        candidate = path.suffix.lower() in IMAGE_SUFFIXES
        row = dict.fromkeys(RECORD_FIELDS, '')
        row.update(filename=name, basename=path.name, label=label_for(name) if candidate else '',
                   is_image_candidate=int(candidate), technical_status='skipped', feature_status='skipped')
        records.append(row)
        if path.is_symlink():
            row.update(technical_error='symlink_not_followed', feature_error='technical_not_successful')
            continue
        if not candidate:
            row.update(technical_error='unsupported_extension', feature_error='not_an_image_candidate')
            continue
        try:
            raw = path.read_bytes()
            row['sha256'] = hashlib.sha256(raw).hexdigest()
            with Image.open(io.BytesIO(raw)) as im:
                im.load()  # Full decode, rather than metadata-only validation.
                row.update(width=im.width, height=im.height, format=im.format, mode=im.mode,
                           frame_count=getattr(im, 'n_frames', 1))
                decoded_image = im.copy()
            row['technical_status'] = 'success'
        except Exception as exc:
            row.update(technical_status='failed', technical_error=f'{type(exc).__name__}: {exc}',
                       feature_error='technical_not_successful')
            continue
        if row['frame_count'] != 1:
            row['feature_error'] = 'multi_frame_unsupported'
            continue
        try:
            rgb = np.array(decoded_image.convert('RGB'))
            metrics, vector = measure_features(rgb)
            measurements.append(dict(filename=name, label=row['label'], **metrics))
            vectors.append(vector)
            row['feature_status'] = 'success'
        except Exception as exc:
            row.update(feature_status='failed', feature_error=f'{type(exc).__name__}: {exc}')

    candidates = [r for r in records if r['is_image_candidate']]
    decoded = [r for r in candidates if r['technical_status'] == 'success']
    labels = sorted({r['label'] for r in candidates})
    label_counts = []
    for label in labels:
        group = [r for r in candidates if r['label'] == label]
        label_counts.append(dict(label=label, input_count=len(group),
            technical_success=sum(r['technical_status'] == 'success' for r in group),
            technical_failed=sum(r['technical_status'] == 'failed' for r in group),
            technical_skipped=sum(r['technical_status'] == 'skipped' for r in group),
            feature_success=sum(r['feature_status'] == 'success' for r in group),
            feature_failed=sum(r['feature_status'] == 'failed' for r in group),
            feature_skipped=sum(r['feature_status'] == 'skipped' for r in group)))
    counts = Counter(r['basename'] for r in candidates)
    summary = dict(schema_version=2, image_count=len(candidates), file_count=len(records),
        non_image_file_count=len(records) - len(candidates),
        unique_image_filenames=len({r['filename'] for r in candidates}),
        unique_image_basenames=len(counts), duplicate_image_basenames=sorted(k for k, n in counts.items() if n > 1),
        technical_status_counts=dict(Counter(r['technical_status'] for r in candidates)),
        feature_status_counts=dict(Counter(r['feature_status'] for r in candidates)),
        sizes=dict(Counter(f"{r['width']}x{r['height']}" for r in decoded)),
        formats=dict(Counter(r['format'] for r in decoded)),
        modes=dict(Counter(r['mode'] for r in decoded)),
        labels={r['label']: r['input_count'] for r in label_counts}, label_counts=label_counts,
        issues=[r for r in records if r['technical_status'] != 'success' or r['feature_status'] != 'success'])
    summary['checks'] = dict(unique_relative_filenames=summary['unique_image_filenames'] == len(candidates),
        unique_basenames=len(counts) == len(candidates),
        technical_total=sum(summary['technical_status_counts'].values()) == len(candidates),
        feature_total=sum(summary['feature_status_counts'].values()) == len(candidates),
        label_total=sum(r['input_count'] for r in label_counts) == len(candidates),
        feature_rows=len(measurements) == sum(r['feature_success'] for r in label_counts))
    feature_summary = dict(schema_version=1, scope='full_frame_including_background',
        successful_images=len(measurements), descriptor_name='full_frame_color_histograms_v1',
        descriptor_dimensions=176, b400_status='design_only_not_extracted',
        statistics=statistics(measurements),
        by_label={label: statistics([r for r in measurements if r['label'] == label]) for label in labels})
    environment = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        input_directory=str(data), python=platform.python_version(), platform=platform.platform(),
        machine=platform.machine(), pillow=pillow_version, numpy=np.__version__, opencv=cv2.__version__,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        image_extensions=sorted(IMAGE_SUFFIXES), recursive=True, source_writes=False,
        color_conversion='Pillow RGB then OpenCV uint8 HSV/Lab/GRAY; no resize, EXIF rotation or ICC transform',
        histogram='Per-channel L1, saturation-weighted hue; zero total gives zero histogram; no final L2',
        grid='2 rows x 4 columns, numpy.array_split, row-major',
        descriptor_blocks={'global_hsv': [0, 32], 'global_lab_ab': [32, 48], 'grid_hsv': [48, 176]},
        grayscale='OpenCV uint8 gray, then float64 /255; entropy on 256 gray levels',
        dark_threshold='gray_u8 < 64', bright_threshold='gray_u8 >= 192',
        sobel='ksize=3, no scale factor; hypot(gx,gy), strong > 0.5',
        laplacian='ksize=3 on gray/255; population variance',
        border='BORDER_REFLECT_101', aggregation='Each successful image has equal weight; population std, linear quantiles')
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'image_processing.csv', RECORD_FIELDS, records)
    write_csv(output / 'feature_metrics.csv', ['filename', 'label'] + METRICS, measurements)
    write_csv(output / 'label_counts.csv', list(label_counts[0]) if label_counts else
              ['label', 'input_count', 'technical_success', 'technical_failed', 'technical_skipped',
               'feature_success', 'feature_failed', 'feature_skipped'], label_counts)
    group_rows = []
    for label, rows in [('__all__', measurements)] + [(k, [r for r in measurements if r['label'] == k]) for k in labels]:
        for metric, values in statistics(rows).items():
            group_rows.append(dict(label=label, metric=metric, **values))
    write_csv(output / 'feature_statistics.csv', ['label', 'metric', 'count', 'mean', 'std', 'min',
                                                'q25', 'median', 'q75', 'max'], group_rows)
    np.savez_compressed(output / 'full_frame_color_features.npz',
        filenames=np.array([r['filename'] for r in measurements], dtype=str),
        feature_names=np.array(feature_names(), dtype=str),
        features=np.stack(vectors) if vectors else np.empty((0, 176), dtype=np.float32))
    for name, content in [('image_inventory.json', summary), ('feature_summary.json', feature_summary),
                          ('analysis_environment.json', environment)]:
        (output / name).write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=DATA)
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args(argv)
    try:
        summary = audit(args.input_dir, args.output_dir)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: summary[key] for key in ['image_count', 'file_count', 'non_image_file_count',
          'technical_status_counts', 'feature_status_counts', 'checks']}, ensure_ascii=False, indent=2))
    return 0 if summary['image_count'] > 0 and all(summary['checks'].values()) and all(
        r['technical_status'] == 'success' and r['feature_status'] == 'success'
        for r in summary['issues'] if r['is_image_candidate']) else 1


if __name__ == '__main__':
    sys.exit(main())
