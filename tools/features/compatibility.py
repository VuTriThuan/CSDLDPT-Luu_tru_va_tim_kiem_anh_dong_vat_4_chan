"""Explicit byte-level approval of the portable B400 implementation.

The policy is a reviewed release allowlist, not a way to bless arbitrary edits.
Changing an approved file requires a fresh code review and updated policy.
Existing artifacts retain their ORIGINAL identity and provenance.
"""
import json
from pathlib import Path
import platform
import struct

import cv2
import numpy as np
from PIL import __version__ as pillow_version

from tools.features import b400, inputs
from tools.project_paths import PROJECT_ROOT

POLICY_PATH = Path(__file__).with_name('compatibility.json')
SOURCE_FILES = (
    'tools/features/b400.py', 'tools/features/inputs.py', 'tools/features/storage.py',
    'tools/features/cli.py', 'tools/features/compatibility.py',
    'tools/features/publication.py', 'tools/file_lock.py', 'tools/project_paths.py',
    'tools/image_processing/tool_common.py', 'tools/validation/audit_images.py',
)


def current_code():
    return {name: inputs.sha256(PROJECT_ROOT/name) for name in SOURCE_FILES}


def runtime():
    return dict(python=platform.python_version(), numpy=np.__version__,
                opencv=cv2.__version__, pillow=pillow_version)


def feature_set():
    """New extractions identify actual bytes, including portability I/O helpers."""
    value = dict(descriptor=b400.configuration(), code_sha256=current_code(), runtime=runtime())
    value = json.loads(json.dumps(value))
    value['id'] = b400.digest_json(value)
    return value


def check_feature_set(saved):
    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    if policy['version'] != 1 or current_code() != policy['approved_code_sha256']:
        raise ValueError('Running B400 source bytes are not an approved portable revision; '
                         'check LF checkout and review code changes; no automatic rebuild')
    if (platform.python_implementation() != 'CPython' or struct.calcsize('P') != 8
            or platform.machine().lower() not in {'x86_64', 'amd64'}
            or runtime() != policy['runtime']):
        raise ValueError('B400 requires approved CPython x86-64 and exact pinned runtime versions')
    body = dict(saved)
    identifier = body.pop('id')
    if b400.digest_json(body) != identifier:
        raise ValueError('Saved feature set checksum differs')
    if saved['descriptor'] != json.loads(json.dumps(b400.configuration())):
        raise ValueError('Saved descriptor/formula/dimension order differs')
    if saved['runtime'] != runtime():
        raise ValueError('Saved B400 runtime differs from current pinned runtime')
    if saved == feature_set():
        return 'portable-byte-exact'
    # This digest binds the ENTIRE legacy descriptor, all four original source
    # hashes and the exact runtime. Matching only the name b400_v1 is insufficient.
    if identifier != policy['legacy_feature_set_id']:
        raise ValueError('Saved feature set is outside the approved compatibility scope')
    return 'legacy-io-compatible'
