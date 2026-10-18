"""Project locations and scoped aliases for historical data references.

Only the three data directories have moved. Report artifacts, requirements and
both Python environments retain their original locations.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = PROJECT_ROOT / "reports" / "yeu_cau_2"
GRABCUT_OUTPUT_DIR = REPORT_DIR / "grabcut_output"
LEGACY_IMAGE_PROCESSING_DIR = PROJECT_ROOT / "bo_tool_anh_576x384"
SOURCE_IMAGES_DIR = DATA_DIR / "source_images"
CROPPED_IMAGES_DIR = DATA_DIR / "cropped_images_576x384"
REJECTED_CROPS_DIR = DATA_DIR / "rejected_crops"

LEGACY_DATA_FOLDERS = {
    "anh-chua-loc": "source_images",
    "anh-da-cat-576x384": "cropped_images_576x384",
    "anh-da-cat-576x384-da-xoa": "rejected_crops",
}


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
