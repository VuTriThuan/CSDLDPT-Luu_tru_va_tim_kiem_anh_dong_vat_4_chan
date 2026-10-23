"""Publish an already verified, closed B400 staging directory on one filesystem."""
import ctypes
import os
from pathlib import Path
import shutil
import sys


def backup_path(output):
    output = Path(output)
    return output.with_name(f'.{output.name}-previous')


def recover_output(output):
    """Call under the stable sibling lock, before creating/opening output.

    A process interruption between the Windows renames leaves the whole old
    directory in a stable sibling, outside TemporaryDirectory's cleanup scope.
    If the second rename completed, output is the whole verified new set.
    """
    output = Path(output)
    backup = backup_path(output)
    if backup.is_symlink() or output.is_symlink():
        raise ValueError('Publication paths must not be symlinks')
    if backup.exists():
        if output.exists():
            shutil.rmtree(backup)
        else:
            backup.rename(output)


def replace_windows(stage, output):
    """Two renames, NOT an atomic exchange. Caller holds the sibling lock.

    Cooperating readers hold that same lock until all SQLite/NPZ handles close.
    Other readers must be stopped; Windows may refuse renaming an open file.
    Rollback failures retain the old set at the reported sibling backup path.
    """
    stage, output = Path(stage), Path(output)
    backup = backup_path(output)
    if backup.exists():
        raise FileExistsError(f'Unrecovered output backup: {backup}')
    output.rename(backup)
    try:
        stage.rename(output)
    except BaseException as exc:
        try:
            backup.rename(output)
        except OSError as rollback:
            raise OSError(f'Publication and rollback failed; old B400 retained at {backup}; '
                          f'retry after closing readers: {rollback}') from exc
        raise
    shutil.rmtree(backup)


def exchange_directories(first, second):
    if sys.platform == 'win32':
        return replace_windows(first, second)
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        call = libc.renamex_np
        call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = call(os.fsencode(first), os.fsencode(second), 2)
    elif sys.platform.startswith('linux'):
        call = libc.renameat2
        call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = call(-100, os.fsencode(first), -100, os.fsencode(second), 2)
    else:
        raise OSError(f'Unsupported publication platform: {sys.platform}')
    if result:
        raise OSError(ctypes.get_errno(), 'Atomic output exchange failed')
