"""Saved-run diagnostics: reproducibility, mask agreement, and output isolation."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
from PIL import Image

from tools.features import b400
from tools.search.diagnostics import diagnose
from tools.search.index import rank
from tools.search.query import digest, load_image, retrieve, write_json


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rng = np.random.default_rng(17)
        self.raw = rng.random((6, 400)).astype('<f4')
        self.valid = np.ones((6, 400), bool)
        # Only synthetic fixture observations are fitted; diagnostics never fit.
        self.normalizer = b400.fit_normalizer(self.raw, self.valid, 'synthetic-fixture')
        self.matrix = b400.transform(self.raw, self.valid, self.normalizer)
        self.rgb = np.full((40, 60, 3), [20, 80, 140], np.uint8)
        self.rgb[8:32, 15:47] = [220, 60, 40]
        self.approved = np.zeros((40, 60), np.uint8)
        self.approved[8:32, 15:47] = 255
        self.used = self.approved.copy()
        self.used[8:14, 15:47] = 0
        self.used[28:35, 47:52] = 255
        self.records = []
        for i in range(6):
            path = self.root/f'{i}.png'
            image = self.rgb.copy(); image[0, 0, 0] = i
            Image.fromarray(image).save(path)
            mask_path = self.root/f'{i}-mask.png'
            Image.fromarray(self.approved).save(mask_path)
            self.records.append(dict(filename=path.name, path=path.name,
                sha256=digest(path.read_bytes()), label=f'label{i}',
                mask_path=mask_path.name, mask_sha256=digest(mask_path.read_bytes()),
                validity=self.valid[i].tolist(), quality={}, review_status='da_duyet', review_result='dat'))
        self.index = SimpleNamespace(root=self.root, normalizer=self.normalizer, spec={'id': 'test-features'},
            run={'id': 'test-run', 'feature_set_id': 'test-features', 'normalizer_id': self.normalizer['id']},
            records=self.records, matrix=self.matrix, load_seconds=0.)
        self.index.describe = lambda: dict(run_id=self.index.run['id'], feature_set_id=self.index.run['feature_set_id'],
            normalizer_id=self.index.run['normalizer_id'], candidate_files=6)
        self.index.search = lambda original, flipped, query_hash=None, exclude_self=True, deduplicate=False: rank(
            self.index.matrix, self.index.records, original, flipped, query_hash, exclude_self,
            deduplicate=deduplicate)

    def saved_query(self, corpus=False, exclude_self=True):
        if corpus:
            query = load_image(self.root/'0.png')
        else:
            rgb = self.rgb.copy(); rgb[0, 0, 0] = 99
            Image.fromarray(rgb).save(self.root/'external.png')
            query = load_image(self.root/'external.png')
        extractions = [(self.raw[i], self.matrix[i], self.valid[i], {}) for i in (1, 2)]
        with mock.patch.object(b400, 'extract_normalized', side_effect=extractions):
            result = retrieve(self.index, query, self.used, {'method': 'fixture'}, exclude_self=exclude_self)
        return Path(result['output_directory']), result

    def test_external_reproduces_frozen_vectors_and_exact_rank_without_extraction(self):
        folder, result = self.saved_query()
        before = {path: digest(path.read_bytes()) for path in folder.rglob('*') if path.is_file()}
        with mock.patch.object(b400, 'fit_normalizer', side_effect=AssertionError('no fitting')):
            with mock.patch.object(b400, 'extract_normalized', side_effect=AssertionError('no external re-extraction')):
                report = diagnose(self.index, folder)
        self.assertTrue(all(value['matches'] for value in report['identity'].values()))
        self.assertTrue(all(report['configuration_matches'].values()))
        self.assertTrue(all(value['exact_match'] for value in report['normalization'].values()))
        self.assertTrue(report['reranking']['all_saved_hits_match'])
        self.assertFalse(report['reference_mask']['available'])
        self.assertNotIn('comparisons', report['reference_mask'])
        self.assertIn('No automatic visual relevance', report['interpretation']['relevance'])
        self.assertEqual([hit['filename'] for hit in report['hits']], [hit['filename'] for hit in result['results']])
        self.assertTrue((Path(report['output_directory'])/'diagnostics.json').is_file())
        self.assertTrue(all(digest(path.read_bytes()) == sha for path, sha in before.items()))
        second = diagnose(self.index, folder)
        self.assertNotEqual(second['output_directory'], report['output_directory'])

    def test_decomposition_uses_winning_variant_and_actual_candidate_row(self):
        folder, _ = self.saved_query()
        report = diagnose(self.index, folder)
        saw_flipped = False
        for hit in report['hits']:
            if hit['orientation'] == 'flipped': saw_flipped = True
            q = self.matrix[2 if hit['orientation'] == 'flipped' else 1].astype(float)
            squared = (q-self.matrix[hit['candidate_row']].astype(float))**2
            parts = hit['decomposition']
            self.assertTrue(parts['contributions_sum_matches'])
            self.assertAlmostEqual(parts['distance'], hit['distance'], places=12)
            self.assertAlmostEqual(sum(block['distance'] for block in parts['subblocks']), hit['distance'], places=12)
            for block in parts['subblocks']:
                self.assertAlmostEqual(block['distance'], squared[block['start']:block['stop']].sum(), places=12)
        self.assertTrue(saw_flipped)

    def test_reference_agreement_and_full_flip_preserve_self_exclusion(self):
        folder, _ = self.saved_query(corpus=True)
        expected_d2 = float(np.square(self.matrix[1].astype(float)-self.matrix[0].astype(float)).sum())
        flipped_result = (self.raw[0], self.matrix[0], self.valid[0], {})
        with mock.patch.object(b400, 'fit_normalizer', side_effect=AssertionError('no fitting')):
            with mock.patch.object(b400, 'extract_normalized', return_value=flipped_result) as extract:
                report = diagnose(self.index, folder)
        extract.assert_called_once()
        np.testing.assert_array_equal(extract.call_args.args[0], load_image(self.root/'0.png').rgb[:, ::-1])
        np.testing.assert_array_equal(extract.call_args.args[1], self.approved[:, ::-1])
        self.assertIs(extract.call_args.args[2], self.normalizer)
        ref = report['reference_mask']['comparisons'][0]
        a, b = self.used > 0, self.approved > 0
        self.assertAlmostEqual(ref['agreement']['iou'], (a & b).sum()/(a | b).sum())
        self.assertEqual(ref['agreement']['symmetric_difference_pixels'], int((a ^ b).sum()))
        self.assertEqual(ref['agreement']['used_area_pixels'], int(a.sum()))
        self.assertEqual(ref['agreement']['approved_area_pixels'], int(b.sum()))
        self.assertIn('not segmentation accuracy', ref['agreement']['interpretation'])
        self.assertAlmostEqual(ref['original_vector_comparison']['distance'], expected_d2, places=12)
        self.assertTrue(ref['approved_mask_search']['exclude_self'])
        self.assertEqual(ref['approved_mask_search']['excluded_self_files'], 1)
        self.assertNotIn('0.png', [hit['filename'] for hit in ref['approved_mask_search']['results']])

    def test_include_self_policy_preserved_in_reference_search(self):
        folder, _ = self.saved_query(corpus=True, exclude_self=False)
        with mock.patch.object(b400, 'extract_normalized', return_value=(self.raw[0], self.matrix[0], self.valid[0], {})):
            report = diagnose(self.index, folder)
        ref = report['reference_mask']['comparisons'][0]['approved_mask_search']
        self.assertFalse(ref['exclude_self'])
        self.assertEqual(ref['excluded_self_files'], 0)
        self.assertEqual(ref['results'][0]['filename'], '0.png')

    def test_finite_vector_and_saved_rank_corruption_are_reported(self):
        folder, result = self.saved_query()
        with np.load(folder/'vectors.npz', allow_pickle=False) as data:
            arrays = {key: data[key] for key in data.files}
        arrays['original_normalized'] = arrays['original_normalized'].copy()
        arrays['original_normalized'][0] += 1
        np.savez_compressed(folder/'vectors.npz', **arrays)
        result['results'][0]['distance'] += 10
        write_json(folder/'result.json', result)
        report = diagnose(self.index, folder)
        self.assertFalse(report['normalization']['original']['exact_match'])
        self.assertGreater(report['normalization']['original']['max_absolute_difference'], .9)
        self.assertFalse(report['reranking']['all_saved_hits_match'])

    def test_identity_and_configuration_mismatch_are_explicit(self):
        folder, result = self.saved_query()
        result['index']['normalizer_id'] = 'different'
        write_json(folder/'result.json', result)
        configuration = json.loads((folder/'configuration.json').read_text())
        configuration['selected_run']['id'] = 'different'
        write_json(folder/'configuration.json', configuration)
        report = diagnose(self.index, folder)
        self.assertFalse(report['identity']['normalizer_id']['matches'])
        self.assertFalse(report['configuration_matches']['selected_run'])

    def test_changed_artifacts_invalid_vectors_and_escape_destinations_fail(self):
        folder, _ = self.saved_query()
        with self.assertRaisesRegex(ValueError, 'inside'):
            diagnose(self.index, folder, self.root/'outside')
        self.assertFalse((self.root/'outside').exists())
        original = (folder/'mask.png').read_bytes()
        Image.fromarray(self.approved).save(folder/'mask.png')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            diagnose(self.index, folder)
        (folder/'mask.png').write_bytes(original)
        with np.load(folder/'vectors.npz', allow_pickle=False) as data:
            arrays = {key: data[key] for key in data.files}
        arrays['original_validity'] = np.full(400, 2, np.uint8)
        np.savez_compressed(folder/'vectors.npz', **arrays)
        with self.assertRaisesRegex(ValueError, '0/1'):
            diagnose(self.index, folder)

    def test_reference_mask_hash_is_checked(self):
        folder, _ = self.saved_query(corpus=True)
        Image.fromarray(self.used).save(self.root/'0-mask.png')
        with self.assertRaisesRegex(ValueError, 'Approved mask bytes changed'):
            diagnose(self.index, folder)


if __name__ == '__main__':
    unittest.main()
