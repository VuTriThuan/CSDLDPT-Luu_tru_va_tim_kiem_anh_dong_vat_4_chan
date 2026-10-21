"""Current project locations and scoped, read-only aliases for historical evidence."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = PROJECT_ROOT / "reports" / "yeu_cau_2"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
INVENTORY_DIR = OUTPUTS_DIR / "inventory"
FEATURES_DIR = OUTPUTS_DIR / "features"
B400_OUTPUT_DIR = FEATURES_DIR / "b400_v1"
SEGMENTATION_DIR = OUTPUTS_DIR / "segmentation"
GRABCUT_OUTPUT_DIR = SEGMENTATION_DIR / "grabcut"
GRABCUT_SOURCE_INVENTORY = GRABCUT_OUTPUT_DIR / "provenance" / "source_before.json"
REGENERATED_OUTPUT_DIR = SEGMENTATION_DIR / "mask_regeneration"
# Keep this beside the intended result directory, without occupying a fresh output.
REGENERATED_SOURCE_INVENTORY = SEGMENTATION_DIR / "mask_regeneration_source_before.json"
LEGACY_IMAGE_PROCESSING_DIR = PROJECT_ROOT / "bo_tool_anh_576x384"
SOURCE_IMAGES_DIR = DATA_DIR / "source_images"
CROPPED_IMAGES_DIR = DATA_DIR / "cropped_images_576x384"
REJECTED_CROPS_DIR = DATA_DIR / "rejected_crops"

LEGACY_DATA_FOLDERS = {
    "anh-chua-loc": "source_images",
    "anh-da-cat-576x384": "cropped_images_576x384",
    "anh-da-cat-576x384-da-xoa": "rejected_crops",
}

LEGACY_OVERLAY_CATEGORIES = {"đạt": "accepted", "cần sửa": "needs_revision", "làm lại": "redo"}
LEGACY_RESULT_PATHS = {
    "reports/yeu_cau_2/grabcut_output": "outputs/segmentation/grabcut",
    "reports/yeu_cau_2/mask_moi_can_sua": "outputs/segmentation/mask_regeneration",
    "reports/yeu_cau_2/grabcut_source_before.json": "outputs/segmentation/grabcut/provenance/source_before.json",
    "reports/yeu_cau_2/mask_moi_can_sua_truoc_khi_chay.json": "outputs/segmentation/mask_regeneration_source_before.json",
    "reports/yeu_cau_2/kiem_ke.json": "outputs/inventory/image_inventory.json",
    "reports/yeu_cau_2/anh_da_xem.csv": "outputs/inventory/viewed_images.csv",
    "reports/yeu_cau_2/grabcut_so_do.csv": "outputs/inventory/grabcut_sample_statistics.csv",
    "reports/yeu_cau_2/grabcut_moi_truong.json": "outputs/inventory/grabcut_sample_environment.json",
}


def resolve_project_reference(path, project_root=PROJECT_ROOT):
    """Locate moved evidence without changing its stored path, hash or timestamp.

    Only known paths within this project are aliased. Foreign absolute paths and
    unrelated output directories are left alone.
    """
    root = Path(project_root).resolve()
    candidate = resolve_data_reference(path, root)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return candidate
    for before, after in LEGACY_RESULT_PATHS.items():
        try:
            tail = relative.relative_to(before)
        except ValueError:
            continue
        relative = Path(after) / tail
        break
    parts = list(relative.parts)
    if (len(parts) >= 5 and parts[:2] == ['outputs', 'segmentation']
            and parts[2] in {'grabcut', 'mask_regeneration'} and parts[3] == 'overlays'):
        parts[4] = LEGACY_OVERLAY_CATEGORIES.get(parts[4], parts[4])
    return root.joinpath(*parts)


def resolve_data_reference(path, project_root=PROJECT_ROOT):
    """Resolve an old data path within this project, without rewriting evidence.

    Paths outside project_root/data and unrelated source folders are unchanged.
    Passing a different project_root supports isolated copies and restored trees.
    """
    project_root = Path(project_root).resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(project_root / "data")
    except ValueError:
        return candidate
    if relative.parts and relative.parts[0] in LEGACY_DATA_FOLDERS:
        return project_root / "data" / LEGACY_DATA_FOLDERS[relative.parts[0]] / Path(*relative.parts[1:])
    return candidate


def rejected_directory(cropped_folder):
    """Use the canonical rejection folder while preserving custom-folder behavior."""
    folder = Path(cropped_folder)
    if folder.name == "cropped_images_576x384":
        return folder.with_name("rejected_crops")
    return folder.with_name(folder.name + "-da-xoa")
