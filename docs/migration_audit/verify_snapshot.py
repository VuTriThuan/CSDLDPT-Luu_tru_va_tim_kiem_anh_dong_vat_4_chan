"""Read-only verification of a restored BTL tree against baseline_inventory.json.

Usage: python3 verify_snapshot.py --root /path/to/restored_btl --inventory baseline_inventory.json
Optional: --archive project_snapshot.tar --archive-sha256 EXPECTED_HEX
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--archive-sha256')
    parser.add_argument('--allow-preparation', action='store_true',
                        help='Allow new docs/ and outputs/ artifacts when verifying the original workspace')
    args = parser.parse_args()
    if bool(args.archive) != bool(args.archive_sha256):
        parser.error('--archive and --archive-sha256 must be supplied together')
    if args.archive and sha256(args.archive) != args.archive_sha256:
        raise SystemExit('FAIL: archive SHA-256 mismatch')
    root = args.root.resolve()
    entries = json.loads(args.inventory.read_text())['entries']
    expected = {row['path'] for row in entries}
    actual = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        rel = Path(directory).relative_to(root)
        if args.allow_preparation and rel == Path('.'):
            dirs[:] = [name for name in dirs if name not in ['docs', 'outputs']]
        for name in dirs + files:
            actual.add((rel / name).as_posix())
    problems = []
    for row in entries:
        path = root / row['path']
        try:
            info = path.lstat()
        except FileNotFoundError:
            problems.append('missing: ' + row['path'])
            continue
        kind = ('symlink' if stat.S_ISLNK(info.st_mode) else
                'directory' if stat.S_ISDIR(info.st_mode) else
                'file' if stat.S_ISREG(info.st_mode) else 'other')
        if kind != row['kind']:
            problems.append('type: ' + row['path'])
            continue
        if stat.S_IMODE(info.st_mode) != row['mode']:
            problems.append('mode: ' + row['path'])
        # PAX timestamps are decimal nanoseconds; some Python/macOS stat conversions
        # round by less than a microsecond. Content hashes remain exact.
        if abs(info.st_mtime_ns - row['mtime_ns']) > 10000:
            problems.append('mtime: ' + row['path'])
        if kind == 'file' and (info.st_size != row['size'] or sha256(path) != row['sha256']):
            problems.append('content: ' + row['path'])
        if kind == 'symlink' and os.readlink(path) != row['link_target']:
            problems.append('link: ' + row['path'])
        if sys.platform == 'darwin' and row.get('xattr_sha256'):
            from restore_extended_attributes import attributes
            values = attributes(path)
            for name, expected_hash in row['xattr_sha256'].items():
                if name not in values or hashlib.sha256(values[name]).hexdigest() != expected_hash:
                    problems.append('extended_attribute: ' + row['path'] + ': ' + name)
    for path in sorted(actual - expected):
        problems.append('unexpected: ' + path)
    report = dict(verified=not problems, root=str(root), expected_entries=len(expected),
                  actual_entries=len(actual), problems=problems)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not problems else 1)


if __name__ == '__main__':
    main()
