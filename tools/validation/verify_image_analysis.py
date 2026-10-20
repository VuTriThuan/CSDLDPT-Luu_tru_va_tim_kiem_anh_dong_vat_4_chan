"""Verify requirement-2 outputs against source files, aggregates and report tables."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
from tools.validation import audit_images as audit


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def verify(data, output, report=None):
    data, output = data.resolve(), output.resolve()
    inventory = json.loads((output / 'image_inventory.json').read_text())
    summary = json.loads((output / 'feature_summary.json').read_text())
    environment = json.loads((output / 'analysis_environment.json').read_text())
    require(environment['script_sha256'] == hashlib.sha256(Path(audit.__file__).read_bytes()).hexdigest(),
            'Analysis script has changed since the run; rerun the analysis')
    records = read_csv(output / 'image_processing.csv')
    sources = {p.relative_to(data).as_posix(): p for p in data.rglob('*') if p.is_file() or p.is_symlink()}
    require(len(records) == len(sources) == inventory['file_count'], 'File count mismatch')
    require({r['filename'] for r in records} == set(sources), 'Source filenames differ from manifest')
    require(len({r['filename'] for r in records}) == len(records), 'Duplicate manifest rows')
    candidates = [r for r in records if r['is_image_candidate'] == '1']
    require(len(candidates) == inventory['image_count'], 'Image count mismatch')
    for row in records:
        path = sources[row['filename']]
        require((row['is_image_candidate'] == '1') == (path.suffix.lower() in audit.IMAGE_SUFFIXES),
                f'Candidate mismatch: {path.name}')
        if row['sha256']:
            require(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'],
                    f'Source hash mismatch: {path.name}')
        for stage in ['technical', 'feature']:
            require(row[f'{stage}_status'] in {'success', 'failed', 'skipped'}, 'Invalid status')
            if row[f'{stage}_status'] != 'success':
                require(bool(row[f'{stage}_error']), f'Missing error/skip reason: {path.name}')
    require(len({r['filename'] for r in candidates}) == inventory['unique_image_filenames'], 'Unique path mismatch')
    basename_counts = Counter(r['basename'] for r in candidates)
    require(len(basename_counts) == inventory['unique_image_basenames'], 'Unique basename mismatch')
    require(sorted(k for k, n in basename_counts.items() if n > 1) == inventory['duplicate_image_basenames'],
            'Duplicate basenames mismatch')
    require(len(records) - len(candidates) == inventory['non_image_file_count'], 'Non-image count mismatch')
    for stage in ['technical', 'feature']:
        require(dict(Counter(r[f'{stage}_status'] for r in candidates)) == inventory[f'{stage}_status_counts'],
                f'{stage} status count mismatch')
    decoded = [r for r in candidates if r['technical_status'] == 'success']
    require(dict(Counter(f"{r['width']}x{r['height']}" for r in decoded)) == inventory['sizes'], 'Size counts mismatch')
    for field, key in [('format', 'formats'), ('mode', 'modes')]:
        require(dict(Counter(r[field] for r in decoded)) == inventory[key], f'{key} mismatch')
    require(dict(Counter(r['label'] for r in candidates)) == inventory['labels'], 'Labels mismatch')
    counts = read_csv(output / 'label_counts.csv')
    require(len(counts) == len(inventory['label_counts']), 'Label row count mismatch')
    for saved, expected in zip(counts, inventory['label_counts']):
        require(saved == {k: str(v) for k, v in expected.items()}, 'Label CSV/JSON mismatch')
        group = [r for r in candidates if r['label'] == saved['label']]
        require(len(group) == int(saved['input_count']), 'Label input count mismatch')
        for stage in ['technical', 'feature']:
            for status in ['success', 'failed', 'skipped']:
                require(sum(r[f'{stage}_status'] == status for r in group) == int(saved[f'{stage}_{status}']),
                        f'Label {stage}/{status} count mismatch')
    metrics = read_csv(output / 'feature_metrics.csv')
    successful = [r for r in candidates if r['feature_status'] == 'success']
    require([r['filename'] for r in metrics] == [r['filename'] for r in successful], 'Feature filenames mismatch')
    require([r['label'] for r in metrics] == [r['label'] for r in successful], 'Feature labels mismatch')
    require(len(metrics) == summary['successful_images'], 'Feature count mismatch')
    values = [dict(r, **{key: float(r[key]) for key in audit.METRICS}) for r in metrics]
    require(summary['scope'] == 'full_frame_including_background' and
            summary['b400_status'] == 'design_only_not_extracted', 'Incorrect feature scope')
    all_stats = read_csv(output / 'feature_statistics.csv')
    expected_stats_rows = (len(counts) + 1) * len(audit.METRICS)
    require(len(all_stats) == expected_stats_rows, 'Statistics row count mismatch')
    stat_lookup = {(r['label'], r['metric']): r for r in all_stats}
    require(len(stat_lookup) == len(all_stats), 'Duplicate statistics rows')
    for label in ['__all__'] + list(inventory['labels']):
        group = values if label == '__all__' else [r for r in values if r['label'] == label]
        calculated = audit.statistics(group)
        stored = summary['statistics'] if label == '__all__' else summary['by_label'][label]
        for metric in audit.METRICS:
            for key, value in calculated[metric].items():
                require(np.isclose(stored[metric][key], value, rtol=1e-12, atol=1e-12), 'JSON statistic mismatch')
                require(np.isclose(float(stat_lookup[label, metric][key]), value, rtol=1e-12, atol=1e-12),
                        'CSV statistic mismatch')
    with np.load(output / 'full_frame_color_features.npz', allow_pickle=False) as arrays:
        matrix = arrays['features']
        require(matrix.shape == (len(metrics), 176) and matrix.dtype == np.float32, 'Descriptor shape/type mismatch')
        require(summary['descriptor_dimensions'] == matrix.shape[1], 'Descriptor dimension summary mismatch')
        require(arrays['filenames'].tolist() == [r['filename'] for r in metrics], 'NPZ filenames mismatch')
        require(arrays['feature_names'].tolist() == audit.feature_names(), 'NPZ feature names mismatch')
        require(np.isfinite(matrix).all() and ((matrix >= 0) & (matrix <= 1)).all(), 'Invalid histogram values')
        # Every channel distribution sums to 1, except a hue distribution may be all zero.
        blocks = [(0, 16, True), (16, 24, False), (24, 32, False), (32, 40, False), (40, 48, False)]
        blocks += [(48 + i * 16 + lo, 48 + i * 16 + hi, hue) for i in range(8)
                   for lo, hi, hue in [(0, 8, True), (8, 12, False), (12, 16, False)]]
        for start, stop, hue in blocks:
            sums = matrix[:, start:stop].sum(axis=1)
            require(np.all(np.isclose(sums, 1) | (hue & np.isclose(sums, 0))), 'Histogram L1 mismatch')
    if report is not None:
        text = report.read_text()
        for row in counts:
            line = f"| `{row['label']}` | {row['input_count']} | {row['technical_success']} | {row['feature_success']} |"
            require(line in text, f'Report label row mismatch: {row["label"]}')
        for metric, stats in summary['statistics'].items():
            line = '| `' + metric + '` | ' + ' | '.join(f'{stats[k]:.6f}' for k in ['mean', 'std', 'min', 'median', 'max']) + ' |'
            require(line in text, f'Report metric row mismatch: {metric}')
        example_block = text.split('<!-- example-results:start -->')[1].split('<!-- example-results:end -->')[0]
        for row in metrics:
            if f'[{row["filename"]}]' in example_block:
                tail = ' | ' + ' | '.join(f'{float(row[k]):.6f}' for k in ['saturation_mean', 'gray_entropy_bits', 'sobel_mean']) + ' |'
                require(any(f'[{row["filename"]}]' in line and line.endswith(tail) for line in example_block.splitlines()),
                        f'Report example mismatch: {row["filename"]}')
        technical = inventory['technical_status_counts']
        feature = inventory['feature_status_counts']
        expected = [
            f"| Tổng tệp trong thư mục | {len(records)} |",
            f"| Tệp ảnh đầu vào | {len(candidates)} |",
            f"| Tên tệp ảnh duy nhất, gồm cả tên cơ sở | {len(basename_counts)} |",
            '| Giải mã thành công / lỗi / bỏ qua ảnh | ' + ' / '.join(str(technical.get(k, 0)) for k in ['success', 'failed', 'skipped']) + ' |',
            '| Tính đặc trưng thành công / lỗi / bỏ qua ảnh | ' + ' / '.join(str(feature.get(k, 0)) for k in ['success', 'failed', 'skipped']) + ' |',
            f"| Định dạng thực JPEG, mode RGB | {inventory['formats'].get('JPEG', 0)} |",
            f"| Kích thước 576 × 384, tỉ lệ 3:2 | {inventory['sizes'].get('576x384', 0)} |",
            f"| Nhóm nhãn theo tên tệp | {len(counts)} |",
            f"| Tệp không phải ảnh, đã ghi lý do bỏ qua | {inventory['non_image_file_count']} |"]
        for line in expected:
            require(line in text, f'Report count mismatch: {line}')
    return dict(verified=True, input_images=len(candidates), technical_success=len(decoded),
                feature_success=len(metrics), source_hashes_checked=sum(bool(r['sha256']) for r in records),
                report_verified=report is not None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=audit.DATA)
    parser.add_argument('--output-dir', type=Path, default=audit.OUT)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    report = args.report
    if report is None and args.input_dir.resolve() == audit.DATA.resolve() and args.output_dir.resolve() == audit.OUT.resolve():
        report = audit.ROOT / 'docs/reports/search_feature_design.md'
    try:
        result = verify(args.input_dir, args.output_dir, report)
    except (ValueError, OSError, KeyError, IndexError) as exc:
        print(f'Verification failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
