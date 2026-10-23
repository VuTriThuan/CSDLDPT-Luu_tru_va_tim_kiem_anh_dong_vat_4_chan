"""Structural mask diagnostics, never a claim of segmentation accuracy."""
import cv2
import numpy as np


def analyze_mask(mask, initial_bbox=None):
    if mask.ndim != 2 or mask.dtype != np.uint8 or not np.isin(mask, [0, 255]).all():
        raise ValueError('Mask diagnostics require binary uint8 0/255')
    foreground = mask != 0
    pixels = int(foreground.sum())
    if not pixels or pixels == mask.size:
        raise ValueError('Mask diagnostics require both foreground and background')
    count, _, stats, _ = cv2.connectedComponentsWithStats(foreground.astype(np.uint8), connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    x, y, w, h = map(int, cv2.boundingRect(mask))
    flags = []
    ratio = pixels/mask.size
    if ratio < .05: flags.append('small_foreground')
    if ratio > .85: flags.append('large_foreground')
    if count-1 >= 8: flags.append('many_fragments')
    significant = int(np.count_nonzero(areas >= max(1, mask.size*.001)))
    if significant >= 3: flags.append('several_large_components')
    # A single distant pixel can change B400's all-component bbox and canvas.
    # Expose the effect, but never delete a component that may be a body part.
    substantial = stats[1:][areas >= max(4, mask.size*.0001)]
    substantial_bbox = None
    bbox_inflation = None
    if len(substantial):
        left = int(substantial[:, cv2.CC_STAT_LEFT].min())
        top = int(substantial[:, cv2.CC_STAT_TOP].min())
        right = int((substantial[:, cv2.CC_STAT_LEFT]+substantial[:, cv2.CC_STAT_WIDTH]).max())
        bottom = int((substantial[:, cv2.CC_STAT_TOP]+substantial[:, cv2.CC_STAT_HEIGHT]).max())
        substantial_bbox = [left, top, right-left, bottom-top]
        bbox_inflation = float(w*h/((right-left)*(bottom-top)))
        if bbox_inflation > 1.1: flags.append('tiny_components_expand_bbox')
    edge_pixels = int(foreground[0].sum()+foreground[-1].sum()+foreground[1:-1, 0].sum()+foreground[1:-1, -1].sum())
    if edge_pixels: flags.append('touches_image_edge')
    bbox_border_fraction = None
    if initial_bbox is not None:
        bx, by, bw, bh = map(int, initial_bbox)
        if min(bx, by) < 0 or min(bw, bh) < 1 or bx+bw > mask.shape[1] or by+bh > mask.shape[0]:
            raise ValueError('Initial bbox outside mask')
        part = foreground[by:by+bh, bx:bx+bw]
        # Inspect the actual initialization bbox; no fixed ring at pixel 10.
        border = np.zeros(part.shape, bool)
        thickness = min(3, max(1, min(bw, bh)//2))
        border[:thickness] = True; border[-thickness:] = True
        border[:, :thickness] = True; border[:, -thickness:] = True
        bbox_border_fraction = float(part[border].mean())
        if bbox_border_fraction > .15: flags.append('near_initial_bbox_border')
    return dict(foreground_pixels=pixels, foreground_fraction=ratio, source_bbox=[x, y, w, h],
                component_count=count-1, significant_component_count=significant,
                largest_component_fraction=float(areas.max()/pixels),
                substantial_component_bbox=substantial_bbox, bbox_area_inflation_from_tiny_components=bbox_inflation,
                image_edge_pixels=edge_pixels, initial_bbox=list(initial_bbox) if initial_bbox is not None else None,
                initial_bbox_border_fraction=bbox_border_fraction, review_flags=flags,
                interpretation='Structural review cues only; no flags does not certify complete animal or clean background',
                thresholds=dict(small_foreground=.05, large_foreground=.85, many_fragments=8,
                                significant_component_fraction=.001, bbox_border_fraction=.15))


def review_message(diagnostics):
    flags = diagnostics['review_flags']
    extra = ' Có mảnh nhỏ làm thay đổi khung chủ thể.' if 'tiny_components_expand_bbox' in flags else ''
    return (f'Mask: {diagnostics["foreground_fraction"]:.1%} ảnh, '
            f'{diagnostics["component_count"]} mảnh. '
            'Kiểm tra đủ đầu/tai/chân/đuôi, loại cây/cỏ/nền; chỉ số kỹ thuật không xác nhận mask đúng.'+extra)
