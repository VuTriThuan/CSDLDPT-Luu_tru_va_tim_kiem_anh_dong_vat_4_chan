import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest


RESTORE = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'outputs/backups/restore_large_files.py'))['restore']


class BackupPartsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.original = b'first-part\x00' + b'second-part\xff'
        parts = []
        for index, data in enumerate([self.original[:11], self.original[11:]]):
            path = self.root / f'part-{index}'
            path.write_bytes(data)
            parts.append({'path': path.name, 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        self.entry = {'path': 'snapshot.tar', 'size_bytes': len(self.original), 'sha256': hashlib.sha256(self.original).hexdigest(), 'parts': parts}
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'parts-manifest.json').write_text(json.dumps({'version': 1, 'files': [self.entry]}))

    def restore(self, verify_only=False):
        with contextlib.redirect_stdout(io.StringIO()):
            RESTORE(self.root, verify_only)

    def test_reconstructs_exact_bytes_and_can_run_again(self):
        self.restore()
        self.assertEqual((self.root / 'snapshot.tar').read_bytes(), self.original)
        self.restore()
        self.assertEqual((self.root / 'snapshot.tar').read_bytes(), self.original)
        self.assertFalse(list(self.root.glob('*.restoring-*')))

    def test_verify_only_checks_parts_without_creating_original(self):
        self.restore(verify_only=True)
        self.assertFalse((self.root / 'snapshot.tar').exists())

    def test_corrupt_part_is_rejected_without_leaving_partial_output(self):
        (self.root / 'part-0').write_bytes(b'x' * 11)
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.restore()
        self.assertFalse((self.root / 'snapshot.tar').exists())
        self.assertFalse(list(self.root.glob('*.restoring-*')))

    def test_existing_different_file_is_not_overwritten(self):
        target = self.root / 'snapshot.tar'
        target.write_bytes(b'existing content')
        with self.assertRaisesRegex(ValueError, 'Existing file differs'):
            self.restore()
        self.assertEqual(target.read_bytes(), b'existing content')

    def test_combined_hash_mismatch_is_rejected(self):
        self.entry['sha256'] = '0' * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Combined file mismatch'):
            self.restore()
        self.assertFalse((self.root / 'snapshot.tar').exists())

    def test_paths_outside_backup_directory_are_rejected(self):
        self.entry['path'] = '../outside-backup-parts-test.tar'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Path outside backup directory'):
            self.restore()


if __name__ == '__main__':
    unittest.main()
