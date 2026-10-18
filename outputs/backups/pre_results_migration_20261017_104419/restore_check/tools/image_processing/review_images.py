#!/usr/bin/env python3
"""Duyệt ảnh đã cắt. D: xóa khỏi bộ ảnh. A: lật ngang. U: hoàn tác.

python3 tools/image_processing/review_images.py
python3 tools/image_processing/review_images.py --folder "data/cropped_images_576x384"

Ảnh loại từ cropped_images_576x384 được chuyển sang rejected_crops bên cạnh.
Với thư mục tùy chọn khác, giữ quy tắc <tên-thư-mục>-da-xoa.
Ảnh gốc trong source_images không bị sửa. A lưu ảnh lật ngay tại chỗ.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.image_processing.tool_common import DATA, configure_console, folder_lock, prepare_runtime
from tools.project_paths import rejected_directory

configure_console()
if __name__ == "__main__":
    prepare_runtime(__file__)

try:
    from PIL import Image, ImageOps
except ImportError:
    raise SystemExit("Thiếu Pillow. Chạy: python3 tools/image_processing/review_images.py --setup")

DEFAULT_FOLDER = DATA / "cropped_images_576x384"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def atomic_bytes(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".duyet-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def read_rgb(path):
    with Image.open(path) as im:
        rgba = ImageOps.exif_transpose(im).convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, "white")
        canvas.alpha_composite(rgba)
        return canvas.convert("RGB")


class ReviewStore:
    def __init__(self, folder):
        self.folder = folder
        self.log_path = folder/"_cat_tu_dong.json"
        self.state = None
        self.history = []
        if self.log_path.exists():
            self.state = json.loads(self.log_path.read_text(encoding="utf-8"))
            if self.state.get("version") != 1 or not isinstance(self.state.get("images"), dict):
                raise ValueError("Nhật ký cắt ảnh không hợp lệ. Hãy giữ lại file này để kiểm tra.")

    def record(self, name):
        if self.state:
            for key, record in self.state["images"].items():
                if record.get("output") == name:
                    return key, record
        return None, {}

    def commit(self, key, new):
        if key is None:
            return
        old = self.state["images"][key]
        self.state["images"][key] = new
        try:
            atomic_json(self.log_path, self.state)
        except Exception:
            self.state["images"][key] = old
            raise

    def sync_report(self):
        if not self.state:
            return
        text = io.StringIO(newline="")
        writer = csv.writer(text)
        writer.writerow(["anh_goc", "anh_da_cat", "trang_thai", "can_kiem_tra", "loi", "so_lan_lat"])
        for source, r in self.state["images"].items():
            writer.writerow([source, r.get("output", ""), r.get("status", ""), "; ".join(r.get("warnings", [])),
                             r.get("error", ""), r.get("review_flip_count", 0)])
        atomic_bytes(self.folder/"bao_cao_cat.csv", text.getvalue().encode("utf-8-sig"))

    def delete(self, path):
        if path.parent != self.folder:
            raise ValueError("Chỉ xóa ảnh nằm trực tiếp trong thư mục đang duyệt.")
        key, old = self.record(path.name)
        archive = rejected_directory(self.folder)
        archive.mkdir(exist_ok=True)
        destination = archive/path.name
        counter = 2
        while destination.exists():
            destination = archive/f"{path.stem}_{counter:03d}{path.suffix}"
            counter += 1
        path.rename(destination)
        try:
            self.commit(key, {**old, "status": "deleted", "review_deleted_at": time.strftime('%Y-%m-%dT%H:%M:%S')})
        except Exception:
            destination.rename(path)
            raise
        self.history.append({"action":"delete", "path":path, "archive":destination, "key":key, "old":dict(old)})
        self.history = self.history[-50:]

    def flip(self, path):
        before = path.read_bytes()
        image = ImageOps.mirror(read_rgb(path))
        data = io.BytesIO()
        fmt = {".png":"PNG", ".webp":"WEBP", ".bmp":"BMP", ".tif":"TIFF", ".tiff":"TIFF"}.get(path.suffix.lower(), "JPEG")
        image.save(data, fmt, **({"quality":95, "subsampling":0} if fmt == "JPEG" else {}))
        key, old = self.record(path.name)
        atomic_bytes(path, data.getvalue())
        try:
            self.commit(key, {**old, "status":"saved", "review_flip_count":old.get("review_flip_count",0)+1})
        except Exception:
            atomic_bytes(path, before)
            raise
        self.history.append({"action":"flip", "path":path, "bytes":before, "key":key, "old":dict(old)})
        # Giới hạn bộ nhớ cho hoàn tác; tối đa 50 thao tác gần nhất.
        self.history = self.history[-50:]

    def undo(self):
        if not self.history:
            return None
        item = self.history[-1]
        path = item["path"]
        if item["action"] == "delete":
            if path.exists():
                raise ValueError("Không hoàn tác được: có file khác cùng tên. Đổi tên file đó trước.")
            item["archive"].rename(path)
            try:
                self.commit(item["key"], item["old"])
            except Exception:
                path.rename(item["archive"])
                raise
        else:
            current = path.read_bytes()
            atomic_bytes(path, item["bytes"])
            try:
                self.commit(item["key"], item["old"])
            except Exception:
                atomic_bytes(path, current)
                raise
        self.history.pop()
        return path


class Viewer:
    def __init__(self, root, folder, store):
        import tkinter as tk
        from tkinter import ttk
        from PIL import ImageTk
        self.root, self.folder, self.store, self.ImageTk = root, folder, store, ImageTk
        self.files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS and not p.name.startswith('.')], key=lambda p:p.name.casefold())
        self.index = 0
        self.image = None
        self.status = tk.StringVar()
        self.note = tk.StringVar(value="D: xóa và tiếp • A: lật ngang • ←/→: trước/sau • U: hoàn tác • Esc: thoát")
        root.title("Duyệt ảnh • D xóa • A lật ngang")
        root.geometry("1000x720")
        root.minsize(700,500)
        header = ttk.Frame(root, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="DUYỆT ẢNH SAU KHI CẮT", font=("Helvetica",17,"bold")).pack(anchor="w")
        ttk.Label(header, textvariable=self.status, wraplength=940).pack(anchor="w", pady=5)
        self.canvas = tk.Canvas(root, bg="#202733", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12)
        footer = ttk.Frame(root, padding=12)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.note, wraplength=940).pack(anchor="w", pady=(0,8))
        buttons = ttk.Frame(footer)
        buttons.pack(fill="x")
        for label, action in [("◀ Trước",lambda:self.move(-1)), ("Sau ▶",lambda:self.move(1)),
                              ("Xóa (D)",self.delete), ("Lật ngang (A)",self.flip), ("Hoàn tác (U)",self.undo)]:
            ttk.Button(buttons,text=label,command=action).pack(side="left",padx=(0,8))
        self.busy = False
        self.last_mutation = 0.0
        for key, action in [("d",self.delete),("D",self.delete),("a",self.flip),("A",self.flip),
                            ("u",self.undo),("U",self.undo),("<Left>",lambda:self.move(-1)),
                            ("<Right>",lambda:self.move(1)),("<Escape>",root.destroy)]:
            root.bind(key,lambda e,fn=action:fn())
        root.protocol("WM_DELETE_WINDOW",root.destroy)
        self.canvas.bind("<Configure>",lambda e:self.draw())
        root.after(100,self.load)

    def current(self):
        return self.files[self.index] if self.files else None

    def load(self):
        self.image = None
        path = self.current()
        if path is None:
            self.status.set("Không còn ảnh trong thư mục. U để hoàn tác thao tác vừa làm.")
            self.draw()
            return
        try:
            self.image = read_rgb(path)
            _, record = self.store.record(path.name)
            warnings = record.get("warnings", [])
            self.status.set(f"{self.index+1}/{len(self.files)} • {path.name} • {self.image.width} × {self.image.height}" +
                            ("\nCần kiểm tra: "+"; ".join(warnings) if warnings else ""))
        except Exception as exc:
            self.status.set(f"Không đọc được {path.name}: {exc}. D để loại ảnh, → để tiếp.")
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        if self.image is None:
            return
        view = self.image.copy()
        view.thumbnail((max(1,self.canvas.winfo_width()-20), max(1,self.canvas.winfo_height()-20)), Image.Resampling.LANCZOS)
        self.photo = self.ImageTk.PhotoImage(view)
        self.canvas.create_image(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,image=self.photo)

    def move(self, step):
        if self.files:
            self.index = max(0,min(len(self.files)-1,self.index+step))
            self.load()

    def mutation(self, action):
        # Chống sự kiện lặp nhanh khi giữ phím D/A.
        if self.busy or time.monotonic()-self.last_mutation < 0.35:
            return
        self.busy = True
        self.last_mutation = time.monotonic()
        try:
            action()
            try:
                self.store.sync_report()
            except OSError:
                self.note.set("Đã sửa ảnh; không cập nhật được CSV. Nhật ký JSON đã ghi thành công.")
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Không thực hiện được",str(exc),parent=self.root)
        finally:
            self.busy = False

    def delete(self):
        if self.current():
            def action():
                path = self.current()
                self.store.delete(path)
                self.files.pop(self.index)
                self.index = min(self.index,max(0,len(self.files)-1))
                self.load()
                self.note.set(f"Đã xóa {path.name} khỏi bộ ảnh. U để khôi phục.")
            self.mutation(action)

    def flip(self):
        if self.current():
            def action():
                self.store.flip(self.current())
                self.load()
                self.note.set("Đã lật ngang và lưu ngay. U để khôi phục ảnh trước khi lật.")
            self.mutation(action)

    def undo(self):
        def action():
            path = self.store.undo()
            if path is None:
                self.note.set("Không có thao tác để hoàn tác trong phiên này.")
                return
            if path not in self.files:
                self.files.append(path)
                self.files.sort(key=lambda p:p.name.casefold())
            self.index = self.files.index(path)
            self.load()
            self.note.set("Đã hoàn tác.")
        self.mutation(action)


def main():
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setup", action="store_true", help="Tạo môi trường ảo và cài thư viện, rồi thoát")
    parser.add_argument("--folder",type=Path,default=DEFAULT_FOLDER)
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Không tìm thấy {folder}. Chạy tool 1 trước hoặc chỉ định --folder.")
    try:
        with folder_lock(folder):
            store = ReviewStore(folder)
            try:
                import tkinter as tk
            except ImportError:
                raise RuntimeError("Thiếu Tkinter. Cài Python từ python.org với Tcl/Tk, rồi kiểm tra: python -m tkinter")
            root = tk.Tk()
            Viewer(root,folder,store)
            root.mainloop()
    except Exception as exc:
        print(f"Lỗi: {exc}",file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
