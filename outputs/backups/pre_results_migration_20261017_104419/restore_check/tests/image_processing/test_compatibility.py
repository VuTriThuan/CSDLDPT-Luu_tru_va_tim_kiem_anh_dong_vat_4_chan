"""Chạy từ root: bo_tool_anh_576x384/.venv/bin/python -m unittest discover -s tests/image_processing -v."""
import argparse
import builtins
from contextlib import redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import venv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
TOOL_DIR = PROJECT_ROOT / "tools/image_processing"

from PIL import Image
from tools.image_processing import auto_crop as crop
from tools.image_processing import review_images as review
from tools.image_processing import tool_common as common


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tool ảnh ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def child_lock(self, folder):
        code = (
            "import sys; from pathlib import Path; "
            f"sys.path.insert(0, {str(PROJECT_ROOT)!r}); "
            "from tools.image_processing.tool_common import folder_lock\n"
            "try:\n"
            " with folder_lock(Path(sys.argv[1])): print('locked')\n"
            "except RuntimeError: sys.exit(2)\n"
        )
        return subprocess.run([sys.executable, "-c", code, str(folder)],
                              capture_output=True, text=True, timeout=15)

    def test_native_lock_blocks_other_process_and_releases(self):
        with crop.folder_lock(self.root):
            self.assertEqual(self.child_lock(self.root).returncode, 2)
            with self.assertRaises(RuntimeError):
                with review.folder_lock(self.root):
                    pass
        self.assertEqual(self.child_lock(self.root).returncode, 0)

    def test_lock_releases_after_exception(self):
        with self.assertRaisesRegex(ValueError, "test"):
            with common.folder_lock(self.root):
                raise ValueError("test")
        self.assertEqual(self.child_lock(self.root).returncode, 0)

    def test_windows_adapter_unlocks_same_byte_after_exception(self):
        positions = []
        api = SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0)
        api.locking = Mock(side_effect=lambda fd, mode, size:
                           positions.append((mode, size, os.lseek(fd, 0, os.SEEK_CUR))))
        with patch.object(common, "sys", SimpleNamespace(platform="win32")), \
                patch.dict(sys.modules, {"msvcrt": api}):
            with self.assertRaises(ValueError):
                with common.folder_lock(self.root):
                    raise ValueError("test")
        self.assertEqual(positions, [(2, 1, 0), (0, 1, 0)])

    def test_windows_adapter_reports_busy_and_does_not_unlock_foreign_lock(self):
        api = SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0,
                              locking=Mock(side_effect=OSError(errno.EACCES, "locked")))
        with patch.object(common, "sys", SimpleNamespace(platform="win32")), \
                patch.dict(sys.modules, {"msvcrt": api}):
            with self.assertRaises(RuntimeError):
                with common.folder_lock(self.root):
                    self.fail("Must not enter a locked folder")
        self.assertEqual(api.locking.call_count, 1)

    def test_defaults_use_project_location(self):
        self.assertEqual(crop.DATA, PROJECT_ROOT / "data")
        self.assertEqual(review.DEFAULT_FOLDER, PROJECT_ROOT / "data/cropped_images_576x384")

    def test_setup_runs_before_optional_dependencies_are_imported(self):
        original_import = builtins.__import__

        def without_image_packages(name, *args, **kwargs):
            if name.split(".")[0] in {"PIL", "numpy", "certifi", "onnxruntime"}:
                raise ImportError("Simulated fresh Python installation")
            return original_import(name, *args, **kwargs)

        for name in ("auto_crop.py", "review_images.py"):
            with self.subTest(script=name), \
                    patch.object(sys, "argv", [name, "--setup"]), \
                    patch.object(common, "setup_environment") as setup, \
                    patch("builtins.__import__", side_effect=without_image_packages):
                with self.assertRaises(SystemExit) as result:
                    runpy.run_path(str(TOOL_DIR / name), run_name="__main__")
                self.assertEqual(result.exception.code, 0)
                setup.assert_called_once_with()

    def test_runtime_preserves_arguments_cwd_and_exit_status(self):
        tool = self.root / "thư mục tool"
        tool.mkdir()
        environment = tool / (".venv-windows" if sys.platform == "win32" else ".venv")
        venv.EnvBuilder(with_pip=False).create(environment)
        script = tool / "sample.py"
        script.write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "Path(__file__).with_suffix('.json').write_text(json.dumps({"
            "'args': sys.argv[1:], 'prefix': sys.prefix, 'cwd': os.getcwd()}), encoding='utf-8')\n"
            "sys.exit(7)\n", encoding="utf-8")
        args = [str(script), "--folder", "../data/ảnh mèo", "--limit", "30"]
        with patch.object(common, "RUNTIME_DIR", tool), patch.object(sys, "argv", args):
            with self.assertRaises(SystemExit) as result:
                common.prepare_runtime(script)
        self.assertEqual(result.exception.code, 7)
        received = json.loads(script.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(received["args"], args[1:])
        self.assertEqual(Path(received["prefix"]).resolve(), environment.resolve())
        self.assertEqual(Path(received["cwd"]).resolve(), Path.cwd().resolve())

    def test_runtime_does_not_restart_inside_target_environment(self):
        with patch.object(common, "runtime_environment", return_value=Path(sys.prefix)), \
                patch.object(common, "runtime_python", return_value=Path(sys.executable)), \
                patch.object(sys, "argv", ["auto_crop.py"]), \
                patch.object(common.subprocess, "run") as launch:
            common.prepare_runtime(TOOL_DIR / "auto_crop.py")
        launch.assert_not_called()

    def test_setup_failure_is_reported_as_failure(self):
        with patch.object(sys, "argv", ["auto_crop.py", "--setup"]), \
                patch.object(common, "setup_environment", side_effect=RuntimeError("install failed")):
            with self.assertRaisesRegex(SystemExit, "install failed"):
                common.prepare_runtime(TOOL_DIR / "auto_crop.py")

    def test_setup_cannot_be_combined_with_processing_options(self):
        with patch.object(sys, "argv", ["auto_crop.py", "--setup", "--force"]), \
                patch.object(common, "setup_environment") as setup:
            with self.assertRaises(SystemExit):
                common.prepare_runtime(TOOL_DIR / "auto_crop.py")
        setup.assert_not_called()

    def fixture(self):
        data = self.root / "Mac Desktop/BTL/data"
        source, output = data / "anh-chua-loc", data / "anh-da-cat-576x384"
        source.mkdir(parents=True)
        output.mkdir()
        config = {"size": [576, 384], "fill": 0.85, "threshold": 0.25, "model": "u2net"}
        state = crop.fresh_state(source)
        for name, status in [("ảnh mèo.jpg", "saved"), ("ảnh chó.jpg", "deleted")]:
            Image.new("RGB", (48, 32), "orange").save(source / name)
            state["images"][name] = {"signature": crop.signature(source / name),
                                     "status": status, "output": name, "config": config,
                                     "review_flip_count": 1, "warnings": []}
            if status == "saved":
                Image.new("RGB", (576, 384), "blue").save(output / name)
        return source, output, state

    def test_move_between_machines_preserves_review_despite_changed_timestamps(self):
        source, output, state = self.fixture()
        log = output / "_cat_tu_dong.json"
        crop.atomic_json(log, crop.make_state_portable(state, log, source))
        target = self.root / "Windows Desktop/CSDLDPT/BTL/data"
        shutil.copytree(source.parent, target)
        moved_source, moved_output = target / source.name, target / output.name
        before = (moved_output / "ảnh mèo.jpg").read_bytes()
        for image in moved_source.iterdir():
            st = image.stat()
            os.utime(image, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        args = argparse.Namespace(input=moved_source, output=moved_output, repair_borders=False,
                                  recursive=False, fill=0.85, threshold=0.25, model="u2net",
                                  force=False, limit=0)
        with patch.object(crop, "ensure_model", side_effect=AssertionError("Must not recrop")), \
                redirect_stdout(io.StringIO()):
            crop.run_batch(args)
        updated = json.loads((moved_output / log.name).read_text(encoding="utf-8"))
        self.assertEqual(updated["source"], str(moved_source))
        self.assertEqual(updated["source_relative"], "../anh-chua-loc")
        self.assertEqual(updated["images"]["ảnh chó.jpg"]["status"], "deleted")
        self.assertEqual(updated["images"]["ảnh mèo.jpg"]["review_flip_count"], 1)
        self.assertFalse((moved_output / "ảnh chó.jpg").exists())
        self.assertEqual((moved_output / "ảnh mèo.jpg").read_bytes(), before)
        self.assertEqual(updated["images"]["ảnh mèo.jpg"]["signature"],
                         crop.signature(moved_source / "ảnh mèo.jpg"))

    def test_portable_log_accepts_windows_or_mac_absolute_origin(self):
        source, output, state = self.fixture()
        log = output / "_cat_tu_dong.json"
        crop.make_state_portable(state, log, source)
        for origin in [r"C:\Users\User\Desktop\CSDLDPT\BTL\data\anh-chua-loc",
                       "/Users/User/Desktop/CSDLDPT/BTL/data/anh-chua-loc"]:
            with self.subTest(origin=origin):
                state["source"] = origin
                crop.atomic_json(log, state)
                self.assertEqual(crop.load_state(log, source)["source"], str(source))

    def test_different_source_is_rejected(self):
        source, output, state = self.fixture()
        log = output / "_cat_tu_dong.json"
        crop.atomic_json(log, crop.make_state_portable(state, log, source))
        other = source.with_name("different-source")
        other.mkdir()
        with self.assertRaises(ValueError):
            crop.load_state(log, other)

    def test_changed_content_with_same_size_is_not_treated_as_copied_file(self):
        image = self.root / "source.bin"
        image.write_bytes(b"original")
        record = {"signature": crop.signature(image)}
        self.assertTrue(crop.source_unchanged(image, record))
        old = image.stat()
        image.write_bytes(b"modified")
        os.utime(image, ns=(old.st_atime_ns, old.st_mtime_ns + 5_000_000_000))
        self.assertFalse(crop.source_unchanged(image, record))

    def test_review_flip_delete_undo_updates_portable_log(self):
        source, output, state = self.fixture()
        log = output / "_cat_tu_dong.json"
        crop.atomic_json(log, crop.make_state_portable(state, log, source))
        path = output / "ảnh mèo.jpg"
        before = path.read_bytes()
        with review.folder_lock(output):
            store = review.ReviewStore(output)
            store.flip(path)
            store.delete(path)
            self.assertFalse(path.exists())
            store.undo()
            store.undo()
            store.sync_report()
        self.assertEqual(path.read_bytes(), before)
        restored = json.loads(log.read_text(encoding="utf-8"))
        self.assertEqual(restored["source_relative"], "../anh-chua-loc")
        self.assertEqual(restored["images"], state["images"])

    def test_output_names_do_not_collide_by_case(self):
        state = {"images": {"Cat.png": {"output": "Cat.jpg"}}}
        self.assertEqual(crop.allocate_name(Path("cat.png"), self.root, {}, state).name, "cat_002.jpg")


if __name__ == "__main__":
    unittest.main()
