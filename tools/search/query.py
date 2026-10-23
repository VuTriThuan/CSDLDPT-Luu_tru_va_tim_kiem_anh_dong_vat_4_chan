"""Decode query, reuse GrabCut and frozen B400, publish separate query artifacts."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import time
import uuid

import cv2
import numpy as np
from PIL import Image, ImageDraw

from tools.features import b400
from tools.segmentation.run_grabcut import create_foreground_mask, make_overlay, mask_statistics
from tools.search.mask_quality import analyze_mask


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def output_base(root, destination=None):
    """All application writes stay in outputs/search, including batch/export."""
    allowed = Path(root).resolve()/'outputs/search'
    path = Path(destination).absolute() if destination is not None else allowed
    # macOS /var and /tmp themselves are system aliases; reject symlinks
    # within the application output tree without rejecting those aliases.
    if allowed.is_symlink() or allowed.parent.is_symlink() or any(
            p.is_symlink() and p.resolve().is_relative_to(allowed) for p in [path, *path.parents]):
        raise ValueError('Search output symlinks are not supported')
    path = path.resolve()
    if not path.is_relative_to(allowed):
        raise ValueError(f'Search outputs must be inside {allowed}')
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class QueryImage:
    path: Path
    source_bytes: bytes
    rgb: np.ndarray
    sha256: str
    load_seconds: float


def load_image(path):
    start = time.perf_counter()
    path = Path(path).resolve()
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.format not in {'JPEG', 'PNG'} or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Query must be a single-frame JPG/PNG')
        # Same stored-pixel coordinates as B400: no implicit EXIF rotation/ICC.
        rgb = np.array(image.convert('RGB'))
    return QueryImage(path, data, rgb, digest(data), time.perf_counter()-start)


def load_mask(path, rgb):
    start = time.perf_counter()
    data = Path(path).read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.format != 'PNG' or image.mode not in {'1', 'L'} or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Mask must be a single-frame grayscale PNG, binary 0/255')
        mask = np.array(image.convert('L'))
    b400.validate_arrays(rgb, mask)
    return mask, dict(method='loaded', path=str(Path(path).resolve()), input_sha256=digest(data),
                      mask_seconds=0., mask_load_seconds=time.perf_counter()-start,
                      diagnostics=analyze_mask(mask))


def validate_bbox(rgb, bbox):
    x, y, w, h = bbox
    height, width = rgb.shape[:2]
    if any(not isinstance(v, (int, np.integer)) for v in bbox) or min(x, y) < 0 or min(w, h) < 2 or x+w > width or y+h > height or w*h >= width*height:
        raise ValueError('BBox must be integer x,y,width,height inside image with some background outside')
    return tuple(map(int, bbox))


def create_mask(rgb, bbox=None, iterations=5):
    start = time.perf_counter()
    if not 1 <= iterations <= 100:
        raise ValueError('GrabCut iterations must be in [1,100]')
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    automatic = bbox is None
    if bbox is None:
        h, w = rgb.shape[:2]
        if min(h, w) <= 20:
            raise ValueError('Automatic bbox requires both image axes larger than 20 pixels; supply an explicit bbox')
        bbox = (10, 10, w-20, h-20)
        mask = create_foreground_mask(bgr, iterations=iterations, seed=0)
    else:
        bbox = validate_bbox(rgb, bbox)
        labels = np.zeros(rgb.shape[:2], np.uint8)
        cv2.setRNGSeed(0)
        cv2.grabCut(bgr, labels, bbox, np.zeros((1, 65), np.float64),
                    np.zeros((1, 65), np.float64), iterations, cv2.GC_INIT_WITH_RECT)
        mask = np.where(np.isin(labels, [cv2.GC_FGD, cv2.GC_PR_FGD]), 255, 0).astype(np.uint8)
    b400.validate_arrays(rgb, mask)
    return mask, dict(method='existing_grabcut_rectangle_morphology' if automatic else 'grabcut_user_rectangle',
                      initial_bbox=list(bbox), automatic_bbox=automatic,
                      morphology='open_close_5x5_two_iterations' if automatic else 'none', iterations=iterations, seed=0,
                      mask_seconds=time.perf_counter()-start, mask_load_seconds=0.,
                      diagnostics=analyze_mask(mask, bbox))


def refine(rgb, mask, strokes, iterations=5):
    # Reuse the existing editor's probable-mask/hard-stroke GrabCut routine.
    from tools.segmentation.edit_masks import refine_mask
    b400.validate_arrays(rgb, mask)
    if strokes.shape != mask.shape or strokes.dtype != np.uint8 or not np.isin(strokes, [0, 1, 255]).all():
        raise ValueError('Strokes must match mask: 0 remove, 1 keep, 255 unmarked')
    if not np.any(strokes != 255):
        raise ValueError('No keep/remove strokes; paint corrections before refining the mask')
    if not 1 <= iterations <= 100:
        raise ValueError('GrabCut iterations must be in [1,100]')
    start = time.perf_counter()
    result = refine_mask(np.ascontiguousarray(rgb[:, :, ::-1]), mask, strokes, iterations)
    b400.validate_arrays(rgb, result)
    return result, time.perf_counter()-start


def overlay(rgb, mask):
    return make_overlay(np.ascontiguousarray(rgb[:, :, ::-1]), mask)


def retrieve(index, query, mask, mask_info, destination=None, exclude_self=True, strokes=None):
    b400.validate_arrays(query.rgb, mask)
    base = output_base(index.root, destination)
    if strokes is not None and (strokes.shape != mask.shape or strokes.dtype != np.uint8 or not np.isin(strokes, [0, 1, 255]).all()):
        raise ValueError('Invalid query strokes')
    start = time.perf_counter()
    variants = {}
    for name, rgb, m in [('original', query.rgb, mask),
                         ('flipped', np.ascontiguousarray(query.rgb[:, ::-1]), np.ascontiguousarray(mask[:, ::-1]))]:
        raw, normalized, valid, quality = b400.extract_normalized(rgb, m, index.normalizer)
        canvas, cm, geometry = b400.prepare(rgb, m)
        variants[name] = dict(raw=raw, normalized=normalized, validity=valid, quality=quality,
                              canvas=canvas, canvas_mask=cm.astype(np.uint8)*255)
    feature_seconds = time.perf_counter()-start
    start = time.perf_counter()
    ranked = index.search(variants['original']['normalized'], variants['flipped']['normalized'], query.sha256, exclude_self)
    search_seconds = time.perf_counter()-start
    query_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+uuid.uuid4().hex[:8]
    folder = base/query_id
    folder.mkdir(exist_ok=False)
    # A failed publication is visibly incomplete; result.json is written last.
    suffix = '.jpg' if query.source_bytes[:2] == b'\xff\xd8' else '.png'
    (folder/('input'+suffix)).write_bytes(query.source_bytes)
    Image.fromarray(query.rgb).save(folder/'query_rgb.png')
    Image.fromarray(mask).save(folder/'mask.png')
    Image.fromarray(overlay(query.rgb, mask)).save(folder/'overlay.png')
    if strokes is not None:
        Image.fromarray(strokes).save(folder/'strokes.png')
    arrays = {}
    qualities = {}
    for name, values in variants.items():
        for key in ['raw', 'normalized', 'validity']:
            arrays[name+'_'+key] = values[key]
        Image.fromarray(values['canvas']).save(folder/f'foreground_{name}.png')
        Image.fromarray(values['canvas_mask']).save(folder/f'foreground_mask_{name}.png')
        qualities[name] = values['quality']
    np.savez_compressed(folder/'vectors.npz', **arrays)
    write_json(folder/'configuration.json', dict(feature_set=index.spec, normalizer=index.normalizer,
                                               selected_run=index.run, search_policies=ranked['policies']))
    # Copy only displayed candidates; verify their bytes before publication.
    # Results remain inspectable if the source tree later moves.
    result_folder = folder/'results'
    result_folder.mkdir()
    for row in ranked['results']:
        source = index.root/row['path']
        data = source.read_bytes()
        if digest(data) != row['sha256']:
            raise ValueError(f'Candidate image changed since B400 extraction: {row["filename"]}')
        local = result_folder/(str(row['rank'])+source.suffix.lower())
        local.write_bytes(data)
        row['artifact_image'] = local.relative_to(folder).as_posix()
    sheet = Image.new('RGB', (5*240, 220), 'white')
    draw = ImageDraw.Draw(sheet)
    for row in ranked['results']:
        x = (row['rank']-1)*240
        with Image.open(folder/row['artifact_image']) as image:
            preview = image.convert('RGB'); preview.thumbnail((232, 150))
            sheet.paste(preview, (x+(240-preview.width)//2, 0))
        draw.text((x+4, 154), f'#{row["rank"]} {row["filename"][:29]}', fill='black')
        draw.text((x+4, 174), f'D={row["distance"]:.6f} {row["orientation"]}', fill='black')
        draw.text((x+4, 194), row['label'], fill='black')
    sheet.save(folder/'top5.png')
    result = dict(query_id=query_id, created_at_utc=datetime.now(timezone.utc).isoformat(),
        output_directory=str(folder), index=index.describe(),
        query=dict(source_path=str(query.path), source_sha256=query.sha256, rgb_pixels_sha256=digest(query.rgb.tobytes()),
                   mask_pixels_sha256=digest(mask.tobytes()), saved_mask_sha256=digest((folder/'mask.png').read_bytes()),
                   strokes_pixels_sha256=digest(strokes.tobytes()) if strokes is not None else None,
                   width=query.rgb.shape[1], height=query.rgb.shape[0], mask=mask_info,
                   mask_statistics=mask_statistics(mask),
                   mask_diagnostics=analyze_mask(mask, mask_info.get('initial_bbox')), quality=qualities,
                   geometry_policy='stored pixels, RGB; no EXIF/ICC; B400.prepare and independent S3 canvas'),
        timings=dict(image_load_seconds=query.load_seconds, mask_seconds=mask_info.get('mask_seconds', 0.),
                     mask_load_seconds=mask_info.get('mask_load_seconds', 0.), feature_seconds=feature_seconds,
                     search_seconds=search_seconds, index_load_seconds=index.load_seconds), **ranked)
    write_json(folder/'result.json', result)
    return result


def export_result(result, destination, root):
    destination = output_base(root, destination)/result['query_id']
    source = Path(result['output_directory'])
    if destination.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(destination.resolve()):
        raise ValueError('Export destination overlaps the existing query directory')
    shutil.copytree(source, destination)  # No overwrites.
    return destination
