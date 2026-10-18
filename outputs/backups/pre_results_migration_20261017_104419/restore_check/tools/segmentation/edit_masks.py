#!/usr/bin/env python3
"""Chỉnh mask tương tác: tô giữ con vật / loại nền, GrabCut, lưu vào đạt.

    python3 tools/segmentation/edit_masks.py

Ảnh cần sửa chỉ dùng để chọn hàng đợi. GrabCut luôn chạy trên ảnh gốc.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageTk
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError as exc:
    if exc.name == "cv2":
        raise SystemExit(
            "Thiếu OpenCV trong Python đang chạy. Cài vào đúng môi trường hiện tại bằng:\n"
            "python3 -m pip install 'opencv-python-headless==4.11.0.86'"
        ) from exc
    raise SystemExit(f"Thiếu thư viện: {exc}. Cài Tkinter, NumPy và Pillow cho Python đang chạy.") from exc

from tools.segmentation import run_grabcut as gc

UNMARKED = 255
KEEP = cv2.GC_FGD
REMOVE = cv2.GC_BGD


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_bytes(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return stream.getvalue()


def atomic_bytes(path: Path, data: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=".mask-edit-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def create_bytes(path: Path, data: bytes) -> None:
    """Publish a complete file without overwriting an existing destination."""
    fd, name = tempfile.mkstemp(prefix=".mask-edit-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def refine_mask(image, mask, strokes, iterations=5):
    """Existing mask gives probable labels; painted strokes give hard labels."""
    if image.shape[:2] != mask.shape or mask.shape != strokes.shape:
        raise ValueError("Kích thước ảnh, mask và nét tô không khớp.")
    labels = np.where(mask != 0, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
    labels[strokes == KEEP] = cv2.GC_FGD
    labels[strokes == REMOVE] = cv2.GC_BGD
    foreground = (labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD)
    if int(foreground.sum()) < 5:
        raise ValueError("Chưa đủ vùng con vật. Tô thêm vùng 'Giữ con vật' rồi chạy lại.")
    if int((~foreground).sum()) < 5:
        raise ValueError("Chưa đủ vùng nền. Tô thêm vùng 'Loại nền' rồi chạy lại.")
    cv2.setRNGSeed(0)
    cv2.grabCut(image, labels, None, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), iterations, cv2.GC_INIT_WITH_MASK)
    result = np.where((labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    if not np.any(result) or not np.any(result == 0):
        raise ValueError("Mask đang rỗng hoặc phủ toàn ảnh. Tô thêm vùng giữ / loại rồi chạy lại.")
    return result


def mask_from_overlay(image, overlay, fallback_mask):
    """Recover 0/255 labels from a PNG made by make_overlay."""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    if overlay.shape != rgb.shape:
        raise ValueError("Ảnh phủ không cùng kích thước với ảnh nguồn.")
    tinted = (0.35 * rgb + 0.65 * np.array([255, 0, 0])).astype(np.uint8)
    matches_source = np.all(overlay == rgb, axis=2)
    matches_tint = np.all(overlay == tinted, axis=2)
    unknown = ~(matches_source | matches_tint)
    if np.any(unknown):
        raise ValueError(
            f"Ảnh phủ có {int(np.count_nonzero(unknown))} pixel không khớp ảnh nguồn hoặc màu phủ. "
            "Cần kiểm tra ảnh trước khi chạy GrabCut."
        )
    recovered = np.where(matches_source, 255, 0).astype(np.uint8)
    ambiguous = matches_source & matches_tint
    recovered[ambiguous] = fallback_mask[ambiguous]
    return recovered


class MaskDocument:
    def __init__(self, image, mask, overlay_path, mask_path, source_path, row,
                 mask_before, overlay_before, mask_from_current_overlay=False):
        self.image = image
        self.initial_mask = mask.copy()
        self.mask = mask.copy()
        self.strokes = np.full(mask.shape, UNMARKED, np.uint8)
        self.applied_strokes = None
        self.overlay_path, self.mask_path, self.source_path = overlay_path, mask_path, source_path
        self.row = dict(row)
        self.mask_before, self.overlay_before = mask_before, overlay_before
        self.source_hash = gc.sha256(source_path)
        self.mask_from_current_overlay = mask_from_current_overlay
        self.history = []

    @property
    def ready(self):
        return self.applied_strokes is not None and np.array_equal(self.strokes, self.applied_strokes)

    @property
    def dirty(self):
        return self.applied_strokes is not None or np.any(self.strokes != UNMARKED)

    def checkpoint(self):
        self.history.append((self.mask.copy(), self.strokes.copy(),
                             None if self.applied_strokes is None else self.applied_strokes.copy()))
        self.history = self.history[-30:]

    def paint(self, start, end, radius, label):
        cv2.line(self.strokes, start, end, int(label), 2 * radius + 1)
        cv2.circle(self.strokes, end, radius, int(label), -1)

    def apply_result(self, result):
        self.checkpoint()
        self.mask = result
        self.applied_strokes = self.strokes.copy()

    def undo(self):
        if self.history:
            self.mask, self.strokes, self.applied_strokes = self.history.pop()

    def reset(self):
        self.checkpoint()
        self.mask = self.initial_mask.copy()
        self.strokes.fill(UNMARKED)
        self.applied_strokes = None


class MaskRepository:
    def __init__(self, output: Path, source: Path):
        self.output, self.source = output.resolve(), source.resolve()
        if (self.output == self.source or self.output in self.source.parents
                or self.source in self.output.parents):
            raise ValueError("Thư mục nguồn và đầu ra phải tách biệt.")
        self.pending_dir = self.output / "overlays" / "cần sửa"
        self.accepted_dir = self.output / "overlays" / "đạt"
        self.manifest = self.output / "manifest.csv"
        if not self.source.is_dir() or not self.pending_dir.is_dir():
            raise ValueError("Không tìm thấy thư mục ảnh gốc hoặc overlays/cần sửa.")
        self.safe_output("manifest.csv")
        self.safe_output("overlays/cần sửa")
        self.safe_output("overlays/đạt")
        self.read_manifest()

    def safe_output(self, relative):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Đường dẫn đầu ra không hợp lệ: {relative}")
        path = self.output / relative
        if not path.resolve().is_relative_to(self.output):
            raise ValueError(f"Đường dẫn ra ngoài thư mục kết quả: {relative}")
        for parent in (path, *path.parents):
            if parent == self.output:
                break
            if parent.is_symlink():
                raise ValueError(f"Đầu ra không được là liên kết: {parent}")
        return path

    def read_manifest(self):
        data = self.manifest.read_bytes()
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        rows = list(reader)
        required = {"filename", "mask_path", "overlay_path", "width", "height", "review_status"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("manifest.csv thiếu cột cần thiết.")
        if len({row["filename"] for row in rows}) != len(rows):
            raise ValueError("manifest.csv có tên ảnh trùng nhau.")
        return data, reader.fieldnames, rows

    def pending(self):
        return sorted((path for path in self.pending_dir.iterdir()
                       if path.is_file() and not path.is_symlink() and path.suffix.lower() == ".png"),
                      key=lambda path: path.name.casefold())

    def load(self, overlay_path: Path):
        if overlay_path.is_symlink():
            raise ValueError("Chỉ mở ảnh trực tiếp trong overlays/cần sửa.")
        overlay_path = overlay_path.resolve()
        if overlay_path.parent != self.pending_dir:
            raise ValueError("Chỉ mở ảnh trực tiếp trong overlays/cần sửa.")
        _, _, rows = self.read_manifest()
        matches = [row for row in rows if row["filename"] + ".png" == overlay_path.name]
        if len(matches) != 1:
            raise ValueError(f"Không ghép được ảnh với manifest: {overlay_path.name}")
        row = matches[0]
        if Path(row["filename"]).name != row["filename"]:
            raise ValueError("Tên ảnh nguồn không hợp lệ.")
        source_path = self.source / row["filename"]
        mask_path = self.safe_output(row["mask_path"])
        if source_path.is_symlink():
            raise ValueError("Ảnh nguồn không được là liên kết.")
        if row.get("source_sha256") and gc.sha256(source_path) != row["source_sha256"]:
            raise ValueError("Ảnh nguồn đã thay đổi so với manifest.")
        mask_before, overlay_before = mask_path.read_bytes(), overlay_path.read_bytes()
        if row.get("mask_sha256") and digest(mask_before) != row["mask_sha256"]:
            raise ValueError("Mask đã thay đổi so với manifest; cần kiểm tra trước khi sửa.")
        with Image.open(io.BytesIO(mask_before)) as saved:
            mask = np.array(saved.convert("L"))
        width, height = int(row["width"]), int(row["height"])
        if mask.shape != (height, width) or not set(np.unique(mask)).issubset({0, 255}):
            raise ValueError("Mask không phải ảnh nhị phân đúng kích thước.")
        image, sw, sh = gc.read_image(source_path)
        if (sw, sh) != (width, height):
            image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
        with Image.open(io.BytesIO(overlay_before)) as saved_overlay:
            overlay = np.array(saved_overlay.convert("RGB"))
        from_overlay = not np.array_equal(overlay, gc.make_overlay(image, mask))
        if from_overlay:
            mask = mask_from_overlay(image, overlay, mask)
        return MaskDocument(image, mask, overlay_path, mask_path, source_path, row,
                            mask_before, overlay_before, from_overlay)

    def save(self, document: MaskDocument):
        if not document.ready:
            raise ValueError("Chạy lại GrabCut với các nét tô hiện tại trước khi lưu.")
        if not np.any(document.mask) or not np.any(document.mask == 0):
            raise ValueError("Không lưu mask rỗng hoặc phủ toàn ảnh.")
        if (document.overlay_path.read_bytes() != document.overlay_before
                or document.mask_path.read_bytes() != document.mask_before
                or gc.sha256(document.source_path) != document.source_hash):
            raise ValueError("Ảnh hoặc mask đã bị tiến trình khác thay đổi. Mở lại ảnh trước khi lưu.")
        manifest_before, fields, rows = self.read_manifest()
        row = next((row for row in rows if row["filename"] == document.row["filename"]), None)
        if row != document.row:
            raise ValueError("Dòng manifest đã thay đổi. Mở lại ảnh trước khi lưu.")
        self.safe_output("overlays/đạt")
        self.accepted_dir.mkdir(exist_ok=True)
        destination = self.accepted_dir / document.overlay_path.name
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Thư mục đạt đã có ảnh cùng tên: {destination.name}")
        mask_after = png_bytes(document.mask)
        overlay_after = png_bytes(gc.make_overlay(document.image, document.mask))
        before_row = dict(row)
        row.update(gc.mask_statistics(document.mask))
        row.update(overlay_path=destination.relative_to(self.output).as_posix(),
                   mask_sha256=digest(mask_after), overlay_sha256=digest(overlay_after),
                   status="success", review_status="da_duyet", review_result="dat",
                   error="", processed_at=gc.now())
        # A new mask method may omit optional GrabCut statistics in its manifest.
        fields = list(dict.fromkeys([*fields, *row]))
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        manifest_after = stream.getvalue().encode("utf-8")

        backup_root = self.safe_output("manual_edits")
        backup_root.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_root / f"{stamp}_{uuid.uuid4().hex[:12]}"
        backup.mkdir()
        create_bytes(backup / "mask_before.png", document.mask_before)
        create_bytes(backup / "overlay_before.png", document.overlay_before)
        create_bytes(backup / "scribbles.png", png_bytes(document.strokes))
        record = dict(state="prepared", filename=document.row["filename"], saved_at=gc.now(),
                      opencv_version=cv2.__version__, numpy_version=np.__version__,
                      overlay_before=document.overlay_path.relative_to(self.output).as_posix(),
                      overlay_after=destination.relative_to(self.output).as_posix(),
                      mask_path=document.mask_path.relative_to(self.output).as_posix(),
                      manifest_before=before_row, manifest_after=dict(row),
                      scribble_values={"0": "loại nền", "1": "giữ con vật", "255": "chưa tô"})

        def record_state(state):
            record["state"] = state
            atomic_bytes(backup / "record.json", json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"))

        record_state("prepared")
        mask_written = manifest_written = destination_created = source_removed = False
        try:
            create_bytes(destination, overlay_after)
            destination_created = True
            atomic_bytes(document.mask_path, mask_after)
            mask_written = True
            atomic_bytes(self.manifest, manifest_after)
            manifest_written = True
            document.overlay_path.unlink()
            source_removed = True
            record_state("saved")
        except Exception as exc:
            failures = []
            for required, action in (
                (mask_written, lambda: atomic_bytes(document.mask_path, document.mask_before)),
                (manifest_written, lambda: atomic_bytes(self.manifest, manifest_before)),
                (source_removed, lambda: create_bytes(document.overlay_path, document.overlay_before)),
                (destination_created, lambda: destination.unlink()),
            ):
                if required:
                    try:
                        action()
                    except Exception as rollback_error:
                        failures.append(str(rollback_error))
            try:
                record_state("needs_recovery" if failures else "rolled_back")
            except OSError as log_error:
                failures.append(str(log_error))
            if failures:
                raise RuntimeError(f"Lưu lỗi: {exc}. Bản sao phục hồi tại {backup}. " + "; ".join(failures)) from exc
            raise
        return destination, backup


@contextmanager
def output_lock(output: Path):
    with (output / ".run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Có công cụ tạo / chỉnh mask khác đang dùng thư mục kết quả.") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def fit_image(canvas_width, canvas_height, image_width, image_height):
    scale = min(max(1, canvas_width - 20) / image_width,
                max(1, canvas_height - 20) / image_height)
    width, height = max(1, round(image_width * scale)), max(1, round(image_height * scale))
    return (canvas_width - width) / 2, (canvas_height - height) / 2, width, height


class MaskEditor:
    def __init__(self, root: tk.Tk, repository: MaskRepository):
        self.root, self.repository = root, repository
        self.files = repository.pending()
        self.index = 0
        self.document = None
        self.photos = {}
        self.transform = None
        self.last_point = None
        self.stroke_label = None
        self.future = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.mode = tk.StringVar(value="keep")
        self.radius = tk.IntVar(value=8)
        self.iterations = tk.IntVar(value=5)
        self.view = tk.StringVar(value="Ảnh phủ")
        self.status = tk.StringVar()
        self.note = tk.StringVar(value="F: giữ con vật • B: loại nền • E: tẩy nét tô • G: GrabCut • S: lưu & chuyển đạt • U: hoàn tác")
        root.title("Chỉnh mask GrabCut • cần sửa → đạt")
        root.geometry("1320x850")
        root.minsize(1000, 650)
        header = ttk.Frame(root, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="CHỈNH MASK TƯƠNG TÁC", font=("Helvetica", 17, "bold")).pack(anchor="w")
        ttk.Label(header, textvariable=self.status, wraplength=1250).pack(anchor="w", pady=(5, 0))
        toolbar = ttk.Frame(root, padding=(12, 0, 12, 8))
        toolbar.pack(fill="x")
        for text, value in (("Giữ con vật (F)", "keep"), ("Loại nền (B)", "remove"), ("Tẩy nét tô (E)", "erase")):
            ttk.Radiobutton(toolbar, text=text, variable=self.mode, value=value).pack(side="left", padx=(0, 12))
        ttk.Label(toolbar, text="Bán kính cọ (px):").pack(side="left")
        tk.Scale(toolbar, from_=1, to=50, orient="horizontal", variable=self.radius,
                 length=140, highlightthickness=0).pack(side="left", padx=(0, 12))
        ttk.Label(toolbar, text="Số vòng GrabCut:").pack(side="left")
        ttk.Spinbox(toolbar, from_=1, to=20, textvariable=self.iterations, width=4).pack(side="left", padx=5)

        panels = ttk.Frame(root, padding=(12, 0))
        panels.pack(fill="both", expand=True)
        panels.columnconfigure((0, 1), weight=1, uniform="panels")
        panels.rowconfigure(1, weight=1)
        ttk.Label(panels, text="Ảnh gốc: tô xanh lá để giữ, xanh dương để loại").grid(row=0, column=0, sticky="w", pady=5)
        viewbar = ttk.Frame(panels)
        viewbar.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ttk.Label(viewbar, text="Ảnh phủ / kết quả:").pack(side="left")
        selector = ttk.Combobox(viewbar, textvariable=self.view, state="readonly", width=14,
                                values=("Ảnh phủ", "Con vật", "Mask"))
        selector.pack(side="left", padx=8)
        selector.bind("<<ComboboxSelected>>", lambda _e: self.redraw())
        self.left = tk.Canvas(panels, bg="#202733", highlightthickness=0, cursor="crosshair")
        self.right = tk.Canvas(panels, bg="#202733", highlightthickness=0)
        self.left.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        self.right.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        for canvas in (self.left, self.right):
            canvas.bind("<Configure>", lambda _e: self.redraw())
        self.left.bind("<ButtonPress-1>", self.begin_stroke)
        self.left.bind("<B1-Motion>", self.continue_stroke)
        self.left.bind("<ButtonRelease-1>", self.end_stroke)
        self.left.bind("<Motion>", self.draw_cursor)
        self.left.bind("<Leave>", lambda _e: self.left.delete("cursor"))
        footer = ttk.Frame(root, padding=12)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.note, wraplength=1250).pack(anchor="w", pady=(0, 8))
        actions = ttk.Frame(footer)
        actions.pack(fill="x")
        self.buttons = []
        for text, command in (("◀ Trước", lambda: self.navigate(-1)), ("Bỏ qua / Sau ▶", lambda: self.navigate(1)),
                              ("Hoàn tác (U)", self.undo), ("Khôi phục ban đầu", self.reset),
                              ("Chạy GrabCut (G)", self.run_grabcut)):
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side="left", padx=(0, 8))
            self.buttons.append(button)
        self.save_button = ttk.Button(actions, text="Lưu & chuyển đạt (S)", command=self.save)
        self.save_button.pack(side="right")
        root.bind("<KeyPress>", self.on_key)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.load_current()
        root.after(100, self.left.focus_set)

    @property
    def busy(self):
        return self.future is not None

    def load_current(self):
        self.document = None
        self.last_point = None
        self.stroke_label = None
        if self.files:
            self.index = min(self.index, len(self.files) - 1)
            try:
                self.document = self.repository.load(self.files[self.index])
                if self.document.mask_from_current_overlay:
                    self.note.set("Ảnh phủ hiện tại khác mask cũ. Tool đã lấy mask khởi đầu từ ảnh phủ để khung kết quả khớp tệp trên đĩa. Tô nét rồi bấm G.")
                else:
                    self.note.set("Tô vài nét bên trong con vật và phần nền bị giữ nhầm, bấm G rồi kiểm tra kết quả bên phải.")
            except Exception as exc:
                self.note.set(f"Không mở được {self.files[self.index].name}: {exc}. Bấm Sau để bỏ qua.")
        else:
            self.note.set("Không còn ảnh trong 'cần sửa'. Các ảnh đã lưu nằm trong 'đạt'.")
        self.update_status()
        self.redraw()

    def update_status(self):
        document = self.document
        if document is None:
            self.status.set(f"Còn {len(self.files)} ảnh trong 'cần sửa'.")
        else:
            height, width = document.mask.shape
            state = "Đang chạy GrabCut…" if self.busy else ("Có thể lưu" if document.ready else "Tô nét và chạy GrabCut")
            source_note = " • mask lấy từ ảnh phủ hiện tại" if document.mask_from_current_overlay else ""
            self.status.set(f"{self.index + 1}/{len(self.files)} • {document.row['filename']} • {width} × {height} • {state}{source_note}")
        for button in self.buttons:
            button.configure(state="disabled" if self.busy else "normal")
        self.save_button.configure(state="normal" if document is not None and document.ready and not self.busy else "disabled")

    def draw_array(self, canvas, array):
        height, width = array.shape[:2]
        box = fit_image(canvas.winfo_width(), canvas.winfo_height(), width, height)
        left, top, shown_width, shown_height = box
        photo = ImageTk.PhotoImage(Image.fromarray(array).resize((shown_width, shown_height), Image.Resampling.LANCZOS))
        self.photos[canvas] = photo
        canvas.create_image(left, top, anchor="nw", image=photo, tags="image")
        return box

    def redraw(self):
        for canvas in (self.left, self.right):
            canvas.delete("all")
        self.transform = None
        if self.document is None:
            self.photos.clear()
            return
        document = self.document
        rgb = cv2.cvtColor(document.image, cv2.COLOR_BGR2RGB)
        annotated = rgb.copy()
        for label, color in ((KEEP, [30, 255, 80]), (REMOVE, [40, 120, 255])):
            selected = document.strokes == label
            annotated[selected] = (0.3 * rgb[selected] + 0.7 * np.array(color)).astype(np.uint8)
        self.transform = self.draw_array(self.left, annotated)
        if self.view.get() == "Mask":
            result = document.mask
        elif self.view.get() == "Con vật":
            result = rgb.copy()
            result[document.mask == 0] = (235, 235, 235)
        else:
            result = gc.make_overlay(document.image, document.mask)
        self.draw_array(self.right, result)

    def image_point(self, event):
        if self.document is None or self.transform is None:
            return None
        left, top, width, height = self.transform
        if not (left <= event.x < left + width and top <= event.y < top + height):
            return None
        image_height, image_width = self.document.mask.shape
        return min(image_width - 1, int((event.x - left) * image_width / width)), \
            min(image_height - 1, int((event.y - top) * image_height / height))

    def draw_cursor(self, event):
        self.left.delete("cursor")
        if self.transform is None or self.image_point(event) is None:
            return
        radius = self.radius.get() * self.transform[2] / self.document.mask.shape[1]
        color = {"keep": "#32ff70", "remove": "#489aff", "erase": "#ffffff"}[self.mode.get()]
        self.left.create_oval(event.x - radius, event.y - radius, event.x + radius, event.y + radius,
                              outline=color, width=2, tags="cursor")

    def begin_stroke(self, event):
        if self.busy or self.document is None:
            return
        self.left.focus_set()
        point = self.image_point(event)
        if point is None:
            return
        self.document.checkpoint()
        self.stroke_label = {"keep": KEEP, "remove": REMOVE, "erase": UNMARKED}[self.mode.get()]
        self.last_point = point
        self.continue_stroke(event)

    def continue_stroke(self, event):
        if self.busy or self.stroke_label is None or self.document is None:
            return
        point = self.image_point(event)
        if point is None:
            self.last_point = None
            return
        self.document.paint(self.last_point or point, point, self.radius.get(), self.stroke_label)
        self.last_point = point
        self.redraw()
        self.draw_cursor(event)
        self.update_status()

    def end_stroke(self, _event=None):
        self.last_point = None
        self.stroke_label = None

    def run_grabcut(self):
        if self.busy or self.document is None:
            return
        try:
            iterations = self.iterations.get()
            if not 1 <= iterations <= 20:
                raise ValueError("Số vòng GrabCut phải từ 1 đến 20.")
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Số vòng không hợp lệ", str(exc), parent=self.root)
            return
        self.end_stroke()
        document = self.document
        self.future = self.executor.submit(refine_mask, document.image.copy(), document.mask.copy(),
                                           document.strokes.copy(), iterations)
        self.note.set("Đang tính lại mask. Chờ kết quả để kiểm tra trước khi lưu.")
        self.update_status()
        self.root.after(80, self.poll_result)

    def poll_result(self):
        if not self.future.done():
            self.root.after(80, self.poll_result)
            return
        future, self.future = self.future, None
        try:
            self.document.apply_result(future.result())
            self.note.set("Đã cập nhật kết quả bên phải. Tô thêm rồi chạy G nếu cần; bấm S để lưu và chuyển sang đạt.")
        except Exception as exc:
            messagebox.showerror("Không chạy được GrabCut", str(exc), parent=self.root)
            self.note.set("Tô thêm nét giữ con vật / loại nền rồi thử chạy lại.")
        self.update_status()
        self.redraw()

    def save(self):
        if self.busy or self.document is None:
            return
        if not self.document.ready:
            self.note.set("Chạy GrabCut (G) với các nét tô hiện tại trước khi lưu.")
            return
        self.end_stroke()
        try:
            destination, _backup = self.repository.save(self.document)
        except Exception as exc:
            messagebox.showerror("Không lưu được", str(exc), parent=self.root)
            return
        self.files.pop(self.index)
        self.load_current()
        self.note.set(f"Đã lưu mask và chuyển {destination.name} sang 'đạt'. Bản trước khi sửa nằm trong manual_edits/.")

    def may_discard(self):
        return (self.document is None or not self.document.dirty or messagebox.askyesno(
            "Bỏ thay đổi chưa lưu?", "Ảnh đang có nét tô hoặc kết quả chưa lưu. Bỏ các thay đổi này?", parent=self.root))

    def navigate(self, step):
        if self.busy or not self.files:
            return
        next_index = max(0, min(len(self.files) - 1, self.index + step))
        if next_index == self.index or not self.may_discard():
            return
        self.index = next_index
        self.load_current()

    def undo(self):
        if not self.busy and self.document is not None:
            self.end_stroke()
            self.document.undo()
            self.update_status()
            self.redraw()

    def reset(self):
        if not self.busy and self.document is not None:
            self.end_stroke()
            self.document.reset()
            self.update_status()
            self.redraw()

    def on_key(self, event):
        if self.busy or isinstance(event.widget, (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)):
            return
        key = event.keysym.lower()
        if key in ("f", "b", "e"):
            self.mode.set({"f": "keep", "b": "remove", "e": "erase"}[key])
        else:
            action = {"g": self.run_grabcut, "s": self.save, "u": self.undo,
                      "left": lambda: self.navigate(-1), "right": lambda: self.navigate(1)}.get(key)
            if action:
                action()

    def close(self):
        if self.busy:
            self.note.set("Chờ GrabCut chạy xong trước khi đóng cửa sổ.")
            return
        if self.may_discard():
            self.executor.shutdown(wait=False)
            self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=gc.DEFAULT_OUTPUT)
    parser.add_argument("--source-dir", type=Path, default=gc.DEFAULT_INPUT)
    args = parser.parse_args()
    try:
        repository = MaskRepository(args.output_dir, args.source_dir)
        cv2.setNumThreads(1)
        with output_lock(repository.output):
            root = tk.Tk()
            MaskEditor(root, repository)
            root.mainloop()
    except Exception as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
