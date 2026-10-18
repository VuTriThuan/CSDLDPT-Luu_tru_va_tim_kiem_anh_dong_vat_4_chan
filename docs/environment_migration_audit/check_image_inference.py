"""Exercise regenerate_masks and resume with one generated image in the new environment."""
import csv
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw
from tools.segmentation import regenerate_masks as batch


def main():
    with tempfile.TemporaryDirectory(prefix='btl_new_env_inference_') as tmp:
        root = Path(tmp)
        source, previous, output = root/'source', root/'previous', root/'results'
        queue = previous/'overlays/needs_revision'
        for path in [source, queue, previous/'masks']:
            path.mkdir(parents=True)
        name = 'temporary_animal.jpg'
        image = Image.new('RGB', (576,384), (205,215,225))
        ImageDraw.Draw(image).ellipse((120,65,450,325), fill=(120,55,25))
        image.save(source/name)
        image = Image.open(source/name).convert('RGB')
        mask_image = Image.new('L',image.size,0)
        ImageDraw.Draw(mask_image).ellipse((120,65,450,325), fill=255)
        mask = np.asarray(mask_image)
        mask_image.save(previous/'masks'/f'{name}.png')
        batch.overlay(image,mask).save(queue/f'{name}.png')
        with (previous/'manifest.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['filename','source_sha256','mask_path','overlay_path'])
            writer.writeheader()
            writer.writerow(dict(filename=name,source_sha256=batch.sha256(source/name),
                                  mask_path=f'masks/{name}.png',overlay_path=f'overlays/needs_revision/{name}.png'))
        protected={p:p.read_bytes() for base in [source,previous] for p in base.rglob('*') if p.is_file()}
        args=batch.parse_args(['--source-dir',str(source),'--previous-dir',str(previous),
                               '--queue-dir',str(queue),'--output-dir',str(output),'--limit','1','--threads','1'])
        model_hash=batch.sha256(args.model)
        assert model_hash=='8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491'
        with redirect_stdout(io.StringIO()):
            assert batch.run(args)==0
            args.resume=True
            assert batch.run(args)==0
        summary=json.loads((output/'summary.json').read_text())
        assert summary['success']==summary['reused_this_run']==1 and summary['processed_this_run']==0
        row=next(csv.DictReader((output/'manifest.csv').open()))
        assert batch.reusable(row,output)
        assert {p:p.read_bytes() for p in protected}==protected
        with Image.open(output/row['mask_path']) as opened:
            assert opened.size==(576,384) and set(np.unique(np.asarray(opened))).issubset({0,255})
        result=dict(verified=True,interpreter=sys.executable,model_sha256=model_hash,
                    temporary_images_processed=1,new_run_resume_reused=1,real_data_written=False,
                    numpy=np.__version__,pillow=Image.__version__,onnxruntime=batch.ort.__version__)
        Path(__file__).with_name('image_inference_check.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))


if __name__=='__main__':
    main()
