"""Rebuild masks and review sheets from edited overlays, without rerunning GrabCut.

Default: read-only audit. --apply: back up and update derived files.
--verify: also compare the current quicklooks with freshly rendered sheets.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import fcntl
import io
import json
from pathlib import Path
import sys
import tempfile
import uuid
import zipfile

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
from PIL import Image

from tools.segmentation import run_grabcut as gc


def safe_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or relative == Path('.'):
        raise ValueError(f'Unsafe path: {relative}')
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f'Unsafe path: {relative}')
    return path


def recover_mask(image, overlay, old_mask, tolerance=0):
    rgb = image[:, :, ::-1]
    if overlay.shape != rgb.shape or old_mask.shape != rgb.shape[:2]:
        raise ValueError('Source, mask and overlay dimensions differ')
    tinted = (0.35 * rgb + 0.65 * np.array([255, 0, 0])).astype(np.uint8)
    source_distance = np.max(np.abs(overlay.astype(np.int16) - rgb), axis=2)
    tint_distance = np.max(np.abs(overlay.astype(np.int16) - tinted), axis=2)
    source_match, tint_match = source_distance == 0, tint_distance == 0
    unknown = ~(source_match | tint_match)
    # Only accept small deviations if one interpretation is unambiguous.
    approximate_source = unknown & (source_distance <= tolerance) & (tint_distance > tolerance)
    approximate_tint = unknown & (tint_distance <= tolerance) & (source_distance > tolerance)
    unresolved = unknown & ~(approximate_source | approximate_tint)
    if np.any(unresolved):
        raise ValueError(f'{np.count_nonzero(unresolved)} pixels do not match source or red tint')
    mask = np.where(source_match | approximate_source, 255, 0).astype(np.uint8)
    ambiguous = source_match & tint_match
    mask[ambiguous] = old_mask[ambiguous]
    return mask, int(unknown.sum())


def csv_bytes(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def accepted_manual_edits(output):
    """Only a completed 'save and move to accepted' is a recorded pass decision."""
    accepted = defaultdict(set)
    for path in (output / 'manual_edits').glob('*/record.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        name = record.get('filename')
        if (record.get('state') == 'saved' and isinstance(name, str)
                and Path(name).name == name
                and record.get('overlay_after') == f'overlays/đạt/{name}.png'):
            digest = record.get('manifest_after', {}).get('overlay_sha256')
            if digest:
                accepted[name].add(digest)
    return accepted


def atomic_bytes(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            import os
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def sync(output, source, apply=False, verify=False, tolerance=0,
         mark_pending_reviewed=False, mark_empty_results_passed=False):
    output, source = output.resolve(), source.resolve()
    if output == source or output in source.parents or source in output.parents:
        raise ValueError('Source and output directories must be separate')
    manifest_before = (output / 'manifest.csv').read_bytes()
    reader = csv.DictReader(io.StringIO(manifest_before.decode('utf-8')))
    fields, original_rows = reader.fieldnames, list(reader)
    if not original_rows or len({r['filename'] for r in original_rows}) != len(original_rows):
        raise ValueError('Empty manifest or duplicate filenames')
    fields = list(fields)
    if 'review_result' not in fields:
        fields.insert(fields.index('review_status') + 1, 'review_result')
    accepted_names = accepted_manual_edits(output)
    candidates = defaultdict(list)
    for path in (output / 'overlays').rglob('*.png'):
        candidates[path.name].append(path)
    for path in output.glob('*.png'):
        candidates[path.name].append(path)
    report = dict(images=len(original_rows), masks_changed=0, overlay_paths_changed=0,
                  source_hashes_changed=0, metadata_rows_changed=0,
                  review_statuses_changed=0, review_results_changed=0,
                  approximate_pixels=0, approximate_images=[], external_overlays=[], errors=[])
    snapshots = {}
    rows, batches = [], defaultdict(list)
    with tempfile.TemporaryDirectory(prefix='.overlay-sync-', dir=output) as temporary:
        stage = Path(temporary)
        replacements = {}

        def prepare(relative, data):
            target = safe_path(output, relative)
            before = target.read_bytes() if target.exists() else None
            if before == data:
                return
            staged = safe_path(stage, relative)
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
            replacements[str(relative)] = before

        for index, old_row in enumerate(original_rows):
            row = dict(old_row)
            try:
                name = row['filename']
                paths = candidates[name + '.png']
                if len(paths) != 1:
                    raise ValueError(f'Expected one overlay, found {len(paths)}')
                overlay_path = safe_path(output, paths[0].relative_to(output))
                mask_path = safe_path(output, row['mask_path'])
                source_path = safe_path(source, name)
                for path in (overlay_path, mask_path, source_path):
                    snapshots[path] = gc.sha256(path)
                image, sw, sh = gc.read_image(source_path)
                if image.shape[:2] != (int(row['height']), int(row['width'])):
                    raise ValueError('Native source size differs from recorded processing size')
                with Image.open(overlay_path) as saved:
                    if saved.mode != 'RGB' or saved.format != 'PNG':
                        raise ValueError('Expected lossless RGB PNG overlay')
                    overlay = np.array(saved)
                with Image.open(mask_path) as saved:
                    mask = np.array(saved)
                    if saved.mode != 'L' or not set(np.unique(mask)).issubset({0, 255}):
                        raise ValueError('Expected binary L-mode mask')
                recovered, approximate = recover_mask(image, overlay, mask, tolerance)
                changed = not np.array_equal(mask, recovered)
                report['masks_changed'] += int(changed)
                relative_overlay = overlay_path.relative_to(output).as_posix()
                report['overlay_paths_changed'] += int(row['overlay_path'] != relative_overlay)
                report['source_hashes_changed'] += int(row['source_sha256'] != snapshots[source_path])
                if overlay_path.parent == output:
                    report['external_overlays'].append(relative_overlay)
                if approximate:
                    report['approximate_pixels'] += approximate
                    report['approximate_images'].append(dict(filename=name, pixels=approximate))
                if changed:
                    stream = io.BytesIO()
                    Image.fromarray(recovered).save(stream, format='PNG')
                    prepare(row['mask_path'], stream.getvalue())
                row.update(gc.mask_statistics(recovered))
                # Visual observations on an unchanged mask remain applicable.
                flags = set(filter(None, row['review_flags'].split(';')))
                if not changed:
                    flags.update(f for f in old_row['review_flags'].split(';') if f.startswith('visual_'))
                row['review_flags'] = ';'.join(sorted(flags))
                row['suspicious'] = 'yes' if flags else 'no'
                staged_mask = stage / row['mask_path']
                row.update(overlay_path=relative_overlay, source_sha256=snapshots[source_path],
                           source_width=sw, source_height=sh, status='success', error='',
                           mask_sha256=gc.sha256(staged_mask) if changed else snapshots[mask_path],
                           overlay_sha256=snapshots[overlay_path])
                # Preserve existing review decisions; only explicit category folders change them.
                if overlay_path.parent.name == 'đạt':
                    row['review_status'] = 'da_duyet'
                elif overlay_path.parent.name in ('cần sửa', 'làm lại'):
                    row['review_status'] = 'can_sua' if overlay_path.parent.name == 'cần sửa' else 'lam_lai'
                if mark_pending_reviewed and row['review_status'] == 'chua_duyet':
                    row['review_status'] = 'da_duyet'
                result = row.get('review_result', '')
                if result not in ('', 'dat', 'can_sua', 'lam_lai'):
                    raise ValueError(f'Invalid review_result: {result}')
                # An old decision no longer certifies a changed image or mask.
                if (changed or old_row.get('overlay_sha256') != snapshots[overlay_path]):
                    result = ''
                if overlay_path.parent.name == 'đạt':
                    result = 'dat'
                elif overlay_path.parent.name == 'cần sửa':
                    result = 'can_sua'
                elif overlay_path.parent.name == 'làm lại':
                    result = 'lam_lai'
                elif not result and snapshots[overlay_path] in accepted_names.get(name, ()):
                    result = 'dat'
                if mark_empty_results_passed and not result:
                    result = 'dat'
                row['review_result'] = result
                row = {k: str(v) for k, v in row.items()}
                report['metadata_rows_changed'] += int(row != old_row)
                report['review_statuses_changed'] += int(row['review_status'] != old_row['review_status'])
                report['review_results_changed'] += int(result != old_row.get('review_result', ''))
                safe_path(output, row['quicklook_path'])
                batches[row['quicklook_path']].append(row)
                rows.append(row)
            except Exception as exc:
                report['errors'].append(dict(filename=old_row['filename'], error=str(exc)))
            if (index + 1) % 100 == 0:
                print(f'Audited {index + 1}/{len(original_rows)}', flush=True)
        if report['errors']:
            return report
        if not apply and not verify:
            return report

        # Render sheets against staged masks and unchanged overlays. Temporary links
        # are internal to the staging directory and never replace user artifacts.
        for row in rows:
            for field in ('mask_path', 'overlay_path'):
                link = safe_path(stage, row[field])
                if not link.exists():
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(safe_path(output, row[field]))
        for relative, batch in batches.items():
            (stage / relative).parent.mkdir(parents=True, exist_ok=True)
            gc.quicklook(stage, source, batch)
            target = safe_path(output, relative)
            before = target.read_bytes() if target.exists() else None
            if before != (stage / relative).read_bytes():
                replacements[relative] = before
        report['quicklooks'] = len(batches)
        report['quicklooks_changed'] = sum(p in replacements for p in batches)
        prepare('manifest.csv', csv_bytes(rows, fields))
        priority = sorted((r for r in rows if r['suspicious'] == 'yes' or r['status'] == 'failed'),
                          key=lambda r: (r['status'] != 'failed', -len(r['review_flags'].split(';')), r['filename']))
        prepare('review_priority.csv', csv_bytes(priority, fields))
        if verify:
            report['verified'] = not replacements
            report['stale_files'] = sorted(replacements)
            return report

        summary_path = output / 'summary.json'
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        summary.update(selected=len(rows), success=len(rows), failed=0, pending=0,
                       suspicious=sum(r['suspicious'] == 'yes' for r in rows),
                       review_status_counts=dict(Counter(r['review_status'] for r in rows)),
                       review_result_counts=dict(Counter(r['review_result'] or 'chua_co_ket_luan'
                                                         for r in rows)),
                       processing_sizes=sorted({f'{r["width"]}x{r["height"]}' for r in rows}),
                       updated_at=gc.now(),
                       latest_operation=('mark_empty_results_passed' if mark_empty_results_passed
                                         else 'mark_manually_reviewed' if mark_pending_reviewed
                                         else 'sync_from_edited_overlays'),
                       note=gc.NOTE + ' Historical run counters describe the original GrabCut run.')
        prepare('summary.json', json_bytes(summary))
        report.update(synced_at=gc.now(), pixel_tolerance=tolerance,
                      overlays_modified=0, sources_modified=0,
                      note=('Pass results explicitly confirmed by user; masks and overlays unchanged.'
                            if mark_empty_results_passed else
                            'Review status explicitly confirmed by user; masks and overlays unchanged.'
                            if mark_pending_reviewed else
                            'Masks recovered from existing overlays; no GrabCut or automatic review approval.'))
        prepare('overlay_sync_report.json', json_bytes(report))
        # Refuse to publish if an editor changed any input while staging.
        if (output / 'manifest.csv').read_bytes() != manifest_before:
            raise RuntimeError('Manifest changed during synchronization')
        for path, expected in snapshots.items():
            if gc.sha256(path) != expected:
                raise RuntimeError(f'Input changed during synchronization: {path}')
        for relative, before in replacements.items():
            path = output / relative
            if (path.read_bytes() if path.exists() else None) != before:
                raise RuntimeError(f'Output changed during synchronization: {relative}')

        backup_dir = safe_path(output, 'overlay_sync_backups')
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f'{gc.now().replace(":", "-")}_{uuid.uuid4().hex[:8]}.zip'
        with zipfile.ZipFile(backup, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for relative, before in replacements.items():
                if before is not None:
                    archive.writestr(relative, before)
            archive.writestr('sync_transaction.json', json_bytes(dict(
                replacements=sorted(replacements),
                newly_created=[p for p, before in replacements.items() if before is None])))
        published = []
        try:
            for relative in replacements:
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_bytes(target, (stage / relative).read_bytes())
                published.append(relative)
        except BaseException:
            for relative in reversed(published):
                before = replacements[relative]
                if before is None:
                    (output / relative).unlink(missing_ok=True)
                else:
                    atomic_bytes(output / relative, before)
            raise
        report['backup'] = str(backup)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=gc.DEFAULT_OUTPUT)
    parser.add_argument('--source-dir', type=Path, default=gc.DEFAULT_INPUT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--verify', action='store_true')
    parser.add_argument('--pixel-tolerance', type=int, choices=(0, 1), default=0)
    parser.add_argument('--mark-pending-reviewed', action='store_true',
                        help='Explicitly set chua_duyet rows to da_duyet while syncing')
    parser.add_argument('--mark-empty-results-passed', action='store_true',
                        help='Explicitly set blank review_result cells to dat while syncing')
    args = parser.parse_args()
    if (args.mark_pending_reviewed or args.mark_empty_results_passed) and not args.apply:
        parser.error('review changes require --apply')
    with (args.output_dir / '.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = sync(args.output_dir, args.source_dir, args.apply, args.verify,
                      args.pixel_tolerance, args.mark_pending_reviewed,
                      args.mark_empty_results_passed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] or result.get('verified') is False else 0


if __name__ == '__main__':
    raise SystemExit(main())
