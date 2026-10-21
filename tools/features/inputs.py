"""Read-only validation of current approved masks, independent of historical mtimes."""
from collections import Counter
import csv
import hashlib
import io
import re
from pathlib import Path

import numpy as np
from PIL import Image

from tools.features.b400 import validate_arrays
from tools.validation.audit_images import IMAGE_SUFFIXES, label_for


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def safe_path(root, relative):
    root, relative = Path(root).resolve(), Path(relative)
    if relative.is_absolute() or '..' in relative.parts or relative==Path('.'):
        raise ValueError(f'Unsafe relative path: {relative}')
    path = root/relative
    if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path,*path.parents] if p!=root):
        raise ValueError(f'Symlink or escaping path: {relative}')
    return path


def load_pair(source, mask_path):
    source_bytes,mask_bytes = Path(source).read_bytes(),Path(mask_path).read_bytes()
    with Image.open(io.BytesIO(source_bytes)) as image:
        image.load()
        if image.format!='JPEG' or image.mode!='RGB' or image.size!=(576,384) or getattr(image,'n_frames',1)!=1:
            raise ValueError('Expected single-frame JPEG RGB 576x384')
        rgb=np.array(image)
    with Image.open(io.BytesIO(mask_bytes)) as image:
        image.load()
        if image.format!='PNG' or image.mode not in {'L','1'} or getattr(image,'n_frames',1)!=1:
            raise ValueError('Expected single-frame grayscale binary PNG')
        mask=np.array(image.convert('L'))
    validate_arrays(rgb,mask)
    return rgb,mask,hashlib.sha256(source_bytes).hexdigest(),hashlib.sha256(mask_bytes).hexdigest()


def audit(root, source_dir, segmentation_dir, inventory_csv):
    root,source_dir,segmentation_dir = map(lambda p: Path(p).resolve(),[root,source_dir,segmentation_dir])
    for p in [source_dir,segmentation_dir,Path(inventory_csv).resolve()]:
        if not p.is_relative_to(root):
            raise ValueError('Input paths must be inside project root')
    manifest_path=segmentation_dir/'manifest.csv'
    manifest=read_csv(manifest_path)
    baseline_rows=[r for r in read_csv(inventory_csv) if r['is_image_candidate']=='1']
    baseline={r['filename']:r for r in baseline_rows}
    grouped={}
    for row in manifest:
        grouped.setdefault(row['filename'],[]).append(row)
    actual={p.relative_to(source_dir).as_posix() for p in source_dir.rglob('*')
            if (p.is_file() or p.is_symlink()) and p.suffix.lower() in IMAGE_SUFFIXES}
    names=sorted(actual|set(grouped)|set(baseline))
    issues=[]
    if len(baseline)!=len(baseline_rows):
        issues.append('Duplicate filenames in requirement2 inventory')
    mask_refs=Counter(r.get('mask_path','') for r in manifest)
    records=[]
    for name in names:
        row=dict(filename=name,label=label_for(name),validation_status='failed',error='',
                 source_path='',mask_path='',source_sha256='',mask_sha256='',width=None,height=None,
                 mask_pixels=None,review_status='',review_result='',source_flags={})
        records.append(row)
        try:
            matches=grouped.get(name,[])
            if len(matches)!=1:
                raise ValueError(f'Expected one manifest row, found {len(matches)}')
            entry=matches[0]
            row.update(review_status=entry.get('review_status',''),review_result=entry.get('review_result',''),
                source_flags={k:entry.get(k,'') for k in ['suspicious','review_flags','component_count']})
            if name not in baseline:
                raise ValueError('Missing requirement2 inventory entry')
            if name not in actual:
                raise ValueError('Missing source image')
            source=safe_path(source_dir,name)
            mask_path=safe_path(segmentation_dir,entry['mask_path'])
            if not mask_path.resolve().is_relative_to(segmentation_dir/'masks'):
                raise ValueError('Mask path must be in segmentation masks directory')
            if mask_refs[entry['mask_path']]!=1:
                raise ValueError('Mask path shared by multiple manifest rows')
            overlay=safe_path(segmentation_dir,entry['overlay_path'])
            if not overlay.is_file():
                raise ValueError('Missing overlay reference')
            row.update(source_path=source.relative_to(root).as_posix(), mask_path=mask_path.relative_to(root).as_posix())
            rgb,mask,source_hash,mask_hash=load_pair(source,mask_path)
            row.update(source_sha256=source_hash,mask_sha256=mask_hash,width=rgb.shape[1],height=rgb.shape[0],
                       mask_pixels=int(np.count_nonzero(mask)))
            if source_hash!=entry.get('source_sha256') or source_hash!=baseline[name]['sha256']:
                raise ValueError('Source SHA-256 differs from manifest or requirement2 inventory')
            if mask_hash!=entry.get('mask_sha256'):
                raise ValueError('Mask SHA-256 differs from manifest')
            for key,expected in [('source_width',576),('source_height',384),('width',576),('height',384),
                                 ('total_pixels',576*384),('mask_pixels',row['mask_pixels'])]:
                if int(entry[key])!=expected:
                    raise ValueError(f'Manifest {key} differs: {entry[key]} vs {expected}')
            if not np.isclose(float(entry['mask_ratio']),row['mask_pixels']/(576*384),rtol=0,atol=1e-12):
                raise ValueError('Manifest mask_ratio differs')
            if (entry['status'],entry['review_status'],entry['review_result'])!=('success','da_duyet','dat'):
                raise ValueError('Mask lacks saved success/da_duyet/dat decision')
            row['validation_status']='success'
        except (ValueError,OSError,KeyError,TypeError) as exc:
            row['error']=type(exc).__name__+': '+re.sub(r'0x[0-9a-fA-F]+', '<address>', str(exc))
    actual_masks={p.relative_to(segmentation_dir).as_posix() for p in (segmentation_dir/'masks').rglob('*')
                  if p.is_file() or p.is_symlink()}
    for path in sorted(actual_masks-set(mask_refs)):
        if Path(path).suffix.lower()=='.png':
            issues.append(f'Unreferenced mask: {path}')
    return dict(source_directory=source_dir.relative_to(root).as_posix(),
        segmentation_directory=segmentation_dir.relative_to(root).as_posix(),
        inventory_csv=Path(inventory_csv).resolve().relative_to(root).as_posix(),
        manifest_sha256=sha256(manifest_path),inventory_sha256=sha256(inventory_csv),
        manifest_rows=len(manifest),image_files=len(actual),mask_png_files=sum(Path(p).suffix.lower()=='.png' for p in actual_masks),
        success=sum(r['validation_status']=='success' for r in records),
        failed=sum(r['validation_status']!='success' for r in records),issues=issues,records=records)
