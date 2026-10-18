"""Restore recorded macOS extended attributes to an already extracted, isolated tree.

Run only on the restore tree, before swapping it into the project's original path.
"""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys


def attributes(path):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.listxattr.restype = ctypes.c_ssize_t
    libc.getxattr.restype = ctypes.c_ssize_t
    raw_path = os.fsencode(path)
    length = libc.listxattr(raw_path, None, 0, 1)
    if length < 0:
        raise OSError(ctypes.get_errno(), 'listxattr', str(path))
    names = ctypes.create_string_buffer(length)
    if length and libc.listxattr(raw_path, names, length, 1) < 0:
        raise OSError(ctypes.get_errno(), 'listxattr', str(path))
    result = {}
    for name in names.raw.rstrip(b'\0').split(b'\0') if length else []:
        size = libc.getxattr(raw_path, name, None, 0, 0, 1)
        if size < 0:
            raise OSError(ctypes.get_errno(), 'getxattr', str(path))
        value = ctypes.create_string_buffer(size)
        if size and libc.getxattr(raw_path, name, value, size, 0, 1) < 0:
            raise OSError(ctypes.get_errno(), 'getxattr', str(path))
        result[os.fsdecode(name)] = value.raw
    return result


def restore(root, records, selected=None):
    if sys.platform != 'darwin':
        raise RuntimeError('This metadata restoration helper requires macOS')
    root = root.resolve()
    libc = ctypes.CDLL(None, use_errno=True)
    checked = 0
    for relative, values in records.items():
        if selected is not None and relative not in selected:
            continue
        parts = Path(relative)
        if parts.is_absolute() or '..' in parts.parts or relative in ['', '.']:
            raise ValueError('Unsafe relative path: ' + relative)
        path = root / parts
        if not path.parent.resolve().is_relative_to(root):
            raise ValueError('Parent escapes restore tree: ' + relative)
        path.lstat()
        for name, encoded in values.items():
            value = base64.b64decode(encoded, validate=True)
            if attributes(path).get(name) != value:
                buffer = ctypes.create_string_buffer(value)
                if libc.setxattr(os.fsencode(path), os.fsencode(name), buffer, len(value), 0, 1) < 0:
                    raise OSError(ctypes.get_errno(), 'setxattr', str(path))
            if attributes(path).get(name) != value:
                raise RuntimeError('Attribute mismatch: ' + relative + ': ' + name)
            checked += 1
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--attributes', type=Path, required=True)
    parser.add_argument('--inventory', type=Path,
                        help='Also restore directory mtimes after extraction into existing directories')
    args = parser.parse_args()
    count = restore(args.root, json.loads(args.attributes.read_text()))
    directories = 0
    if args.inventory:
        root = args.root.resolve()
        entries = json.loads(args.inventory.read_text())['entries']
        for row in sorted(entries, key=lambda r: len(Path(r['path']).parts), reverse=True):
            if row['kind'] != 'directory':
                continue
            relative = Path(row['path'])
            if relative.is_absolute() or '..' in relative.parts or str(relative) == '.':
                raise ValueError('Unsafe inventory path')
            path = root / relative
            if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_dir():
                raise ValueError('Invalid restore directory: ' + str(relative))
            info = path.stat()
            os.utime(path, ns=(info.st_atime_ns, row['mtime_ns']))
            directories += 1
    print(json.dumps(dict(verified=True, extended_attributes_restored_or_verified=count,
                          directory_timestamps_restored=directories)))


if __name__ == '__main__':
    main()
