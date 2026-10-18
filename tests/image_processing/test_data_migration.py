"""Exercise legacy state and image operations only inside small temporary copies."""
import argparse
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image
from tools.image_processing import auto_crop as crop, rename_images as rename, review_images as review
from tools.project_paths import resolve_data_reference, rejected_directory


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DataMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='btl_data_copy_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        data = PROJECT_ROOT / 'data'
        self.original_source = data / ('source_images' if (data / 'source_images').exists() else 'anh-chua-loc')
        self.original_crops = data / ('cropped_images_576x384' if (data / 'cropped_images_576x384').exists() else 'anh-da-cat-576x384')
        self.original_rejected = data / ('rejected_crops' if (data / 'rejected_crops').exists() else 'anh-da-cat-576x384-da-xoa')

    def fixture(self):
        source = self.root / 'data/source_images'
        output = self.root / 'data/cropped_images_576x384'
        rejected = self.root / 'data/rejected_crops'
        for folder in [source, output, rejected]:
            folder.mkdir(parents=True)
        state = json.loads((self.original_crops / '_cat_tu_dong.json').read_text())
        selected = {}
        categories = set()
        for key, record in state['images'].items():
            name = record['output']
            active = (self.original_crops / name).is_file()
            category = (record['status'], active)
            if category in categories:
                continue
            categories.add(category)
            selected[key] = record
            shutil.copy2(self.original_source / key, source / key)
            shutil.copy2((self.original_crops if active else self.original_rejected) / name,
                         (output if active else rejected) / name)
            if len(categories) == 4:
                break
        self.assertEqual(len(categories), 4)
        state['images'] = selected
        # Start with the original path layout, as in the step-1 backup.
        state['source'] = str(PROJECT_ROOT / 'data/anh-chua-loc')
        state['source_relative'] = '../anh-chua-loc'
        crop.atomic_json(output / '_cat_tu_dong.json', state)
        return source, output, rejected, state

    def args(self, source, output=None):
        return argparse.Namespace(input=source, output=output, repair_borders=False,
                                  recursive=False, fill=0.85, threshold=0.25, model='u2net',
                                  force=False, limit=0, model_dir=Path.home() / '.cache/animal-crop', threads=2)

    def test_legacy_relative_and_absolute_state_paths_are_accepted(self):
        source, output, _, state = self.fixture()
        path = output / '_cat_tu_dong.json'
        before = path.read_bytes()
        self.assertEqual(crop.load_state(path, source)['source'], str(source))
        self.assertEqual(path.read_bytes(), before, 'Loading must not write the state')
        state.pop('source_relative')
        state['source'] = str(source.with_name('anh-chua-loc'))
        crop.atomic_json(path, state)
        self.assertEqual(crop.load_state(path, source)['source'], str(source))

    def test_unrelated_source_is_still_rejected(self):
        source, output, _, _ = self.fixture()
        other = source.with_name('unrelated_source')
        other.mkdir()
        with self.assertRaises(ValueError):
            crop.load_state(output / '_cat_tu_dong.json', other)

    def test_resume_retains_flip_delete_and_existing_state_discrepancies(self):
        source, output, rejected, state = self.fixture()
        files = [*source.glob('*.jpg'), *source.glob('*.png'), *output.glob('*.jpg'), *rejected.glob('*.jpg')]
        before = {p: sha(p) for p in files}
        with patch.object(crop, 'ensure_model', side_effect=AssertionError('Existing images must not be recropped')), \
                redirect_stdout(io.StringIO()):
            crop.run_batch(self.args(source))  # No explicit output: exercise the new default sibling.
        current = json.loads((output / '_cat_tu_dong.json').read_text())
        self.assertEqual(current['source_relative'], '../source_images')
        self.assertEqual(current['source'], str(source))
        self.assertEqual(current['images'], state['images'])
        self.assertEqual({p: sha(p) for p in files}, before)
        self.assertFalse((source.parent / 'anh-da-cat-576x384').exists())

    def test_review_delete_flip_and_undo_use_rejected_crops(self):
        _, output, rejected, state = self.fixture()
        path = next(output.glob('*.jpg'))
        before = path.read_bytes()
        store = review.ReviewStore(output)
        store.flip(path)
        store.delete(path)
        self.assertTrue((rejected / path.name).is_file())
        self.assertFalse((output.parent / 'cropped_images_576x384-da-xoa').exists())
        store.undo()
        store.undo()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads((output / '_cat_tu_dong.json').read_text())['images'], state['images'])
        self.assertEqual(rejected_directory(output), rejected)
        self.assertEqual(rejected_directory(output.with_name('custom')), output.with_name('custom-da-xoa'))

    def test_rename_preview_apply_and_resume_on_copied_data(self):
        source, output, rejected, _ = self.fixture()
        hashes = Counter(sha(p) for folder in [source, output, rejected]
                         for p in folder.iterdir() if p.suffix.lower() in crop.EXTENSIONS)
        before = (output / '_cat_tu_dong.json').read_bytes()
        with patch.object(rename, 'SOURCE', source), patch.object(rename, 'CROPPED', output), \
                patch.object(rename, 'DELETED', rejected):
            moves, state, missing = rename.build_plan()
            self.assertEqual(missing, 0)
            self.assertEqual((output / '_cat_tu_dong.json').read_bytes(), before)
            with rename.folder_lock(output):
                rename.apply_plan(moves, state)
        current = json.loads((output / '_cat_tu_dong.json').read_text())
        self.assertEqual(current['source_relative'], '../source_images')
        self.assertEqual(current['source'], str(source))
        self.assertEqual(hashes, Counter(sha(p) for folder in [source, output, rejected]
                                        for p in folder.iterdir() if p.suffix.lower() in crop.EXTENSIONS))
        with patch.object(crop, 'ensure_model', side_effect=AssertionError('Rename must retain progress')), \
                redirect_stdout(io.StringIO()):
            crop.run_batch(self.args(source, output))

    def test_legacy_snapshot_paths_resolve_without_mutating_snapshots(self):
        source, _, _, _ = self.fixture()
        name = next(source.iterdir()).name
        relative = 'data/anh-chua-loc/' + name
        self.assertEqual(resolve_data_reference(relative, self.root), source / name)
        unrelated = self.root / 'elsewhere/anh-chua-loc' / name
        self.assertEqual(resolve_data_reference(unrelated, self.root), unrelated)

    def test_new_crop_and_second_run_with_one_real_copied_image(self):
        model = Path.home() / '.cache/animal-crop/u2net.onnx'
        self.assertTrue(model.is_file(), 'Cached model required; test never downloads it')
        source = self.root / 'data/source_images'
        source.mkdir(parents=True)
        original = next(p for p in sorted(self.original_source.iterdir()) if p.suffix.lower() in crop.EXTENSIONS)
        copied = source / original.name
        shutil.copy2(original, copied)
        before = sha(copied)
        with patch.object(crop, 'ensure_model', return_value=model), \
                patch.object(crop.urllib.request, 'urlopen', side_effect=AssertionError('No downloads')), \
                redirect_stdout(io.StringIO()):
            crop.run_batch(self.args(source))
        output = source.parent / 'cropped_images_576x384'
        state = json.loads((output / '_cat_tu_dong.json').read_text())
        record = state['images'][copied.name]
        self.assertEqual(record['status'], 'saved', record.get('error'))
        artifact = output / record['output']
        with Image.open(artifact) as image:
            self.assertEqual(image.size, (576, 384))
            self.assertEqual(image.format, 'JPEG')
        self.assertEqual(sha(copied), before)
        result_hash = sha(artifact)
        with patch.object(crop, 'ensure_model', side_effect=AssertionError('Must reuse the copied result')), \
                redirect_stdout(io.StringIO()):
            crop.run_batch(self.args(source))
        self.assertEqual(sha(artifact), result_hash)


if __name__ == '__main__':
    unittest.main()
