"""Analysis math is checked independently from the saved-run experiment."""
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools.search.group_analysis import CONFIGURATIONS, projected_ranking, select_queries
from tools.search.index import rank
from tools.search.query import write_json


class GroupAnalysisTests(unittest.TestCase):
    def test_single_groups_and_ablations_use_saved_coordinates_without_reweighting(self):
        q = np.zeros(400, np.float32)
        x = q.copy(); x[[0, 48, 148, 272]] = [1, 2, 3, 4]
        matrix = x[None].copy()
        rows = [dict(filename='x', path='x', sha256='x')]
        expected = dict(color=1., texture=4., shape=9., layout=16.)
        def distance(name):
            return projected_ranking(matrix, rows, q, q, CONFIGURATIONS[name], None, True, False)[0]['distance']
        self.assertEqual(distance('full'), 30.)
        for name, value in expected.items():
            self.assertEqual(distance('only_'+name), value)
            self.assertEqual(distance('without_'+name), 30.-value)
        np.testing.assert_array_equal(matrix, x[None])

    def test_orientation_reselected_for_subset_never_sum_group_minima(self):
        a = np.zeros(400, np.float32); b = a.copy(); b[[0, 148]] = [2, 3]
        x = a.copy(); x[0] = 2
        rows = [dict(filename='x', path='x', sha256='x')]
        def hit(name):
            return projected_ranking(x[None], rows, a, b, CONFIGURATIONS[name], None, True, False)[0]
        self.assertEqual((hit('full')['distance'], hit('full')['orientation']), (4., 'original'))
        self.assertEqual((hit('only_color')['distance'], hit('only_color')['orientation']), (0., 'flipped'))
        self.assertEqual((hit('only_shape')['distance'], hit('only_shape')['orientation']), (0., 'original'))
        self.assertEqual(hit('without_color')['distance'], 0.)

    def test_full_reproduces_search_with_duplicate_self_ties_and_historical_policy(self):
        rng = np.random.default_rng(3)
        matrix = rng.random((9, 400)).astype(np.float32); matrix[1] = matrix[0]
        rows = [dict(filename=str(i), path=str(i), sha256='same' if i < 2 else str(i)) for i in range(9)]
        for exclude in (True, False):
            for deduplicate in (True, False):
                expected = rank(matrix, rows, matrix[0], matrix[2], 'same', exclude, deduplicate=deduplicate)
                actual = projected_ranking(matrix, rows, matrix[0], matrix[2], CONFIGURATIONS['full'], 'same', exclude, deduplicate)
                self.assertEqual([(h['filename'], h['orientation']) for h in actual[:5]],
                                 [(h['filename'], h['orientation']) for h in expected['results']])
                np.testing.assert_allclose([h['distance'] for h in actual[:5]],
                                           [h['distance'] for h in expected['results']], rtol=1e-14, atol=1e-14)

    def test_selection_uses_earliest_query_not_distance_or_mask_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for qid, source in [('001', 'ngua_bad.jpg'), ('009', 'Equus_caballus_good.jpg'),
                                ('002', 'Bos_taurus_001.jpg'), ('003', 'Canis_familiaris_004.jpg')]:
                folder = base/qid; folder.mkdir()
                write_json(folder/'result.json', dict(query=dict(source_path=source)))
                for name in ('vectors.npz', 'mask.png', 'query_rgb.png', 'configuration.json'):
                    (folder/name).touch()
            eligible, selected = select_queries(base)
            self.assertEqual(len(eligible['horse']), 2)
            self.assertEqual(selected['horse'].parent.name, '001')
            (base/'001/mask.png').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing selected-family artifact'):
                select_queries(base)
