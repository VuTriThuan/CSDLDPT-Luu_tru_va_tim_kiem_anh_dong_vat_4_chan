#!/usr/bin/env python3
"""Tự định vị chủ thể bằng U²-Net ONNX/CPU và cắt giữ tỉ lệ 576x384.

python3 tools/image_processing/auto_crop.py --limit 30
python3 tools/image_processing/auto_crop.py
python3 tools/image_processing/auto_crop.py --model u2netp  # mô hình nhỏ hơn

Mô hình tìm chủ thể nổi bật, không phân loại loài hoặc xác minh tư thế đứng.
Nguồn mặc định: BTL/data/source_images (theo vị trí thư mục chứa tool).
Đích mặc định: BTL/data/cropped_images_576x384
"""
from __future__ import annotations

import argparse
from collections import deque
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import ssl
import sys
import tempfile
import time
import urllib.request

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.image_processing.tool_common import DATA, configure_console, folder_lock, prepare_runtime
from tools.project_paths import resolve_data_reference

configure_console()
if __name__ == "__main__":
    prepare_runtime(__file__)

try:
    import certifi
    import numpy as np
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit(f"Thiếu thư viện: {exc}. Chạy: python3 tools/image_processing/auto_crop.py --setup")

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MODELS = {
    "u2net": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx", "60024c5c889badc19c04ad937298a77b"),
    "u2netp": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx", "8e83ca70e441ab06c318d82300c84806"),
}


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".log-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_rgb(path):
    with Image.open(path) as opened:
        rgba = ImageOps.exif_transpose(opened).convert("RGBA")
        rgb = Image.new("RGBA", rgba.size, "white")
        rgb.alpha_composite(rgba)
        return rgb.convert("RGB")


def atomic_jpg(path, img):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".crop-", suffix=".tmp")
    os.close(fd)
    try:
        img.save(name, "JPEG", quality=95, subsampling=0)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def file_md5(path):
    digest = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_model(model, model_dir):
    url, expected = MODELS[model]
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / (model + ".onnx")
    if target.is_file() and file_md5(target) == expected:
        return target
    print(f"Tải mô hình {model} lần đầu ({'khoảng 176 MB' if model == 'u2net' else 'khoảng 5 MB'})…", flush=True)
    fd, temporary = tempfile.mkstemp(dir=model_dir, prefix=".model-", suffix=".part")
    os.close(fd)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AnimalCrop/1.0"})
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, timeout=60, context=context) as response, open(temporary, "wb") as f:
            total = int(response.headers.get("Content-Length", 0))
            received, last = 0, 0.0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                f.write(block)
                received += len(block)
                if time.monotonic() - last > 2:
                    print(f"  {received / 1048576:.1f} MB" + (f" / {total / 1048576:.1f} MB" if total else ""), flush=True)
                    last = time.monotonic()
        if file_md5(Path(temporary)) != expected:
            raise RuntimeError("Tệp mô hình tải về chưa đúng. Chạy lại để tải lại.")
        os.replace(temporary, target)
    except Exception as exc:
        raise RuntimeError(f"Không tải được mô hình: {exc}\nBạn có thể tải {url} bằng trình duyệt rồi đặt tại {target}.") from exc
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def make_session(path, threads):
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("Thiếu ONNX Runtime. Cài thư viện bằng requirements.txt trong môi trường Python 3.10–3.13 của máy hiện tại.") from exc
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 3
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


def predict_mask(session, image):
    # Tiền xử lý theo U²-Net: RGB 320x320, chia giá trị lớn nhất, chuẩn hóa mean/std.
    arr = np.asarray(image.resize((320, 320), Image.Resampling.LANCZOS), dtype=np.float32)
    arr /= max(float(arr.max()), 1e-6)
    arr = (arr - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
    tensor = np.ascontiguousarray(arr.transpose(2, 0, 1)[None], dtype=np.float32)
    prediction = np.asarray(session.run(None, {session.get_inputs()[0].name: tensor})[0])[0, 0]
    if prediction.shape != (320, 320) or not np.isfinite(prediction).all():
        raise ValueError("Đầu ra mô hình không hợp lệ.")
    low, high = float(prediction.min()), float(prediction.max())
    if high - low < 1e-6:
        raise ValueError("Không tìm thấy vùng chủ thể đủ rõ.")
    return np.clip((prediction - low) / (high - low), 0, 1)


def find_subject(mask, image_size, threshold=0.25):
    """Gộp các vùng đủ lớn để giữ phần chân/đuôi rời nhau trên mặt nạ."""
    binary = np.asarray(mask) >= threshold
    h, w = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    components = []
    for y, x in zip(*np.nonzero(binary)):
        if visited[y, x]:
            continue
        queue = deque([(int(y), int(x))])
        visited[y, x] = True
        count = 0
        xmin = xmax = int(x)
        ymin = ymax = int(y)
        while queue:
            yy, xx = queue.popleft()
            count += 1
            xmin, xmax = min(xmin, xx), max(xmax, xx)
            ymin, ymax = min(ymin, yy), max(ymax, yy)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = yy + dy, xx + dx
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((ny, nx))
        components.append((count, xmin, ymin, xmax+1, ymax+1))
    if not components:
        raise ValueError("Mặt nạ trống. Cần cắt thủ công ảnh này.")
    components.sort(reverse=True)
    largest = components[0][0]
    if largest < h*w*0.005:
        raise ValueError("Vùng chủ thể quá nhỏ. Cần cắt thủ công ảnh này.")
    kept = [c for c in components if c[0] >= max(8, largest*0.001)]
    left, top = min(c[1] for c in kept), min(c[2] for c in kept)
    right, bottom = max(c[3] for c in kept), max(c[4] for c in kept)
    iw, ih = image_size
    bbox = (math.floor(left*iw/w), math.floor(top*ih/h), math.ceil(right*iw/w), math.ceil(bottom*ih/h))
    warnings = []
    if sum(c[0] for c in kept) > h*w*0.9:
        warnings.append("Mặt nạ gần kín ảnh; có thể nhận nhầm nền")
    if left <= 1 or top <= 1 or right >= w-1 or bottom >= h-1:
        warnings.append("Chủ thể sát mép; kiểm tra có mất chân/đuôi ở ảnh gốc")
    if len([c for c in kept if c[0] > largest*0.10]) > 1:
        warnings.append("Nhiều vùng lớn; kiểm tra ảnh nhiều con hoặc nền bị nhận nhầm")
    return bbox, warnings


def crop_subject(image, bbox, size=(576, 384), fill=0.85):
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height):
        raise ValueError("Khung bao chủ thể không hợp lệ.")
    bw, bh = x2-x1, y2-y1
    # Dùng khung có đúng tỉ lệ 3:2 và nằm hoàn toàn trong ảnh gốc.
    # Hai chiều là bội số của 3 và 2 để resize không kéo méo hoặc thêm viền.
    units = max(1, math.ceil(max(bw / (3 * fill), bh / (2 * fill))))
    max_units = min(image.width // 3, image.height // 2)
    if max_units < 1:
        raise ValueError("Ảnh gốc quá nhỏ để cắt tỉ lệ 3:2.")
    units = min(units, max_units)
    crop_w, crop_h = 3 * units, 2 * units
    cx, cy = (x1+x2)/2, (y1+y2)/2
    left = min(max(round(cx - crop_w / 2), 0), image.width - crop_w)
    top = min(max(round(cy - crop_h / 2), 0), image.height - crop_h)
    right, bottom = left + crop_w, top + crop_h
    warnings = []
    if x1 < left or y1 < top or x2 > right or y2 > bottom:
        warnings.append("Ảnh gốc không đủ chỗ cho toàn bộ chủ thể ở tỉ lệ 3:2; kiểm tra mép ảnh")
    result = image.crop((left, top, right, bottom)).resize(size, Image.Resampling.LANCZOS)
    scale = size[0] / crop_w
    return result, [left, top, right, bottom], scale, warnings


def signature(path):
    s = path.stat()
    return [s.st_size, s.st_mtime_ns]


def source_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_unchanged(path, record):
    current = signature(path)
    if record.get("signature") == current:
        # Bổ sung checksum cho nhật ký cũ khi ảnh gốc vẫn khớp chữ ký đã lưu.
        if not record.get("source_sha256"):
            record["source_sha256"] = source_sha256(path)
        return True
    if record.get("source_sha256") and record["source_sha256"] == source_sha256(path):
        record["signature"] = current
        return True
    return False


def fresh_state(source):
    return {"version": 1, "source": str(source), "images": {}}


def load_state(path, source):
    if not path.exists():
        return fresh_state(source)
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != 1 or not isinstance(state.get("images"), dict):
        raise ValueError("Nhật ký đầu ra khác nguồn hoặc không hợp lệ. Chọn --output khác.")
    source = source.resolve()
    relative = state.get("source_relative")
    same_source = state.get("source") == str(source)
    if isinstance(relative, str):
        recorded = (path.parent / relative).resolve()
        same_source = recorded == source
        if not same_source:
            same_source = resolve_data_reference(recorded, source.parent.parent) == source
    elif isinstance(state.get("source"), str):
        same_source = resolve_data_reference(state["source"], source.parent.parent) == source
    if not same_source:
        raise ValueError("Nhật ký thuộc nguồn khác. Trước khi chuyển máy, chạy phiên bản tool mới trên máy cũ để cập nhật nhật ký, hoặc chọn --output khác.")
    state["source"] = str(source)
    return state


def make_state_portable(state, log_path, source):
    # Giữ đường dẫn tuyệt đối cho khả năng đọc nhật ký bằng phiên bản cũ.
    state["source"] = str(source)
    try:
        state["source_relative"] = Path(os.path.relpath(source, log_path.parent)).as_posix()
    except ValueError:
        # Windows không biểu diễn tương đối giữa hai ổ đĩa khác nhau.
        state.pop("source_relative", None)
    for key, record in state["images"].items():
        original = source / key
        if original.is_file():
            source_unchanged(original, record)
    return state


def allocate_name(path, output, record, state):
    previous = record.get("output")
    if previous:
        if Path(previous).name != previous:
            raise ValueError("Tên JPG trong nhật ký không hợp lệ.")
        return output / previous
    used = {r.get("output", "").casefold() for r in state["images"].values()}
    candidate = output / (path.stem + ".jpg")
    counter = 2
    while candidate.exists() or candidate.name.casefold() in used:
        candidate = output / f"{path.stem}_{counter:03d}.jpg"
        counter += 1
    return candidate


def write_csv(output, state):
    rows = []
    for source, r in state["images"].items():
        rows.append([source, r.get("output", ""), r.get("status", ""), "; ".join(r.get("warnings", [])),
                     r.get("error", ""), r.get("review_flip_count", 0)])
    fd, name = tempfile.mkstemp(dir=output, prefix=".report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["anh_goc", "anh_da_cat", "trang_thai", "can_kiem_tra", "loi", "so_lan_lat"])
            writer.writerows(rows)
        os.replace(name, output / "bao_cao_cat.csv")
    finally:
        Path(name).unlink(missing_ok=True)


def repair_borders(source, output):
    """Tạo lại ảnh đã lưu bằng bbox cũ, không chạy mô hình hay khôi phục ảnh đã xóa."""
    with folder_lock(output):
        log_path = output / "_cat_tu_dong.json"
        state = make_state_portable(load_state(log_path, source), log_path, source)
        repaired = skipped = 0
        for key, record in state["images"].items():
            if record.get("status") != "saved" or record.get("crop_mode") == "inside-source":
                continue
            original = source / key
            output_name = record.get("output", "")
            bbox = record.get("bbox")
            if not output_name or Path(output_name).name != output_name:
                skipped += 1
                print(f"Bỏ qua {key}: tên ảnh đầu ra không hợp lệ.")
                continue
            destination = output / output_name
            if (not original.is_file() or not destination.is_file()
                    or not source_unchanged(original, record)
                    or not isinstance(bbox, list) or len(bbox) != 4):
                skipped += 1
                print(f"Bỏ qua {key}: thiếu ảnh/khung cắt hoặc ảnh gốc đã thay đổi.")
                continue
            try:
                image = read_rgb(original)
                cropped, crop_box, scale, crop_warnings = crop_subject(
                    image, bbox, fill=record["config"]["fill"])
                if record.get("review_flip_count", 0) % 2:
                    cropped = ImageOps.mirror(cropped)
                atomic_jpg(destination, cropped)
                warnings = [w for w in record.get("warnings", []) if not w.startswith("Ảnh gốc không đủ chỗ")]
                warnings.extend(crop_warnings)
                if scale > 1.05 and "Vùng con vật nhỏ; ảnh kết quả được phóng lớn" not in warnings:
                    warnings.append("Vùng con vật nhỏ; ảnh kết quả được phóng lớn")
                record.update(crop_box=crop_box, crop_mode="inside-source", warnings=warnings)
                atomic_json(log_path, state)
                repaired += 1
            except Exception as exc:
                skipped += 1
                print(f"Bỏ qua {key}: {exc}")
        atomic_json(log_path, state)
        write_csv(output, state)
        print(f"Đã sửa viền: {repaired} ảnh; bỏ qua: {skipped} ảnh. Ảnh đã xóa được giữ nguyên.")


def run_batch(args):
    source = args.input.expanduser().resolve()
    output = (args.output.expanduser() if args.output else source.parent / "cropped_images_576x384").resolve()
    if not source.is_dir():
        raise ValueError(f"Không tìm thấy thư mục ảnh: {source}")
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Nguồn và đầu ra phải là hai thư mục tách biệt, không nằm trong nhau.")
    if args.repair_borders:
        if not output.is_dir() or not (output / "_cat_tu_dong.json").is_file():
            raise ValueError("Không tìm thấy thư mục kết quả và nhật ký để sửa viền.")
        repair_borders(source, output)
        return
    files = sorted([p for p in (source.rglob('*') if args.recursive else source.iterdir())
                    if p.is_file() and not p.name.startswith('.') and p.suffix.lower() in EXTENSIONS],
                   key=lambda p: p.relative_to(source).as_posix().casefold())
    if not files:
        raise ValueError("Không có ảnh JPG/PNG/WEBP/BMP/TIFF. Nếu ảnh trong thư mục con, thêm --recursive.")
    output.mkdir(parents=True, exist_ok=True)
    config = {"size": [576,384], "fill": args.fill, "threshold": args.threshold, "model": args.model}
    with folder_lock(output):
        log_path = output / "_cat_tu_dong.json"
        state = make_state_portable(load_state(log_path, source), log_path, source)
        pending = []
        for p in files:
            record = state["images"].get(p.relative_to(source).as_posix(), {})
            # Giữ các quyết định xóa/lật của tool duyệt khi chạy lại.
            if (not args.force and record.get("config") == config
                    and source_unchanged(p, record)
                    and record.get("status") in {"saved", "deleted"}):
                continue
            pending.append(p)
        if args.limit:
            pending = pending[:args.limit]
        atomic_json(log_path, state)
        print(f"Nguồn: {source}\nĐầu ra: {output}\nCần xử lý: {len(pending)}/{len(files)}", flush=True)
        if not pending:
            print("Không còn ảnh mới. Tool giữ các ảnh bạn đã lật/xóa. --force sẽ tạo lại từ ảnh gốc.")
            write_csv(output, state)
            return
        model_path = ensure_model(args.model, args.model_dir.expanduser().resolve())
        session = make_session(model_path, args.threads)
        processed = failed = 0
        started = time.monotonic()
        try:
            for index, path in enumerate(pending, 1):
                key = path.relative_to(source).as_posix()
                previous = state["images"].get(key, {})
                record = {"signature": signature(path), "source_sha256": source_sha256(path),
                          "config": config, "status": "error", "warnings": []}
                if previous.get("output"):
                    record["output"] = previous["output"]
                try:
                    img = read_rgb(path)
                    mask = predict_mask(session, img)
                    bbox, warnings = find_subject(mask, img.size, args.threshold)
                    cropped, crop_box, scale, crop_warnings = crop_subject(img, bbox, fill=args.fill)
                    warnings.extend(crop_warnings)
                    if scale > 1.05:
                        warnings.append("Vùng con vật nhỏ; ảnh kết quả được phóng lớn")
                    destination = allocate_name(path, output, previous, state)
                    atomic_jpg(destination, cropped)
                    record.update(status="saved", output=destination.name, bbox=list(bbox), crop_box=crop_box,
                                  crop_mode="inside-source", warnings=warnings, review_flip_count=0)
                    processed += 1
                    print(f"[{index}/{len(pending)}] Đã cắt {path.name}" + (" • CẦN DUYỆT: "+"; ".join(warnings) if warnings else ""), flush=True)
                except Exception as exc:
                    record["error"] = str(exc)
                    failed += 1
                    print(f"[{index}/{len(pending)}] Không cắt được {path.name}: {exc}", flush=True)
                state["images"][key] = record
                # Ghi ngay sau mỗi ảnh để có thể tiếp tục sau khi Ctrl+C.
                atomic_json(log_path, state)
        except KeyboardInterrupt:
            print("\nĐã dừng. Chạy lại cùng lệnh để xử lý tiếp.")
        finally:
            write_csv(output, state)
        print(f"Hoàn tất lượt này: {processed} ảnh JPG, {failed} ảnh lỗi, {time.monotonic()-started:.1f} giây.")
        print(f"Danh sách cảnh báo/lỗi: {output / 'bao_cao_cat.csv'}\nẢnh gốc được giữ nguyên. Chạy tools/image_processing/review_images.py để duyệt kết quả.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setup", action="store_true", help="Tạo môi trường ảo và cài thư viện, rồi thoát")
    parser.add_argument("--input", type=Path, default=DATA / "source_images")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", choices=MODELS, default="u2net")
    parser.add_argument("--model-dir", type=Path, default=Path.home()/".cache/animal-crop")
    parser.add_argument("--fill", type=float, default=0.85, help="Mức chiếm khung, 0.65–0.95")
    parser.add_argument("--threshold", type=float, default=0.25, help="Ngưỡng mặt nạ, 0.10–0.80")
    parser.add_argument("--threads", type=int, default=2, help="Số luồng CPU, mặc định 2")
    parser.add_argument("--limit", type=int, default=0, help="Cắt tối đa N ảnh chưa xử lý; 0 = tất cả")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--force", action="store_true", help="Tạo lại từ ảnh gốc, kể cả ảnh đã lật/xóa khi duyệt")
    parser.add_argument("--repair-borders", action="store_true", help="Sửa viền trắng ở ảnh đã lưu, giữ trạng thái xóa/lật; không cần tải mô hình")
    args = parser.parse_args()
    if not 0.65 <= args.fill <= 0.95 or not 0.10 <= args.threshold <= 0.80 or args.threads < 1 or args.limit < 0:
        parser.error("Tham số ngoài phạm vi. Xem --help.")
    try:
        run_batch(args)
    except KeyboardInterrupt:
        print("\nĐã dừng trước khi cắt. Chạy lại cùng lệnh để tiếp tục.")
    except Exception as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
