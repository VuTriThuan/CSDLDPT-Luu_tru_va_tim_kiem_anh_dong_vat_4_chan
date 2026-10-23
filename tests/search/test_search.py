import contextlib
import copy
import io
import json
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest
from unittest import mock

import cv2
import numpy as np
from PIL import Image

from tools.features import b400, storage
from tools.features.cli import feature_set
from tools.features.inputs import sha256
from tools.search import cli, evaluation
from tools.search.index import SearchIndex, rank
from tools.search.query import (load_image, load_mask, create_mask, refine, retrieve,
                                output_base, write_json, export_result)


def record(name, hash_value=None, label='arbitrary'):
    return dict(filename=name, path=name, sha256=hash_value or name, label=label,
                validity=[True]*400, quality={})


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.zero = np.zeros(400, np.float32)

    def test_known_distance_all_groups_and_no_second_weight(self):
        x = self.zero.copy(); x[[0, 48, 148, 272]] = [1, 2, 3, 4]
        hit = rank(x[None], [record('x')], self.zero, self.zero)['results'][0]
        self.assertEqual(hit['distance'], 30.)
        self.assertEqual(hit['group_distances'], dict(color=1., texture=4., shape=9., layout=16.))
        self.assertEqual(sum(hit['group_distances'].values()), hit['distance'])

    def test_top5_distance_then_lexical_ties(self):
        matrix = np.zeros((7, 400)); matrix[:, 0] = [3, 1, -1, 2, 0, 4, 5]
        names = ['c', 'b', 'a', 'd', 'z', 'e', 'f']
        result = rank(matrix, [record(n) for n in names], self.zero, self.zero)
        self.assertEqual([h['filename'] for h in result['results']], ['z', 'a', 'b', 'd', 'c'])
        self.assertEqual([h['distance'] for h in result['results']], [0, 1, 1, 4, 9])

    def test_orientation_is_per_candidate_and_tie_original(self):
        flipped = self.zero.copy(); flipped[48] = 4
        middle = self.zero.copy(); middle[48] = 2
        rows = [record('original'), record('flip'), record('middle')]
        hits = rank(np.stack([self.zero, flipped, middle]), rows, self.zero, flipped)['results']
        by_name = {h['filename']: h for h in hits}
        self.assertEqual(by_name['original']['orientation'], 'original')
        self.assertEqual(by_name['flip']['orientation'], 'flipped')
        self.assertEqual(by_name['middle']['orientation'], 'original')
        self.assertEqual(by_name['flip']['distance'], 0.)
        self.assertEqual(by_name['flip']['group_distances']['texture'], 0.)

    def test_label_changes_do_not_change_ranking(self):
        matrix = np.zeros((6, 400)); matrix[:, 0] = [3, 5, 2, 0, 1, 4]
        rows = [record(str(i), label='same') for i in range(6)]
        first = rank(matrix, rows, self.zero, self.zero)
        for i, row in enumerate(rows): row['label'] = 'unknown-breed-'+str(5-i)
        second = rank(matrix, rows, self.zero, self.zero)
        self.assertEqual([(h['filename'], h['distance']) for h in first['results']],
                         [(h['filename'], h['distance']) for h in second['results']])

    def test_duplicate_files_rank_separately_and_self_exclusion_covers_both(self):
        matrix = np.zeros((5, 400)); matrix[:, 0] = [0, 1, 3, 2, 4]
        rows = [record('self1', 'q'), record('self2', 'q'), record('dup_far', 'dup'),
                record('dup_near', 'dup'), record('other', 'other')]
        result = rank(matrix, rows, self.zero, self.zero, 'q')
        self.assertEqual(result['excluded_self_files'], 2)
        self.assertEqual(result['candidate_files'], 5)
        self.assertEqual(result['candidate_unique_contents'], 3)
        self.assertEqual([h['filename'] for h in result['results']], ['dup_near', 'dup_far', 'other'])
        self.assertIsNotNone(result['shortfall_reason'])
        self.assertEqual(rank(matrix, rows, self.zero, self.zero, 'q', False)['returned'], 5)
        historical = rank(matrix, rows, self.zero, self.zero, 'q', deduplicate=True)
        self.assertEqual([h['filename'] for h in historical['results']], ['dup_near', 'other'])

    def test_identical_sha_files_can_both_appear_in_top5(self):
        matrix = np.zeros((6, 400)); matrix[:, 0] = [0, 0, 1, 2, 3, 4]
        rows = [record('copy_b', 'same'), record('copy_a', 'same')]
        rows.extend(record(f'other_{i}') for i in range(4))
        result = rank(matrix, rows, self.zero, self.zero)
        self.assertEqual([h['filename'] for h in result['results'][:2]], ['copy_a', 'copy_b'])
        self.assertEqual(result['candidate_files'], 6)
        self.assertEqual(result['candidate_unique_contents'], 5)
        self.assertEqual(result['returned'], 5)

    def test_empty_candidates_and_invalid_vectors(self):
        self.assertEqual(rank(np.empty((0, 400)), [], self.zero, self.zero)['returned'], 0)
        for matrix in [np.zeros((2, 399)), np.full((1, 400), np.nan)]:
            with self.assertRaises(ValueError): rank(matrix, [record('a')], self.zero, self.zero)

    def test_validity_is_not_pairwise_distance_mask(self):
        x = self.zero.copy(); x[100] = 2
        row = record('a'); row['validity'][100] = False
        self.assertEqual(rank(x[None], [row], self.zero, self.zero)['results'][0]['distance'], 4.)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root/'features'; self.directory.mkdir()
        self.spec = feature_set()
        # Synthetic raw descriptors are ONLY for tests, outside the corpus.
        rng = np.random.default_rng(42)
        self.raw = rng.random((6, 400)).astype('<f4')
        self.valid = np.ones((6, 400), bool)
        self.records = []
        for i in range(6):
            image = self.root/f'{i}.png'; mask = self.root/f'{i}-mask.png'
            rgb = np.zeros((60, 90, 3), np.uint8); rgb[10:50, 20:75] = [40+i*30, 90, 140]
            m = np.zeros((60, 90), np.uint8); m[10:50, 20:75] = 255
            Image.fromarray(rgb).save(image); Image.fromarray(m).save(mask)
            self.records.append(dict(filename=image.name, source_path=image.name, mask_path=mask.name,
                source_sha256=sha256(image), mask_sha256=sha256(mask), label='label'+str(i), width=90, height=60,
                mask_pixels=int((m > 0).sum()), validation_status='success', feature_status='success', error='',
                quality=dict(note='synthetic test fixture'), source_flags={}))
        self.save_run('old', 'digest-old')
        self.save_run('current', 'digest-current')

    def save_run(self, identifier, fit_digest):
        params = b400.fit_normalizer(self.raw, self.valid, fit_digest)
        normalized = b400.transform(self.raw, self.valid, params)
        run = dict(id=identifier, input_digest=fit_digest, created_at='2026-10-22', completed_at='2026-10-22', status='complete', audit={})
        db = storage.connect(self.directory/'features.sqlite3')
        storage.save(db, self.spec, run, self.records, self.raw, normalized, self.valid, params); db.close()
        write_json(self.directory/'feature_set.json', self.spec)
        write_json(self.directory/'normalizer.json', params)
        write_json(self.directory/'summary.json', dict(run_id=identifier, feature_set_id=self.spec['id'], normalizer_id=params['id'],
                                                     vector_success=6, status='complete'))

    def index(self, identifier=None):
        return SearchIndex(self.directory, identifier, self.root)

    def sql(self, query, params=()):
        with sqlite3.connect(self.directory/'features.sqlite3') as db: db.execute(query, params)

    def test_select_current_and_explicit_old_run_scaler(self):
        current, old = self.index(), self.index('old')
        self.assertEqual(current.run['id'], 'current'); self.assertEqual(old.run['id'], 'old')
        self.assertEqual(old.normalizer['fit_digest'], 'digest-old')
        self.assertNotEqual(current.normalizer['id'], old.normalizer['id'])
        self.assertEqual(current.matrix.shape, (6, 400)); self.assertFalse(current.matrix.flags.writeable)
        self.assertEqual(current.matrix.dtype, np.dtype('<f4'))

    def test_readonly_database_and_no_feature_fit(self):
        before = sha256(self.directory/'features.sqlite3')
        with mock.patch.object(b400, 'fit_normalizer', side_effect=AssertionError('must not fit')):
            self.index()
        self.assertEqual(before, sha256(self.directory/'features.sqlite3'))

    def test_run_missing_or_incomplete(self):
        with self.assertRaisesRegex(ValueError, 'complete'): self.index('absent')
        self.sql('UPDATE runs SET status="partial" WHERE id="current"')
        with self.assertRaisesRegex(ValueError, 'complete'): self.index()

    def test_summary_ids_and_scaler_sidecar_mismatch(self):
        path = self.directory/'summary.json'; saved = json.loads(path.read_text())
        write_json(path, dict(saved, normalizer_id='wrong'))
        with self.assertRaisesRegex(ValueError, 'summary'): self.index()
        write_json(path, saved)
        path = self.directory/'normalizer.json'; value = json.loads(path.read_text()); value['scale'][0] += 1
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, 'sidecar'): self.index()

    def test_configuration_and_runtime_mismatch(self):
        spec = copy.deepcopy(self.spec); spec['descriptor']['s3']['threshold'] = 'wrong'
        write_json(self.directory/'feature_set.json', spec)
        with self.assertRaisesRegex(ValueError, 'configuration'): self.index()
        write_json(self.directory/'feature_set.json', self.spec)
        with mock.patch('tools.search.index.feature_set', return_value=spec):
            with self.assertRaisesRegex(ValueError, 'configuration'): self.index()

    def test_scaler_checksum_corruption(self):
        db = storage.connect(self.directory/'features.sqlite3', readonly=True)
        params = json.loads(db.execute('SELECT params_json FROM normalizers WHERE id=(SELECT normalizer_id FROM runs WHERE id="current")').fetchone()[0]); db.close()
        params['mean'][90] += 1
        self.sql('UPDATE normalizers SET params_json=? WHERE id=?', (json.dumps(params), params['id']))
        with self.assertRaisesRegex(ValueError, 'checksum'): self.index()

    def test_wrong_vector_scaler_detected(self):
        self.sql('UPDATE vectors SET normalizer_id=(SELECT normalizer_id FROM runs WHERE id="old") WHERE run_id="current"')
        with self.assertRaisesRegex(ValueError, 'foreign keys'): self.index()

    def test_nonfinite_vector_and_invalid_validity(self):
        blob = np.full(400, np.nan, dtype='<f4').tobytes()
        self.sql('UPDATE vectors SET normalized=? WHERE run_id="current" AND filename="0.png"', (blob,))
        with self.assertRaisesRegex(ValueError, 'Corrupt normalized'): self.index()

    def test_invalid_validity_bytes(self):
        self.sql('UPDATE vectors SET validity=? WHERE run_id="current" AND filename="0.png"', (bytes([2])*400,))
        with self.assertRaisesRegex(ValueError, 'Validity'): self.index()

    def test_missing_candidate_and_missing_vector(self):
        image = self.root/'0.png'; saved = image.read_bytes(); image.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing candidate'): self.index()
        image.write_bytes(saved)
        self.sql('DELETE FROM vectors WHERE run_id="current" AND filename="0.png"')
        with self.assertRaisesRegex(ValueError, 'missing vectors'): self.index()

    def test_changed_finite_vector_is_not_silently_accepted(self):
        self.sql('UPDATE vectors SET normalized=? WHERE run_id="current" AND filename="0.png"',
                 (np.zeros(400, dtype='<f4').tobytes(),))
        with self.assertRaisesRegex(ValueError, 'does not reproduce'): self.index()

    def test_candidate_bytes_changed_after_index_load(self):
        index = self.index()
        image = load_image(self.root/'0.png'); mask, info = load_mask(self.root/'0-mask.png', image.rgb)
        (self.root/'1.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed since B400'): retrieve(index, image, mask, info)

    def test_batch_new_unknown_group_corpus_query_and_error(self):
        index = self.index()
        image = Image.new('RGB', (90, 60), (100, 140, 80)); image.save(self.root/'new.png')
        rows = [dict(query_id='corpus', image='0.png', mask='0-mask.png', label='label0', purpose='independent'),
                dict(query_id='new', image='new.png', mask='0-mask.png', label='never-in-db', group='novel', purpose='independent'),
                dict(query_id='bad', image='missing.png', mask='', label='', purpose='independent')]
        manifest = self.root/'queries.csv'
        evaluation.write_csv(manifest, rows, ['query_id', 'image', 'mask', 'label', 'group', 'purpose'])
        folder = evaluation.run_batch(index, manifest)
        report = json.loads((folder/'evaluation.json').read_text())
        self.assertEqual(report['overall']['errors'], 1)
        self.assertEqual(report['overall']['functional_queries'], 1)
        self.assertEqual(report['queries'][1]['returned'], 5)
        self.assertEqual(report['queries'][1]['same_label_at_5'], 0.)
        self.assertIsNone(report['overall']['visual_p_at_5'])
        self.assertTrue(all(r['visual_relevant'] == '' for r in evaluation.read_csv(folder/'judgments.csv')))
        batch = json.loads((folder/'batch.json').read_text())
        self.assertEqual(batch['artifact_paths_version'], 2)
        self.assertFalse(Path(batch['queries'][0]['result_json']).is_absolute())
        for row in evaluation.read_csv(folder/'judgments.csv'):
            self.assertFalse(Path(row['result_image']).is_absolute())
        moved = folder.parent/'moved_batch'
        shutil.move(str(folder), moved)
        rescored = evaluation.score_batch(moved/'batch.json', moved/'judgments.csv', moved/'rescored', self.root)
        self.assertEqual(report['overall'], rescored['overall'])

    def test_export_rejects_recursive_overlap(self):
        source = self.root/'outputs/search/query'; source.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            export_result(dict(query_id='query', output_directory=str(source)), source/'nested', self.root)

    def test_end_to_end_two_full_extractions_artifacts_export(self):
        index = self.index(); image = load_image(self.root/'0.png')
        mask, info = load_mask(self.root/'0-mask.png', image.rgb)
        with mock.patch.object(b400, 'fit_normalizer', side_effect=AssertionError('no query fit')):
            with mock.patch.object(b400, 'extract_normalized', wraps=b400.extract_normalized) as extractor:
                result = retrieve(index, image, mask, info)
                self.assertEqual(extractor.call_count, 2)
                np.testing.assert_array_equal(extractor.call_args_list[1].args[0], image.rgb[:, ::-1])
                np.testing.assert_array_equal(extractor.call_args_list[1].args[1], mask[:, ::-1])
        self.assertEqual(result['returned'], 5); self.assertEqual(result['excluded_self_files'], 1)
        folder = Path(result['output_directory'])
        with np.load(folder/'vectors.npz', allow_pickle=False) as vectors:
            self.assertEqual(len(vectors.files), 6)
            for name in ['original', 'flipped']:
                self.assertEqual(vectors[name+'_raw'].shape, (400,))
                self.assertEqual(vectors[name+'_normalized'].dtype, np.dtype('<f4'))
            for hit in result['results']:
                self.assertAlmostEqual(sum(hit['group_distances'].values()), hit['distance'], places=12)
        for name in ['mask.png', 'overlay.png', 'top5.png', 'configuration.json', 'foreground_original.png', 'foreground_flipped.png']:
            self.assertTrue((folder/name).is_file())
        with Image.open(folder/'query_rgb.png') as preview:
            self.assertEqual(preview.size, (90, 60))
        exported = export_result(result, self.root/'outputs/search/export', self.root)
        self.assertEqual(sha256(exported/'result.json'), sha256(folder/'result.json'))

    def test_cli_query_and_invalid_image_exit(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            base = ['--feature-dir', str(self.directory), '--project-root', str(self.root)]
            self.assertEqual(cli.main(base+['query', '--image', str(self.root/'0.png'), '--mask', str(self.root/'0-mask.png')]), 0)
            self.assertEqual(cli.main(base+['query', '--image', str(self.root/'missing.jpg')]), 2)


class QueryTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rgb = np.zeros((80, 120, 3), np.uint8)
        self.rgb[:] = [20, 90, 160]; self.rgb[20:65, 30:90] = [230, 40, 20]
        self.mask = np.zeros((80, 120), np.uint8); self.mask[20:65, 30:90] = 255

    def test_query_arbitrary_size_rgb_conversion_no_stretch(self):
        path = self.root/'gray.png'; Image.fromarray(self.mask).save(path)
        image = load_image(path)
        self.assertEqual(image.rgb.shape, (80, 120, 3))
        self.assertEqual(image.sha256, sha256(path))
        canvas, _, geom = b400.prepare(image.rgb, self.mask)
        self.assertEqual(canvas.shape, (192, 288, 3))
        self.assertEqual(geom['resized'], [256, 192])

    def test_invalid_masks_nonbinary_empty_full_wrong_shape_and_mode(self):
        for i, mask in enumerate([np.zeros((80, 120), np.uint8), np.full((80, 120), 255, np.uint8),
                                  np.full((80, 120), 127, np.uint8), np.zeros((2, 2), np.uint8), self.rgb]):
            path = self.root/f'{i}.png'; Image.fromarray(mask).save(path)
            with self.assertRaises(ValueError): load_mask(path, self.rgb)

    def test_corrupt_missing_and_unsupported_image(self):
        path = self.root/'bad.jpg'; path.write_bytes(b'not an image')
        with self.assertRaises(OSError): load_image(path)
        with self.assertRaises(OSError): load_image(self.root/'missing.png')
        path = self.root/'image.gif'; Image.fromarray(self.rgb).save(path)
        with self.assertRaisesRegex(ValueError, 'JPG/PNG'): load_image(path)

    def test_grabcut_bbox_refine_hard_labels_and_original_resolution(self):
        mask, info = create_mask(self.rgb, (10, 10, 100, 65), 2)
        self.assertEqual(mask.shape, self.mask.shape); self.assertGreater(info['mask_seconds'], 0)
        strokes = np.full(mask.shape, 255, np.uint8); strokes[35:40, 50:55] = 1; strokes[5:10, 5:10] = 0
        result, seconds = refine(self.rgb, mask, strokes, 2)
        self.assertTrue((result[35:40, 50:55] == 255).all()); self.assertTrue((result[5:10, 5:10] == 0).all())
        self.assertGreater(seconds, 0)

    def test_default_grabcut_reuses_existing_tool(self):
        with mock.patch('tools.search.query.create_foreground_mask', return_value=self.mask) as existing:
            result, info = create_mask(self.rgb)
        existing.assert_called_once()
        np.testing.assert_array_equal(existing.call_args.args[0], self.rgb[:, :, ::-1])
        self.assertIn('existing', info['method'])

    def test_bad_bbox_strokes_and_output_protection(self):
        for box in [(-1, 0, 20, 20), (0, 0, 120, 80), (0, 0, 2, 900), (0, 0, 1, 1)]:
            with self.assertRaises(ValueError): create_mask(self.rgb, box)
        with self.assertRaises(ValueError): refine(self.rgb, self.mask, np.zeros((2, 2), np.uint8))
        for destination in [self.root/'data', self.root/'outputs/features/b400_v1', self.root, self.root/'outputs/segmentation']:
            with self.assertRaisesRegex(ValueError, 'outputs'): output_base(self.root, destination)
        self.assertTrue(output_base(self.root).is_dir())

    def test_output_symlink_rejected(self):
        base = output_base(self.root)
        (base/'link').symlink_to(base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlinks'): output_base(self.root, base/'link')


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queries, self.rows = [], []
        for qid, group, ratings in [('a', 'g1', [1, 1, 1, 0, 0]), ('b', 'g1', [1, 0, 0, 0, 0]), ('c', 'g2', [1, 1, 1, 1, 1])]:
            hits = [dict(rank=i+1, filename=f'{i}.jpg', sha256=str(i), label='known' if i < 2 else 'other',
                         artifact_image=f'results/{i+1}.jpg', distance=float(i), orientation='original') for i in range(5)]
            result = self.root/'queries'/qid/'result.json'; result.parent.mkdir(parents=True)
            write_json(result, dict(query_id=qid, results=hits, index=dict(run_id='r', feature_set_id='f', normalizer_id='n')))
            self.queries.append(dict(query_id=qid, group=group, query_label='known', purpose='independent',
                                     status='success', result_json=result.relative_to(self.root).as_posix(), returned=5, elapsed_seconds=2.))
            for h, rating in zip(hits, ratings):
                self.rows.append(dict(query_id=qid, purpose='independent', group=group, query_label='known',
                                      result_label=h['label'], visual_relevant=rating,
                                      result_image=f'queries/{qid}/'+h['artifact_image'], query_image=f'queries/{qid}/query_rgb.png',
                                      query_mask=f'queries/{qid}/mask.png', distance=h['distance'], orientation=h['orientation'],
                                      same_label=int(h['label']=='known'), **{k: h[k] for k in ['rank', 'filename', 'sha256']}))

    def score(self):
        batch = self.root/'batch.json'; judgments = self.root/'judgments.csv'
        write_json(batch, dict(queries=self.queries, index=dict(run_id='r', feature_set_id='f', normalizer_id='n'))); evaluation.write_csv(judgments, self.rows, evaluation.FIELDS)
        return evaluation.score_batch(batch, judgments, self.root/'outputs/search/scored', self.root)

    def test_known_p5_per_query_group_overall_separate_label_agreement(self):
        result = self.score()
        self.assertAlmostEqual(result['queries'][0]['visual_p_at_5'], .6)
        self.assertAlmostEqual(result['queries'][1]['visual_p_at_5'], .2)
        self.assertAlmostEqual(result['by_group']['g1']['visual_p_at_5'], .4)
        self.assertAlmostEqual(result['overall']['visual_p_at_5'], .6)
        self.assertAlmostEqual(result['overall']['same_label_at_5'], .4)

    def test_unjudged_blank_not_zero(self):
        for row in self.rows: row['visual_relevant'] = ''
        result = self.score()
        self.assertIsNone(result['overall']['visual_p_at_5'])
        self.assertEqual(result['overall']['fully_judged_independent_queries'], 0)

    def test_partial_judgments_and_short_top5_have_no_p5(self):
        self.rows[0]['visual_relevant'] = ''
        path = self.root/self.queries[1]['result_json']; result = json.loads(path.read_text()); result['results'].pop()
        write_json(path, result); self.rows = [r for r in self.rows if not (r['query_id'] == 'b' and r['rank'] == 5)]
        self.queries[1]['returned'] = 4
        result = self.score()
        self.assertIsNone(result['queries'][0]['visual_p_at_5']); self.assertIsNone(result['queries'][1]['visual_p_at_5'])
        self.assertEqual(result['overall']['visual_p_at_5'], 1.)

    def test_functional_checks_and_errors_excluded_from_metrics(self):
        self.queries[0]['purpose'] = 'functional_check'
        for row in self.rows:
            if row['query_id'] == 'a': row['purpose'] = 'functional_check'
        self.queries.append(dict(query_id='error', group='g2', query_label='', purpose='independent', status='failed',
                                 error='bad image', returned=0, elapsed_seconds=1., result_json=None))
        result = self.score()
        self.assertIsNone(result['queries'][0]['visual_p_at_5'])
        self.assertEqual(result['overall']['errors'], 1)
        self.assertAlmostEqual(result['overall']['visual_p_at_5'], .6)

    def test_duplicate_invalid_unknown_and_changed_identity_judgments(self):
        original = copy.deepcopy(self.rows)
        cases = [original+[original[0]], [dict(r, visual_relevant='yes') for r in original],
                 [dict(r, sha256='changed') for r in original], original[1:],
                 original+[dict(original[0], query_id='unknown')]]
        for rows in cases:
            self.rows = rows
            with self.assertRaises(ValueError): self.score()

    def test_copied_legacy_absolute_batch_maps_locally_without_old_root(self):
        self.score()
        batch = json.loads((self.root/'batch.json').read_text())
        old = Path('/nonexistent/old-clone/outputs/search/functional_checks/batch_historical')
        for query in batch['queries']:
            relative = query['result_json']
            local = self.root/relative
            result = json.loads(local.read_text())
            result['output_directory'] = str((old/relative).parent)
            write_json(local, result)
            query['result_json'] = str(old/relative)
        write_json(self.root/'batch.json', batch)
        rows = evaluation.read_csv(self.root/'judgments.csv')
        for row in rows:
            for key in ('query_image', 'query_mask', 'result_image'):
                row[key] = str(old/row[key])
        evaluation.write_csv(self.root/'judgments.csv', rows, evaluation.FIELDS)
        moved = self.root/'outputs/search/copied_legacy'
        moved.mkdir(parents=True)
        shutil.copytree(self.root/'queries', moved/'queries')
        for name in ('batch.json', 'judgments.csv'):
            shutil.copy2(self.root/name, moved/name)
        before = {p: p.read_bytes() for p in moved.rglob('*') if p.is_file()}
        report = evaluation.score_batch(moved/'batch.json', moved/'judgments.csv', moved/'scored', self.root)
        self.assertAlmostEqual(report['overall']['visual_p_at_5'], .6)
        self.assertTrue(all(p.read_bytes() == value for p, value in before.items()))
        path = moved/'queries/a/result.json'
        result = json.loads(path.read_text()); result['output_directory'] = '/wrong'
        write_json(path, result)
        with self.assertRaisesRegex(ValueError, 'original directory mismatch'):
            evaluation.score_batch(moved/'batch.json', moved/'judgments.csv', moved/'failed', self.root)

    def test_escape_missing_query_and_index_metadata_are_rejected(self):
        self.score()
        batch = json.loads((self.root/'batch.json').read_text())
        query = batch['queries'][0]
        for unsafe in ('../queries/a/result.json', '/arbitrary/outside/result.json', 'outside.json'):
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                evaluation.resolve_result(self.root/'batch.json', batch, dict(query, result_json=unsafe))
        path = self.root/query['result_json']; original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing artifact'):
            evaluation.resolve_result(self.root/'batch.json', batch, query)
        path.symlink_to(self.root/'queries/b/result.json')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            evaluation.resolve_result(self.root/'batch.json', batch, query)
        path.unlink(); path.write_bytes(original)
        for field, value in (('query_id', 'b'), ('index', dict(run_id='changed'))):
            result = json.loads(original); result[field] = value; write_json(path, result)
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                evaluation.resolve_result(self.root/'batch.json', batch, query)
        path.write_bytes(original)
        modern = dict(batch, artifact_paths_version=2)
        checked = dict(query, artifact_query_id='a', result_sha256=evaluation.digest(original))
        evaluation.resolve_result(self.root/'batch.json', modern, checked)
        with self.assertRaisesRegex(ValueError, 'binding'):
            evaluation.resolve_result(self.root/'batch.json', modern, dict(checked, artifact_query_id=None))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            evaluation.resolve_result(self.root/'batch.json', modern, dict(checked, result_sha256=None))
        result = json.loads(original); result['results'][0]['distance'] += .1; write_json(path, result)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            evaluation.resolve_result(self.root/'batch.json', modern, checked)

    def test_sheet_paths_distance_orientation_and_labels_are_immutable(self):
        original = copy.deepcopy(self.rows)
        for field in ('result_image', 'query_image', 'query_mask', 'distance', 'orientation', 'same_label'):
            self.rows = copy.deepcopy(original); self.rows[0][field] = '/outside/changed'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'metadata changed'):
                self.score()


if __name__ == '__main__':
    unittest.main()
