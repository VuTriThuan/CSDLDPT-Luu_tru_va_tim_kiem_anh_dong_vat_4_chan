#!/usr/bin/env python3
"""Duyệt ảnh phủ và phân loại bằng A/S/D.

Chạy từ thư mục gốc dự án:
    .venv/bin/python tools/segmentation/review_overlays.py

Thêm --all để xem lại cả ảnh đã nằm trong các thư mục phân loại.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import GRABCUT_OUTPUT_DIR

from PIL import Image, ImageOps, ImageTk
import tkinter as tk
from tkinter import messagebox, ttk


DEFAULT_FOLDER = GRABCUT_OUTPUT_DIR / "overlays"
CATEGORIES = {"a": "accepted", "s": "needs_revision", "d": "redo"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def images_in(folder: Path) -> list[Path]:
    return [path for path in folder.iterdir()
            if path.is_file() and not path.is_symlink()
            and path.suffix.lower() in IMAGE_EXTENSIONS]


class ReviewSession:
    def __init__(self, folder: Path, review_all: bool = False):
        self.folder = folder
        self.review_all = review_all
        self.destinations = {key: folder / name for key, name in CATEGORIES.items()}
        for destination in self.destinations.values():
            if destination.is_symlink():
                raise ValueError(f"Thư mục phân loại là liên kết: {destination}")
            destination.mkdir(exist_ok=True)
        self.counts = {key: len(images_in(destination))
                       for key, destination in self.destinations.items()}
        self.files = images_in(folder)
        if review_all:
            for destination in self.destinations.values():
                self.files.extend(images_in(destination))
        self.files.sort(key=lambda path: (path.name.casefold(), str(path.parent)))
        self.index = 0
        self.history: list[tuple[Path, Path, int]] = []

    def current(self) -> Path | None:
        return self.files[self.index] if self.index < len(self.files) else None

    def classify(self, key: str) -> tuple[Path, Path]:
        source = self.current()
        if source is None:
            raise ValueError("Không còn ảnh để duyệt.")
        destination = self.destinations[key] / source.name
        if source != destination:
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"'{CATEGORIES[key]}' đã có ảnh cùng tên: {source.name}")
            source.rename(destination)
            for old_key, old_folder in self.destinations.items():
                if source.parent == old_folder:
                    self.counts[old_key] -= 1
                    break
            self.counts[key] += 1
        previous_index = self.index
        self.history.append((source, destination, previous_index))
        if self.review_all:
            self.files[self.index] = destination
            self.index += 1
        else:
            self.files.pop(self.index)
        return source, destination

    def undo(self) -> Path | None:
        if not self.history:
            return None
        source, destination, previous_index = self.history[-1]
        if source != destination:
            if source.exists() or source.is_symlink():
                raise FileExistsError(f"Không thể hoàn tác: đã có {source.name} ở thư mục cũ.")
            if not destination.is_file():
                raise FileNotFoundError(f"Không tìm thấy ảnh để hoàn tác: {destination}")
            destination.rename(source)
            for key, folder in self.destinations.items():
                if destination.parent == folder:
                    self.counts[key] -= 1
                if source.parent == folder:
                    self.counts[key] += 1
        self.history.pop()
        if self.review_all:
            self.files[previous_index] = source
            self.index = previous_index
        else:
            self.files.append(source)
            self.files.sort(key=lambda path: (path.name.casefold(), str(path.parent)))
            self.index = self.files.index(source)
        return source

    def step(self, amount: int) -> None:
        if self.files:
            self.index = max(0, min(len(self.files) - 1, self.index + amount))


class Viewer:
    def __init__(self, root: tk.Tk, session: ReviewSession):
        self.root = root
        self.session = session
        self.image: Image.Image | None = None
        self.photo = None
        self.last_key = ""
        self.last_key_time = 0.0
        self.held_keys: set[str] = set()
        self.release_jobs: dict[str, str] = {}
        self.status = tk.StringVar()
        self.note = tk.StringVar(value="A: đạt   •   S: cần sửa   •   D: làm lại   •   ←/→: chuyển ảnh   •   U: hoàn tác   •   Esc: thoát")
        root.title("Duyệt ảnh overlays")
        root.geometry("1100x780")
        root.minsize(700, 500)

        header = ttk.Frame(root, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="PHÂN LOẠI ẢNH OVERLAYS", font=("Helvetica", 17, "bold")).pack(anchor="w")
        ttk.Label(header, textvariable=self.status, wraplength=1050).pack(anchor="w", pady=(5, 0))
        self.canvas = tk.Canvas(root, bg="#202733", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12)
        footer = ttk.Frame(root, padding=12)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.note, wraplength=1050).pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(footer)
        buttons.pack(fill="x")
        for label, action in (
            ("◀ Trước", lambda: self.step(-1)),
            ("Sau ▶", lambda: self.step(1)),
            ("Đạt (A)", lambda: self.classify("a")),
            ("Cần sửa (S)", lambda: self.classify("s")),
            ("Làm lại (D)", lambda: self.classify("d")),
            ("Hoàn tác (U)", self.undo),
        ):
            ttk.Button(buttons, text=label, command=action).pack(side="left", padx=(0, 8))

        root.bind("<KeyPress>", self.on_key)
        root.bind("<KeyRelease>", self.on_key_release)
        self.canvas.bind("<Configure>", lambda _event: self.draw())
        self.load()

    def on_key(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key in CATEGORIES:
            release_job = self.release_jobs.pop(key, None)
            if release_job is not None:
                self.root.after_cancel(release_job)
            if key in self.held_keys:
                return
            self.held_keys.add(key)
            now = time.monotonic()
            if key == self.last_key and now - self.last_key_time < 0.4:
                return
            self.last_key, self.last_key_time = key, now
            self.classify(key)
        elif key == "u":
            self.undo()
        elif key == "left":
            self.step(-1)
        elif key == "right":
            self.step(1)
        elif key == "escape":
            self.root.destroy()

    def on_key_release(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key not in CATEGORIES or key not in self.held_keys:
            return
        previous_job = self.release_jobs.pop(key, None)
        if previous_job is not None:
            self.root.after_cancel(previous_job)

        def clear_key() -> None:
            self.held_keys.discard(key)
            self.release_jobs.pop(key, None)

        # Trên một số hệ, giữ phím tạo cặp KeyRelease/KeyPress liên tục.
        self.release_jobs[key] = self.root.after(120, clear_key)

    def load(self) -> None:
        self.image = None
        path = self.session.current()
        counts = self.session.counts
        summary = f"Đạt: {counts['a']}   •   Cần sửa: {counts['s']}   •   Làm lại: {counts['d']}"
        if path is None:
            hint = " Chạy lại với --all để xem ảnh đã phân loại." if not self.session.review_all else ""
            self.status.set(f"Đã duyệt hết ảnh. {summary}.{hint}")
            self.draw()
            return
        try:
            with Image.open(path) as image:
                self.image = ImageOps.exif_transpose(image).convert("RGB")
            category = next((name for name in CATEGORIES.values() if path.parent.name == name), "chưa phân loại")
            self.status.set(
                f"{self.session.index + 1}/{len(self.session.files)}   •   {path.name}   •   "
                f"{self.image.width} × {self.image.height}   •   {category}\n{summary}"
            )
        except Exception as exc:
            self.status.set(f"Không đọc được {path.name}: {exc}. Dùng ←/→ để chuyển ảnh.\n{summary}")
        self.draw()

    def draw(self) -> None:
        self.canvas.delete("all")
        if self.image is None:
            self.photo = None
            return
        preview = self.image.copy()
        preview.thumbnail(
            (max(1, self.canvas.winfo_width() - 20), max(1, self.canvas.winfo_height() - 20)),
            Image.Resampling.LANCZOS,
        )
        self.photo = ImageTk.PhotoImage(preview)
        self.canvas.create_image(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2,
                                 image=self.photo)

    def step(self, amount: int) -> None:
        self.session.step(amount)
        self.load()

    def classify(self, key: str) -> None:
        if self.session.current() is None:
            return
        try:
            source, destination = self.session.classify(key)
            self.load()
            self.note.set(f"Đã phân loại {source.name} → '{destination.parent.name}'. Bấm U để hoàn tác.")
        except Exception as exc:
            messagebox.showerror("Không thể phân loại", str(exc), parent=self.root)

    def undo(self) -> None:
        try:
            path = self.session.undo()
            if path is None:
                self.note.set("Không có thao tác nào để hoàn tác trong phiên này.")
                return
            self.load()
            self.note.set(f"Đã hoàn tác thao tác với {path.name}.")
        except Exception as exc:
            messagebox.showerror("Không thể hoàn tác", str(exc), parent=self.root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER, help="Thư mục overlays cần duyệt")
    parser.add_argument("--all", action="store_true", help="Xem lại cả ảnh đã phân loại")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Không tìm thấy thư mục: {folder}")
    try:
        root = tk.Tk()
        Viewer(root, ReviewSession(folder, review_all=args.all))
        root.mainloop()
    except Exception as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
