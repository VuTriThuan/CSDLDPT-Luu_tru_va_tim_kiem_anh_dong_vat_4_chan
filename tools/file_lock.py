"""Process-owned, exclusive, nonblocking file locks; lock files are never deleted."""
from contextlib import contextmanager
import errno
from pathlib import Path
import sys


class LockBusyError(BlockingIOError):
    """Another process owns the lock; permission/filesystem errors stay OSError."""


def _windows_lock(handle):
    # LockFileEx preserves Win32 error codes; CRT locking maps both access errors
    # and contention to EACCES, which cannot distinguish the required failures.
    import ctypes
    from ctypes import wintypes
    import msvcrt

    class Overlapped(ctypes.Structure):
        _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                    ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                    ('hEvent', wintypes.HANDLE)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    lock = kernel.LockFileEx
    lock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                     wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    lock.restype = wintypes.BOOL
    unlock = kernel.UnlockFileEx
    unlock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                       wintypes.DWORD, ctypes.POINTER(Overlapped)]
    unlock.restype = wintypes.BOOL
    native = msvcrt.get_osfhandle(handle.fileno())
    offset = Overlapped()  # Byte 0, even for an empty file.
    if not lock(native, 0x00000003, 0, 1, 0, ctypes.byref(offset)):
        error = ctypes.get_last_error()
        if error == 33:  # ERROR_LOCK_VIOLATION only; access denied is NOT busy.
            raise LockBusyError(errno.EWOULDBLOCK, 'Output is locked by another process')
        raise ctypes.WinError(error)

    def release():
        if not unlock(native, 0, 1, 0, ctypes.byref(offset)):
            raise ctypes.WinError(ctypes.get_last_error())
    return release


@contextmanager
def file_lock(path):
    """Never wait; close releases the OS lock even after an exception or exit."""
    with Path(path).open('a+b') as handle:
        if sys.platform == 'win32':
            release = _windows_lock(handle)
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {errno.EAGAIN, errno.EWOULDBLOCK}:
                    raise LockBusyError(exc.errno, f'Output is locked: {path}') from exc
                raise
            release = lambda: fcntl.flock(handle, fcntl.LOCK_UN)
        try:
            yield
        finally:
            release()
