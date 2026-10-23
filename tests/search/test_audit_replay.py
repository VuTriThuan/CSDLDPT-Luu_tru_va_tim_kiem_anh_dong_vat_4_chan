"""Regression for the audit entry point and shared historical policy parser."""
import copy
from types import SimpleNamespace
import unittest

import numpy as np

from tools.search.index import rank
from tools.search.policies import search_options
from tools.search.replay import replay_ranking


class ReplayTests(unittest.TestCase):
    def test_duplicate_hash_include_default_and_historical_replays(self):
        matrix = np.zeros((7, 400), np.float32)
        matrix[2:, 0] = np.arange(1, 6)
        records = [dict(filename=str(i), path=str(i), sha256='same' if i < 2 else str(i)) for i in range(7)]
        identity = dict(run_id='r', feature_set_id='f', normalizer_id='n')
        index = SimpleNamespace(describe=lambda: identity)
        index.search = lambda a, b, query_hash=None, **kw: rank(matrix, records, a, b, query_hash, **kw)
        q = np.zeros(400, np.float32)
        for exclude, deduplicate, expected in [(False, False, ['0', '1']),
                                               (True, False, ['2', '3']),
                                               (False, True, ['0', '2']), (True, True, ['2', '3'])]:
            with self.subTest(exclude=exclude, deduplicate=deduplicate):
                result = dict(index=identity, query=dict(source_sha256='same'),
                              **index.search(q, q, 'same', exclude_self=exclude, deduplicate=deduplicate))
                report = replay_ranking(index, result, q, q)
                self.assertTrue(report['ranking_reproduces_exactly'], report['reasons'])
                self.assertEqual([h['filename'] for h in report['computed_results'][:2]], expected)
                if not exclude and not deduplicate:
                    self.assertEqual([h['distance'] for h in report['computed_results'][:2]], [0., 0.])
                if exclude:
                    self.assertEqual(result['excluded_self_files'], 2)
                altered = copy.deepcopy(result)
                altered['results'][0]['distance'] += .25
                mismatch = replay_ranking(index, altered, q, q)
                self.assertFalse(mismatch['ranking_reproduces_exactly'])
                self.assertEqual(mismatch['reasons'][0]['field'], 'distance')
                self.assertEqual(altered['results'][0]['distance'], result['results'][0]['distance']+.25)

    def test_missing_or_unknown_policy_fails_explicitly(self):
        for result in ({}, {'policies': {'self_match': 'guess'}}):
            with self.assertRaisesRegex(ValueError, 'Unknown saved self_match'):
                search_options(result)
