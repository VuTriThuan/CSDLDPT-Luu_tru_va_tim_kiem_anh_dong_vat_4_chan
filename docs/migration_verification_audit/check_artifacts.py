"""Decode all live artifacts; check binary masks and source/mask/overlay pixels."""
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image
from tools.segmentation import run_grabcut as gc
from tools import project_paths as paths
from docs.migration_verification_audit.prepare import write


def main():
    output=paths.GRABCUT_OUTPUT_DIR
    rows=list(csv.DictReader((output/'manifest.csv').open(newline='')))
    pixels=[]
    for index,row in enumerate(rows):
        assert row['quicklook_path']==f'quicklooks/batch_{index//8+1:03d}.jpg'
        assert Path(row['mask_path']).name==Path(row['overlay_path']).name==row['filename']+'.png'
        source,_,_=gc.read_image(paths.CROPPED_IMAGES_DIR/row['filename'])
        with Image.open(output/row['mask_path']) as image:
            assert image.format=='PNG' and image.mode=='L' and image.size==(576,384)
            mask=np.asarray(image)
        assert set(np.unique(mask)).issubset({0,255})
        assert int(np.count_nonzero(mask))==int(row['mask_pixels'])
        assert abs(np.count_nonzero(mask)/mask.size-float(row['mask_ratio']))<1e-12
        with Image.open(output/row['overlay_path']) as image:
            actual=np.asarray(image.convert('RGB'))
        expected=gc.make_overlay(source,mask)
        difference=np.max(np.abs(actual.astype(np.int16)-expected.astype(np.int16)),axis=2)
        assert np.max(difference)<=1,(row['filename'],int(np.max(difference)))
        if np.any(difference):
            pixels.append(dict(filename=row['filename'],nonexact_pixels=int(np.count_nonzero(difference)),max_channel_difference=int(np.max(difference))))
    decoded=0
    for start in range(0,len(rows),8):
        batch=rows[start:start+8]
        with Image.open(output/batch[0]['quicklook_path']) as image:
            assert image.size==(864,30+254*len(batch))
    for folder in ['quicklooks','manual_edits']:
        for path in (output/folder).rglob('*'):
            if path.suffix.lower() in {'.png','.jpg'}:
                with Image.open(path) as image:
                    image.verify()
                decoded+=1
    write('artifact_content_verification.json',dict(verified=True,mask_overlay_pairs_checked=len(rows),
        quicklook_and_history_images_decoded=decoded,source_mask_overlay_pixel_tolerance=1,
        overlay_nonexact_pixels=pixels,quicklook_batch_indices_and_dimensions_verified=True,
        annotation_quality_or_segmentation_accuracy_evaluated=False))
    print(json.dumps(dict(verified=True,mask_overlay_pairs_checked=len(rows),quicklook_history_images_decoded=decoded,nonexact_pixels=pixels)))


if __name__=='__main__':
    main()
