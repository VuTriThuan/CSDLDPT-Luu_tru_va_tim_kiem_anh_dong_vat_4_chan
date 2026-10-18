#!/usr/bin/env python3
"""Verify split backups and reconstruct their original files without overwriting."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f'Path outside backup directory: {relative}')
    return path


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def restore(root, verify_only=False):
    manifest = json.loads((root / 'parts-manifest.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unsupported parts manifest version')
    for entry in manifest['files']:
        target = safe_path(root, entry['path'])
        if not verify_only and target.exists():
            if target.stat().st_size != entry['size_bytes'] or file_hash(target) != entry['sha256']:
                raise ValueError(f'Existing file differs; left unchanged: {target}')
            print(f"Already restored, SHA-256 OK: {entry['path']}", flush=True)
            continue
        temporary = None
        output = None
        try:
            if not verify_only:
                target.parent.mkdir(parents=True, exist_ok=True)
                output = tempfile.NamedTemporaryFile(mode='wb', dir=target.parent, prefix=target.name + '.restoring-', delete=False)
                temporary = Path(output.name)
            combined = hashlib.sha256()
            total = 0
            for part in entry['parts']:
                source = safe_path(root, part['path'])
                if source.stat().st_size != part['size_bytes']:
                    raise ValueError(f'Part size mismatch: {source}')
                digest = hashlib.sha256()
                with source.open('rb') as stream:
                    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        digest.update(block)
                        combined.update(block)
                        total += len(block)
                        if output is not None:
                            output.write(block)
                if digest.hexdigest() != part['sha256']:
                    raise ValueError(f'Part SHA-256 mismatch: {source}')
            if total != entry['size_bytes'] or combined.hexdigest() != entry['sha256']:
                raise ValueError(f"Combined file mismatch: {entry['path']}")
            if output is not None:
                output.flush()
                os.fsync(output.fileno())
                output.close()
                # Linking fails if the destination appeared meanwhile: never overwrite.
                os.link(temporary, target)
            label = 'Verified all parts' if verify_only else 'Restored'
            print(f"{label}, SHA-256 OK: {entry['path']}", flush=True)
        finally:
            if output is not None and not output.closed:
                output.close()
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Verify every part and combined SHA-256 without writing files.')
    args = parser.parse_args()
    try:
        restore(Path(__file__).resolve().parent, args.verify_only)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
