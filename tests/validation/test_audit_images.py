"""Coverage, failure accounting and numerical checks for requirement 2."""
from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
from tools.validation import audit_images as audit
from tools.validation import verify_image_analysis as verifier


class AuditImagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'output'

    def run_audit(self):
        with redirect_stdout(io.StringIO()):
            return audit.main(['--input-dir', str(self.source), '--output-dir', str(self.output)])

    def read_csv(self, name):
        with (self.output / name).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))

    def test_all_images_without_sampling_and_unsupported_file_is_accounted(self):
        for index in range(90):
            Image.new('RGB', (8, 4), 'red').save(self.source / f'Canis_familiaris_{index:04d}.png')
        (self.source / 'metadata.csv').write_text('metadata')
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        self.assertEqual(self.run_audit(), 0)
        summary = json.loads((self.output / 'image_inventory.json').read_text())
        self.assertEqual(summary['image_count'], 90)
        self.assertEqual(summary['file_count'], 91)
        self.assertEqual(summary['labels'], {'canis_familiaris': 90})
        self.assertEqual(summary['technical_status_counts'], {'success': 90})
        self.assertEqual(summary['feature_status_counts'], {'success': 90})
        self.assertTrue(all(summary['checks'].values()))
        records = self.read_csv('image_processing.csv')
        self.assertEqual(len(records), 91)
        self.assertEqual(records[-1]['technical_error'], 'unsupported_extension')
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, before)
        first_metrics = (self.output / 'feature_metrics.csv').read_bytes()
        with np.load(self.output / 'full_frame_color_features.npz', allow_pickle=False) as arrays:
            self.assertEqual(arrays['features'].shape, (90, 176))
            self.assertEqual(len(set(arrays['feature_names'])), 176)
            self.assertEqual(len(set(arrays['filenames'])), 90)
            first_vectors = arrays['features'].copy()
        self.assertEqual(self.run_audit(), 0)
        self.assertEqual((self.output / 'feature_metrics.csv').read_bytes(), first_metrics)
        with np.load(self.output / 'full_frame_color_features.npz') as arrays:
            np.testing.assert_array_equal(arrays['features'], first_vectors)

    def test_decode_failure_feature_failure_and_skip_are_separate(self):
        Image.new('RGB', (8, 4), 'blue').save(self.source / 'bos-taurus_0001.png')
        Image.new('RGB', (1, 1), 'red').save(self.source / 'bos-taurus_0002.png')
        (self.source / 'bos-taurus_0003.jpg').write_bytes(b'corrupt JPEG')
        (self.source / 'bos-taurus_0004.jpg').symlink_to(self.source / 'bos-taurus_0003.jpg')
        self.assertEqual(self.run_audit(), 1)
        records = self.read_csv('image_processing.csv')
        self.assertEqual([r['technical_status'] for r in records], ['success', 'success', 'failed', 'skipped'])
        self.assertEqual([r['feature_status'] for r in records], ['success', 'failed', 'skipped', 'skipped'])
        counts = self.read_csv('label_counts.csv')[0]
        self.assertEqual([counts[k] for k in ['input_count', 'technical_success', 'technical_failed',
                                            'technical_skipped', 'feature_success', 'feature_failed', 'feature_skipped']],
                         ['4', '2', '1', '1', '1', '1', '2'])
        self.assertTrue(all(r['technical_error'] or r['feature_error'] for r in records[1:]))
        self.assertEqual(len(self.read_csv('feature_metrics.csv')), 1)

    def test_constant_image_expected_measurements(self):
        metrics, vector = audit.measure_features(np.full((4, 8, 3), 128, dtype=np.uint8))
        self.assertAlmostEqual(metrics['gray_mean'], 128 / 255)
        self.assertEqual(metrics['saturation_mean'], 0)
        for key in ['gray_std', 'dark_fraction', 'bright_fraction', 'gray_entropy_bits',
                    'sobel_mean', 'sobel_strong_fraction', 'laplacian_variance']:
            self.assertAlmostEqual(metrics[key], 0)
        self.assertEqual(vector[:16].sum(), 0)  # Hue has zero saturation weight.
        self.assertAlmostEqual(vector[16:24].sum(), 1)
        self.assertAlmostEqual(vector[24:32].sum(), 1)
        self.assertTrue(np.isfinite(vector).all())

    def test_multiple_frames_are_not_silently_reduced_to_one(self):
        Image.new('RGB', (8, 4), 'red').save(self.source / 'test_0001.gif', save_all=True,
            append_images=[Image.new('RGB', (8, 4), 'blue')], duration=50)
        self.assertEqual(self.run_audit(), 1)
        row = self.read_csv('image_processing.csv')[0]
        self.assertEqual(row['technical_status'], 'success')
        self.assertEqual(row['frame_count'], '2')
        self.assertEqual(row['feature_status'], 'skipped')
        self.assertEqual(row['feature_error'], 'multi_frame_unsupported')
        with np.load(self.output / 'full_frame_color_features.npz') as arrays:
            self.assertEqual(arrays['features'].shape, (0, 176))

    def test_duplicate_basenames_recorded_and_empty_input_is_not_success(self):
        self.assertEqual(self.run_audit(), 1)
        for folder in ['a', 'b']:
            (self.source / folder).mkdir()
            Image.new('RGB', (8, 4), 'red').save(self.source / folder / 'test_0001.png')
        self.assertEqual(self.run_audit(), 1)
        summary = json.loads((self.output / 'image_inventory.json').read_text())
        self.assertEqual(summary['unique_image_filenames'], 2)
        self.assertEqual(summary['unique_image_basenames'], 1)
        self.assertEqual(summary['duplicate_image_basenames'], ['test_0001.png'])
        self.assertEqual(len(self.read_csv('feature_metrics.csv')), 2)

    def test_output_cannot_overlap_input(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            audit.audit(self.source, self.source / 'output')
        self.assertEqual(list(self.source.iterdir()), [])

    def test_verifier_detects_modified_sources_and_inconsistent_statistics(self):
        path = self.source / 'test_0001.png'
        Image.new('RGB', (8, 4), 'red').save(path)
        self.assertEqual(self.run_audit(), 0)
        result = verifier.verify(self.source, self.output)
        self.assertEqual(result['source_hashes_checked'], 1)
        summary_path = self.output / 'feature_summary.json'
        original = summary_path.read_text()
        summary = json.loads(original)
        summary['statistics']['gray_mean']['mean'] += 0.1
        summary_path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError, 'statistic mismatch'):
            verifier.verify(self.source, self.output)
        summary_path.write_text(original)
        Image.new('RGB', (8, 4), 'blue').save(path)
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            verifier.verify(self.source, self.output)


if __name__ == '__main__':
    unittest.main()
