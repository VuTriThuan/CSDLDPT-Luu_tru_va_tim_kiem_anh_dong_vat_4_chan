"""Result relocation, provenance and resume checks on isolated generated images."""
from contextlib import redirect_stderr, redirect_stdout
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import project_paths as paths
from tools.segmentation import run_grabcut as gc, sync_overlays, review_overlays, regenerate_masks
from tests.validation import test_source_migration as source_tests


class ResultsMigrationTests(unittest.TestCase):
    fixture = source_tests.SourceMigrationTests.fixture

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='btl_results_test_')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def rows(self, output):
        return list(csv.DictReader((output / 'manifest.csv').read_text().splitlines()))

    def test_resume_retains_classified_paths_and_review_decision(self):
        source, output, _, args = self.fixture()
        rows = self.rows(output)
        row = rows[0]
        old = output / row['overlay_path']
        accepted = output / 'overlays/accepted' / old.name
        accepted.parent.mkdir()
        old.rename(accepted)
        row.update(overlay_path=accepted.relative_to(output).as_posix(), review_status='da_duyet', review_result='dat')
        gc.write_csv(output / 'manifest.csv', rows)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in [accepted, output / row['mask_path']]}
        with patch.object(gc, 'create_foreground_mask', side_effect=AssertionError('Intact output reprocessed')), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(gc.main(args + ['--resume']), 0)
        self.assertEqual(self.rows(output), rows)
        self.assertFalse(old.exists())
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
        self.assertEqual(json.loads((output / 'summary.json').read_text())['resumed_this_run'], 1)

    def test_old_config_is_rejected_without_changing_historical_bytes(self):
        source, _, _, _ = self.fixture()
        legacy = self.root / 'legacy'
        legacy.mkdir()
        actual = paths.GRABCUT_OUTPUT_DIR
        if not actual.exists():
            actual = paths.REPORT_DIR / 'grabcut_output'
        for name in ['run_config.json', 'manifest.csv', '.run.lock']:
            shutil.copy2(actual / name, legacy / name)
        before = {p.name: p.read_bytes() for p in legacy.iterdir()}
        err = io.StringIO()
        with patch.object(gc, 'create_foreground_mask', side_effect=AssertionError('Legacy output reprocessed')), \
                redirect_stderr(err), redirect_stdout(io.StringIO()):
            self.assertEqual(gc.main(['--all', '--resume', '--input-dir', str(source), '--output-dir', str(legacy)]), 2)
        self.assertIn('Resume configuration/code differs', err.getvalue())
        self.assertEqual({p.name: p.read_bytes() for p in legacy.iterdir()}, before)

    def test_source_mask_overlay_hash_guards_and_unsafe_paths(self):
        source, output, _, _ = self.fixture()
        row = self.rows(output)[0]
        self.assertTrue(gc.reusable(row, source / row['filename'], output))
        for key, path in [('source_sha256', source / row['filename']),
                          ('mask_sha256', output / row['mask_path']),
                          ('overlay_sha256', output / row['overlay_path'])]:
            with self.subTest(key=key):
                original = path.read_bytes()
                path.write_bytes(b'corrupt temporary copy')
                self.assertFalse(gc.reusable(row, source / row['filename'], output))
                path.write_bytes(original)
        for relative in ['../outside.png', '/tmp/outside.png']:
            self.assertFalse(gc.reusable(dict(row, overlay_path=relative), source / row['filename'], output))
        external = self.root / 'external'
        external.mkdir()
        shutil.copy2(output / row['overlay_path'], external / 'copy.png')
        (output / 'overlays/escape').symlink_to(external, target_is_directory=True)
        self.assertFalse(gc.reusable(dict(row, overlay_path='overlays/escape/copy.png'), source / row['filename'], output))

    def test_all_english_categories_sync_and_undo(self):
        source, output, _, _ = self.fixture()
        session = review_overlays.ReviewSession(output / 'overlays')
        row = self.rows(output)[0]
        for key, category, result in [('a', 'accepted', 'dat'), ('s', 'needs_revision', 'can_sua'), ('d', 'redo', 'lam_lai')]:
            original, moved = session.classify(key)
            self.assertEqual(moved.parent.name, category)
            before = moved.read_bytes()
            report = sync_overlays.sync(output, source, apply=True)
            self.assertEqual(report['errors'], [])
            updated = self.rows(output)[0]
            self.assertEqual(updated['overlay_path'], f'overlays/{category}/{moved.name}')
            self.assertEqual(updated['review_result'], result)
            self.assertEqual(updated['overlay_sha256'], gc.sha256(moved))
            self.assertEqual(moved.read_bytes(), before)
            session.undo()
            self.assertTrue(original.exists())
            self.assertFalse(moved.exists())
        self.assertEqual({p.name for p in (output / 'overlays').iterdir() if p.is_dir()},
                         {'accepted', 'needs_revision', 'redo'})

    def test_both_edit_record_generations_preserve_hash_requirement(self):
        source, output, _, _ = self.fixture()
        row = self.rows(output)[0]
        records = output / 'manual_edits'
        for i, folder in enumerate(['đạt', 'accepted']):
            history = records / str(i)
            history.mkdir(parents=True)
            record = dict(state='saved', filename=row['filename'],
                          overlay_after=f'overlays/{folder}/{row["filename"]}.png',
                          manifest_after={'overlay_sha256': row['overlay_sha256']})
            path = history / 'record.json'
            path.write_text(json.dumps(record, ensure_ascii=False))
            before = path.read_bytes()
            self.assertIn(row['overlay_sha256'], sync_overlays.accepted_manual_edits(output)[row['filename']])
            self.assertEqual(path.read_bytes(), before)
        # A historical decision approves only the exact digest recorded at save time.
        accepted = sync_overlays.accepted_manual_edits(output)
        self.assertNotIn('0' * 64, accepted[row['filename']])

    def test_scoped_historical_reference_aliases(self):
        for before, after in paths.LEGACY_RESULT_PATHS.items():
            self.assertEqual(paths.resolve_project_reference(before, self.root), self.root / after)
        self.assertEqual(paths.resolve_project_reference('reports/yeu_cau_2/grabcut_output/overlays/cần sửa/X.jpg.png', self.root),
                         self.root / 'outputs/segmentation/grabcut/overlays/needs_revision/X.jpg.png')
        self.assertEqual(paths.resolve_project_reference('/foreign/reports/yeu_cau_2/grabcut_output/x.png', self.root),
                         Path('/foreign/reports/yeu_cau_2/grabcut_output/x.png'))
        self.assertEqual(paths.resolve_project_reference('outputs/segmentation/other/overlays/đạt/x.png', self.root),
                         self.root / 'outputs/segmentation/other/overlays/đạt/x.png')

    def test_regeneration_uses_separate_output_and_can_resume(self):
        source, previous, _, _ = self.fixture()
        queue = previous / 'overlays/needs_revision'
        queue.mkdir()
        old = previous / self.rows(previous)[0]['overlay_path']
        old.rename(queue / old.name)
        output = self.root / 'mask_regeneration'
        protected = {p: p.read_bytes() for base in [source, previous] for p in base.rglob('*') if p.is_file()}
        args = regenerate_masks.parse_args(['--source-dir', str(source), '--previous-dir', str(previous),
                                           '--queue-dir', str(queue), '--output-dir', str(output), '--limit', '1'])
        # One generated image, actual cached U2Net inference; no download or real-data writes.
        self.assertTrue(args.model.is_file(), 'Expected the previously verified cached model')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(regenerate_masks.run(args), 0)
        row = self.rows(output)[0]
        self.assertTrue(row['overlay_path'].startswith('overlays/needs_revision/'))
        self.assertTrue(regenerate_masks.reusable(row, output))
        before = {p: p.read_bytes() for p in [output / row['mask_path'], output / row['overlay_path']]}
        args.resume = True
        with patch.object(regenerate_masks, 'predict_mask', side_effect=AssertionError('Intact mask reprocessed')), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(regenerate_masks.run(args), 0)
        self.assertEqual(json.loads((output / 'summary.json').read_text())['reused_this_run'], 1)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual({p: p.read_bytes() for p in protected}, protected)


if __name__ == '__main__':
    unittest.main()
