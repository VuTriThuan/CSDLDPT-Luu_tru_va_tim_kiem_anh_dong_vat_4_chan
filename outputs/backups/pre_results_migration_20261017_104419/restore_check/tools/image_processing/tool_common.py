"""Cài đặt, môi trường Python, đường dẫn và khóa thư mục trên macOS/Windows."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import struct
import subprocess
import sys


# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import PROJECT_ROOT, DATA_DIR, LEGACY_IMAGE_PROCESSING_DIR

TOOL_DIR = Path(__file__).resolve().parent
DATA = DATA_DIR
RUNTIME_DIR = LEGACY_IMAGE_PROCESSING_DIR
REQUIREMENTS = LEGACY_IMAGE_PROCESSING_DIR / "requirements.txt"


def configure_console():
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")


def runtime_environment():
    return RUNTIME_DIR / (".venv-windows" if sys.platform == "win32" else ".venv")


def runtime_python():
    environment = runtime_environment()
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def setup_environment():
    """Chỉ cài thư viện khi người dùng chủ động chạy --setup."""
    if not (3, 10) <= sys.version_info[:2] <= (3, 13) or struct.calcsize("P") != 8:
        raise RuntimeError("Cần Python 3.10–3.13 64-bit để cài đặt dự án.")
    import venv
    environment = runtime_environment()
    if Path(sys.prefix).resolve() != environment.resolve():
        print(f"Tạo môi trường Python tại {environment}", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    interpreter = str(runtime_python())
    subprocess.run([interpreter, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([interpreter, "-m", "pip", "install", "--only-binary=:all:",
                    "-r", str(REQUIREMENTS)], check=True)
    subprocess.run([interpreter, "-c", "import tkinter, numpy, PIL, onnxruntime, certifi"], check=True)
    print("Cài đặt hoàn tất. Có thể chạy auto_crop.py hoặc review_images.py.", flush=True)


def prepare_runtime(script):
    """Chạy trước các import thư viện ngoài để --setup dùng được trên máy mới."""
    configure_console()
    if "--setup" in sys.argv[1:]:
        if sys.argv[1:] != ["--setup"]:
            raise SystemExit("Chạy --setup riêng để cài đặt, sau đó chạy lại tool với các tùy chọn xử lý ảnh.")
        try:
            setup_environment()
        except KeyboardInterrupt:
            raise SystemExit(130)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            raise SystemExit(f"Cài đặt chưa hoàn tất: {exc}. Xem lỗi phía trên rồi chạy lại --setup.")
        raise SystemExit(0)
    interpreter = runtime_python()
    if interpreter.is_file() and Path(sys.prefix).resolve() != runtime_environment().resolve():
        try:
            result = subprocess.run([str(interpreter), "-X", "utf8", str(Path(script).resolve()),
                                     *sys.argv[1:]])
        except KeyboardInterrupt:
            raise SystemExit(130)
        except OSError as exc:
            raise SystemExit(f"Không mở được môi trường Python: {exc}. Chạy lại tool với --setup.")
        raise SystemExit(result.returncode)


@contextmanager
def folder_lock(folder):
    """Khóa tự nhả khi đóng tool hoặc tiến trình bị ngắt; không xóa file khóa."""
    with (folder / ".tool_anh.lock").open("a+b") as handle:
        if sys.platform == "win32":
            import msvcrt
            # Windows cho phép khóa một byte vượt cuối file, kể cả file rỗng.
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                raise RuntimeError("Tool cắt/duyệt khác đang dùng thư mục. Đóng tool đó trước.") from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Tool cắt/duyệt khác đang dùng thư mục. Đóng tool đó trước.") from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
