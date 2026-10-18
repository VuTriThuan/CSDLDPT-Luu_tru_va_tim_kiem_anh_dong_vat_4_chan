"""Đánh số ảnh toàn bộ bộ dữ liệu từ 0001, đồng bộ ảnh cắt và nhật ký.

Xem trước: python3 tools/image_processing/rename_images.py
Thực hiện: python3 tools/image_processing/rename_images.py --apply
"""

import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys
import re
import tempfile
from uuid import uuid4

# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.image_processing.tool_common import DATA, folder_lock


SOURCE = DATA / "source_images"
CROPPED = DATA / "cropped_images_576x384"
DELETED = DATA / "rejected_crops"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
# (1) là hậu tố bản sao của một ảnh nguồn hiện có.
NUMBERED_NAME = re.compile(r"^(?P<prefix>.+)_(?P<number>\d+)(?:\((?P<copy>\d+)\))?$")


def images(folder):
    if not folder.is_dir():
        raise ValueError(f"Không tìm thấy thư mục: {folder}")
    return {p.name: p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS}


def atomic_write(path, content):
    fd, temp_name = tempfile.mkstemp(prefix=".doi-ten-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def report_bytes(state):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["anh_goc", "anh_da_cat", "trang_thai", "can_kiem_tra", "loi", "so_lan_lat"])
    for source_name, record in state["images"].items():
        writer.writerow([source_name, record.get("output", ""), record.get("status", ""),
                         "; ".join(record.get("warnings", [])), record.get("error", ""),
                         record.get("review_flip_count", 0)])
    return buffer.getvalue().encode("utf-8-sig")


def build_plan():
    original = images(SOURCE)
    cropped = images(CROPPED)
    deleted = images(DELETED)
    log_path = CROPPED / "_cat_tu_dong.json"
    if not log_path.is_file():
        raise ValueError(f"Thiếu nhật ký để ghép ảnh gốc với ảnh cắt: {log_path}")
    state = json.loads(log_path.read_text(encoding="utf-8"))
    records = state.get("images")
    if not isinstance(records, dict) or set(records) != set(original):
        raise ValueError("Nhật ký không khớp danh sách ảnh gốc; chưa đổi tên file nào.")
    state["source"] = str(SOURCE.resolve())
    state["source_relative"] = Path(os.path.relpath(SOURCE.resolve(), CROPPED.resolve())).as_posix()

    parsed = []
    for name in original:
        match = NUMBERED_NAME.fullmatch(Path(name).stem)
        if not match:
            raise ValueError(f"Tên ảnh gốc không có số thứ tự hợp lệ: {name}")
        parsed.append((int(match["number"]), match["prefix"].casefold(),
                       int(match["copy"] or 0), name.casefold(), name, match["prefix"]))
    parsed.sort()

    moves = []
    next_records = {}
    seen_outputs = set()
    for index, (_, _, _, _, old_name, prefix) in enumerate(parsed, start=1):
        source_target = f"{prefix}_{index:04d}{original[old_name].suffix}"
        moves.append((original[old_name], SOURCE / source_target))
        record = dict(records[old_name])
        old_output = record.get("output")
        if old_output:
            if Path(old_output).name != old_output or old_output in seen_outputs:
                raise ValueError(f"Tên ảnh cắt trong nhật ký không hợp lệ hoặc bị trùng: {old_output}")
            seen_outputs.add(old_output)
            new_output = f"{prefix}_{index:04d}{Path(old_output).suffix}"
            record["output"] = new_output
            locations = [folder[old_output] for folder in (cropped, deleted) if old_output in folder]
            if len(locations) > 1:
                raise ValueError(f"Ảnh cắt có mặt trong cả hai thư mục: {old_output}")
            if locations:
                moves.append((locations[0], locations[0].with_name(new_output)))
        next_records[source_target] = record

    unexpected = (set(cropped) | set(deleted)) - seen_outputs
    if unexpected:
        raise ValueError(f"Có ảnh cắt không có trong nhật ký: {', '.join(sorted(unexpected)[:5])}")
    state["images"] = next_records
    validate_moves(moves)
    missing = len(seen_outputs - set(cropped) - set(deleted))
    return moves, state, missing


def validate_moves(moves):
    by_folder = {}
    for old, new in moves:
        by_folder.setdefault(old.parent, []).append((old, new))
    for folder, pairs in by_folder.items():
        old_names = {old.name.casefold() for old, _ in pairs}
        new_names = [new.name.casefold() for _, new in pairs]
        if len(new_names) != len(set(new_names)):
            raise ValueError(f"Tên mới bị trùng trong {folder}")
        for old, new in pairs:
            if new.name.casefold() not in old_names and new.exists():
                raise ValueError(f"Tên mới đã tồn tại: {new}")


def apply_plan(moves, state):
    log_path = CROPPED / "_cat_tu_dong.json"
    report_path = CROPPED / "bao_cao_cat.csv"
    before = {path: path.read_bytes() if path.exists() else None
              for path in (log_path, report_path)}
    staged = []
    finished = []
    token = uuid4().hex
    try:
        for index, (old, new) in enumerate(moves):
            temp = old.with_name(f".doi-ten-{token}-{index}.tmp")
            if temp.exists():
                raise FileExistsError(temp)
            old.rename(temp)
            staged.append((old, temp, new))
        for old, temp, new in staged:
            if new.exists():
                raise FileExistsError(new)
            temp.rename(new)
            finished.append((old, temp, new))
        atomic_write(log_path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        atomic_write(report_path, report_bytes(state))
    except BaseException:
        for _, temp, new in reversed(finished):
            if new.exists():
                new.rename(temp)
        for old, temp, _ in reversed(staged):
            if temp.exists():
                temp.rename(old)
        for path, content in before.items():
            if content is not None:
                atomic_write(path, content)
            elif path.exists():
                path.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Thực hiện đổi tên; mặc định chỉ xem trước")
    args = parser.parse_args()
    if args.apply:
        # Cùng khóa với tool cắt/duyệt: đóng các tool này trước khi đổi tên.
        with folder_lock(CROPPED):
            moves, state, missing = build_plan()
            apply_plan(moves, state)
    else:
        moves, _, missing = build_plan()
    counts = {folder: sum(old.parent == folder for old, _ in moves)
              for folder in (SOURCE, CROPPED, DELETED)}
    print("Đã đổi tên:" if args.apply else "Xem trước (chưa đổi tên):")
    for folder, count in counts.items():
        print(f"  {folder.name}: {count} ảnh")
    print(f"  Ảnh cắt đang thiếu: {missing} (nhật ký vẫn được đổi tên tương ứng)")
    for old, new in moves[:5]:
        print(f"  {old.relative_to(DATA)} -> {new.relative_to(DATA)}")
    if not args.apply:
        print("Chạy lại với --apply để thực hiện.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Lỗi: {exc}") from exc
