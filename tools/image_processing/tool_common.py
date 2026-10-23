"""Cài đặt, môi trường Python, đường dẫn và khóa thư mục trên macOS/Windows."""
from contextlib import contextmanager
import os
from pathlib import Path
import struct
import subprocess
import sys


# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import PROJECT_ROOT, DATA_DIR
from tools.file_lock import file_lock

TOOL_DIR = Path(__file__).resolve().parent
DATA = DATA_DIR
RUNTIME_DIR = PROJECT_ROOT
REQUIREMENTS = PROJECT_ROOT / "requirements_image_tools.txt"


def configure_console():
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")


def runtime_environment():
    return RUNTIME_DIR / ".venv-image-tools"


def runtime_python():
    environment = runtime_environment()
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def setup_environment():
    """Chỉ cài thư viện khi người dùng chủ động chạy --setup."""
    if not (3, 10) <= sys.version_info[:2] <= (3, 13) or struct.calcsize("P") != 8:
        raise RuntimeError("Cần Python 3.10–3.13 64-bit để cài đặt dự án.")
    environment = runtime_environment()
    if Path(sys.prefix).resolve() != environment.resolve():
        print(f"Tạo môi trường Python tại {environment}", flush=True)
        # On macOS, sys._base_executable can still point into the calling venv.
        # Invoke the base installation so new launchers do not depend on that venv.
        base_python = Path(sys.base_prefix) / ("python.exe" if sys.platform == "win32" else "bin")
        if sys.platform != "win32":
            base_python = base_python / "python3"
        if not base_python.is_file():
            raise RuntimeError(f"Không tìm thấy Python nền: {base_python}. Tạo lại môi trường bằng Python hệ thống.")
        subprocess.run([str(base_python), "-m", "venv", str(environment)], check=True)
    interpreter = str(runtime_python())
    subprocess.run([interpreter, "-m", "pip", "install", "--only-binary=:all:",
                    "-r", str(REQUIREMENTS)], check=True)
    subprocess.run([interpreter, "-m", "pip", "check"], check=True)
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
    with file_lock(folder / '.tool_anh.lock'):
        yield
