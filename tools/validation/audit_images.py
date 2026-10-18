"""Read-only image inventory and reproducible contact sheets for the report."""
from pathlib import Path
import sys
import argparse
from collections import Counter, defaultdict
import csv
import json
import re
# Allow both `python -m tools....` and direct invocation from any cwd.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import PROJECT_ROOT, DATA_DIR, INVENTORY_DIR

from PIL import Image, ImageOps, ImageDraw

ROOT = PROJECT_ROOT
DATA = DATA_DIR / 'cropped_images_576x384'
OUT = INVENTORY_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=DATA)
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args(argv)
    data, output = args.input_dir, args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    sizes, formats, errors = Counter(), Counter(), []
    for p in sorted(data.iterdir()):
        if p.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}:
            continue
        try:
            with Image.open(p) as im:
                im.load()
                sizes[str(im.size)] += 1
                formats[im.format] += 1
        except Exception as e:
            errors.append([p.name, str(e)])
        name = re.sub(r'_\d+$', '', p.stem).lower().replace('-', '_')
        if name.startswith('canis_lupus_familiaris') or name.startswith('canis_familiaris'):
            name = 'canis_familiaris'
        if name.startswith('felis_catus'):
            name = 'felis_catus'
        groups[name].append(p.name)

    extras = '''Equus_caballus_1014.jpg Equus_asinus_0587.jpg equus-quagga_0779.jpg
Canis_familiaris_0410.jpg Canis_lupus_0922.jpg Vulpes_vulpes_0314.jpg
panthera-tigris_0250.jpg Panthera_pardus_0611.jpg
Bos_taurus_1287.jpg bubalus-bubalis_0639.jpg Bos_taurus_1254.jpg Bos_taurus_1277.jpg
Camelus_bactrianus_0303.jpg Camelus_dromedarius_0434.jpg
Camelus_dromedarius_0892.jpg Camelus_dromedarius_0894.jpg
Camelus_dromedarius_0910.jpg Camelus_dromedarius_0912.jpg
ursus-americanus_0649.jpg Ursus_arctos_1177.jpg Ursus_arctos_1206.jpg
Canis_familiaris_0052.jpg Canis_lupus_familiaris_doberman_0953.jpg
cervidae_0568.jpg cervidae_0633.jpg Equus_caballus_1024.jpg
Capra_hircus_1005.jpg Capra_hircus_1011.jpg ovis-aries_0187.jpg
Panthera_leo_1155.jpg Panthera_leo_1157.jpg Ailuropoda_melanoleuca_1218.jpg'''.split()
    selected = set(extras)
    for names in groups.values():
        selected.update(names[i] for i in sorted({0, len(names)//2, len(names)-1}))
    missing = sorted(x for x in selected if not (data / x).is_file())
    selected.difference_update(missing)
    selected = sorted(selected, key=lambda n: (next(k for k,v in groups.items() if n in v), n))
    summary = dict(image_count=sum(map(len, groups.values())), sizes=dict(sizes), formats=dict(formats),
                   labels={k: len(v) for k,v in sorted(groups.items())}, errors=errors,
                   missing_requested=missing, selected_count=len(selected))
    (output / 'image_inventory.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    with (output / 'viewed_images.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['sheet', 'filename', 'display_width', 'display_height'])
        for i,n in enumerate(selected):
            writer.writerow([f'contact_{i//16+1:02d}.jpg', n, 288, 192])
    for start in range(0, len(selected), 16):
        sheet = Image.new('RGB', (1152, 4*232), 'white')
        draw = ImageDraw.Draw(sheet)
        for j,n in enumerate(selected[start:start+16]):
            x,y = (j%4)*288, (j//4)*232
            with Image.open(data/n) as im:
                sheet.paste(ImageOps.contain(im.convert('RGB'), (288,192)), (x,y))
            # Default font is deliberately ASCII: scientific filenames are ASCII.
            draw.text((x+3,y+194), n[:38], fill='black')
            if len(n)>38:
                draw.text((x+3,y+208), n[38:], fill='black')
        sheet.save(output / f'contact_{start//16+1:02d}.jpg', quality=92)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
