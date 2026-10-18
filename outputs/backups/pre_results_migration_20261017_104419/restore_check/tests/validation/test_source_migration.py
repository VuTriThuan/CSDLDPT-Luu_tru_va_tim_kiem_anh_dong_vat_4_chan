"""Source layout regression checks; processing uses generated temporary images only."""
import ast
from contextlib import redirect_stderr, redirect_stdout
import csv
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw

from tools import project_paths as paths
from tools.segmentation import edit_masks, regenerate_masks, review_overlays, run_grabcut as gc, sync_overlays
from tools.validation import audit_images, verify_grabcut_results


class SourceMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='btl_source_test_')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_default_locations_keep_current_datasets(self):
        self.assertEqual(paths.PROJECT_ROOT, PROJECT_ROOT)
        self.assertEqual(gc.DEFAULT_INPUT, PROJECT_ROOT / 'data/cropped_images_576x384')
        self.assertEqual(gc.DEFAULT_OUTPUT, PROJECT_ROOT / 'reports/yeu_cau_2/grabcut_output')
        self.assertEqual(regenerate_masks.BASE, PROJECT_ROOT / 'reports/yeu_cau_2')
        self.assertEqual(regenerate_masks.PREVIOUS, gc.DEFAULT_OUTPUT)
        args = regenerate_masks.parse_args([])
        self.assertEqual(args.source_dir, gc.DEFAULT_INPUT)
        self.assertEqual(args.queue_dir, gc.DEFAULT_OUTPUT / 'overlays/cần sửa')
        self.assertEqual(args.output_dir, regenerate_masks.BASE / 'mask_moi_can_sua')
        self.assertEqual(review_overlays.DEFAULT_FOLDER, gc.DEFAULT_OUTPUT / 'overlays')
        self.assertEqual(audit_images.DATA, gc.DEFAULT_INPUT)
        self.assertEqual(audit_images.OUT, PROJECT_ROOT / 'reports/yeu_cau_2')

    def test_all_entry_points_help_direct_and_as_modules(self):
        mapping = json.loads((PROJECT_ROOT / 'docs/source_migration_audit/source_mapping.json').read_text())
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for destination in mapping.values():
            if destination.startswith('tests/') or destination.endswith('/tool_common.py'):
                continue
            module = destination.removesuffix('.py').replace('/', '.')
            commands = [([sys.executable, '-B', str(PROJECT_ROOT / destination), '--help'], self.root),
                        ([sys.executable, '-B', '-m', module, '--help'], PROJECT_ROOT)]
            for command, cwd in commands:
                with self.subTest(script=destination, module='-m' in command):
                    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                            text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_importing_auditor_does_not_inspect_or_write_datasets(self):
        with patch.object(Path, 'iterdir', side_effect=AssertionError('Import read dataset')), \
                patch.object(Path, 'write_text', side_effect=AssertionError('Import wrote output')):
            importlib.reload(audit_images)

    def test_processing_functions_and_history_protocol_are_unchanged(self):
        audit = PROJECT_ROOT / 'docs/source_migration_audit'
        mapping = json.loads((audit / 'source_mapping.json').read_text())
        replacements = {Path(a).name: Path(b).name for a, b in mapping.items()}
        compared = 0
        with tarfile.open(audit / 'source_before.tar') as archive:
            for source, destination in mapping.items():
                if source.startswith('bo_tool_anh_576x384/tests/'):
                    continue
                old = archive.extractfile(source).read().decode()
                for before, after in replacements.items():
                    old = old.replace(before, after)
                for name in ['auto_crop.py', 'review_images.py', 'rename_images.py']:
                    for prefix in ['python ', 'python3 ']:
                        old = old.replace(prefix + name, 'python3 tools/image_processing/' + name)
                old = old.replace('Chạy review_images.py', 'Chạy tools/image_processing/review_images.py')
                for before, after in [('anh-da-cat-576x384-da-xoa', 'rejected_crops'),
                                      ('anh-da-cat-576x384', 'cropped_images_576x384'),
                                      ('anh-chua-loc', 'source_images')]:
                    old = old.replace(before, after)
                old_tree = ast.parse(old)
                new_tree = ast.parse((PROJECT_ROOT / destination).read_text())
                new_defs = {n.name: n for n in new_tree.body
                            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
                excluded = {'main'} if destination.startswith('tools/validation/') else set()
                if destination.endswith('/auto_crop.py'):
                    excluded.add('load_state')  # Covered by legacy-state relocation tests.
                if destination.endswith('/tool_common.py'):
                    excluded |= {'runtime_environment', 'setup_environment'}
                for definition in old_tree.body:
                    if not isinstance(definition, (ast.FunctionDef, ast.ClassDef)) or definition.name in excluded:
                        continue
                    if destination.endswith('/review_images.py') and definition.name == 'ReviewStore':
                        # Keep the image/undo/commit methods under the original AST guard;
                        # the new rejection-directory routing has its own behavioral test.
                        for node in [definition, new_defs[definition.name]]:
                            node.body = [method for method in node.body
                                         if not isinstance(method, ast.FunctionDef) or method.name != 'delete']
                    if destination.endswith('/rename_images.py') and definition.name == 'build_plan':
                        new_defs[definition.name].body = [statement for statement in new_defs[definition.name].body
                            if not (isinstance(statement, ast.Assign)
                                    and isinstance(statement.targets[0], ast.Subscript)
                                    and isinstance(statement.targets[0].value, ast.Name)
                                    and statement.targets[0].value.id == 'state'
                                    and isinstance(statement.targets[0].slice, ast.Constant)
                                    and statement.targets[0].slice.value in {'source', 'source_relative'})]
                    with self.subTest(script=destination, definition=definition.name):
                        self.assertEqual(ast.dump(definition), ast.dump(new_defs[definition.name]))
                    compared += 1
                if destination.endswith('/audit_images.py'):
                    start = next(i for i, n in enumerate(old_tree.body)
                                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                                 and n.targets[0].id == 'groups')

                    class LocalNames(ast.NodeTransformer):
                        def visit_Name(self, node):
                            return ast.copy_location(ast.Name(id={'DATA': 'data', 'OUT': 'output'}.get(node.id, node.id),
                                                              ctx=node.ctx), node)

                    expected = [LocalNames().visit(n) for n in old_tree.body[start:]]
                    body = new_defs['main'].body
                    start_new = next(i for i, n in enumerate(body)
                                     if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                                     and n.targets[0].id == 'groups')
                    self.assertEqual([ast.dump(n) for n in expected], [ast.dump(n) for n in body[start_new:]])
        self.assertGreater(compared, 90)

    def fixture(self):
        source = self.root / 'source'
        output = self.root / 'results'
        source.mkdir()
        image = Image.new('RGB', (576, 384), (205, 215, 225))
        ImageDraw.Draw(image).ellipse((120, 65, 450, 325), fill=(120, 55, 25))
        image.save(source / 'sample_0001.jpg')
        inventory = self.root / 'before.json'
        p = source / 'sample_0001.jpg'
        inventory.write_text(json.dumps({p.name: dict(sha256=gc.sha256(p), size=p.stat().st_size,
                                                     mtime_ns=p.stat().st_mtime_ns)}))
        args = ['--all', '--input-dir', str(source), '--output-dir', str(output), '--iterations', '1']
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(gc.main(args), 0)
        return source, output, inventory, args

    def test_grabcut_resume_and_validation_on_temporary_image(self):
        source, output, inventory, args = self.fixture()
        artifacts = list((output / 'masks').glob('*.png')) + list((output / 'overlays').glob('*.png'))
        before = {p: p.read_bytes() for p in artifacts}
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(gc.main(args + ['--resume']), 0)
            verify_grabcut_results.main(['--source-dir', str(source), '--output-dir', str(output),
                                         '--inventory', str(inventory)])
        summary = json.loads((output / 'summary.json').read_text())
        self.assertEqual(summary['attempted_this_run'], 0)
        self.assertEqual(summary['resumed_this_run'], 1)
        self.assertEqual({p: p.read_bytes() for p in artifacts}, before)
        self.assertEqual(json.loads((output / 'verification.json').read_text())['images_verified'], 1)
        row = next(csv.DictReader((output / 'manifest.csv').read_text().splitlines()))
        (output / row['mask_path']).write_bytes(b'corrupt fixture')
        self.assertFalse(gc.reusable(row, source / row['filename'], output))

    def test_edit_history_and_overlay_sync_keep_legacy_paths(self):
        source, output, _, _ = self.fixture()
        row = next(csv.DictReader((output / 'manifest.csv').read_text().splitlines()))
        pending = output / 'overlays/cần sửa'
        pending.mkdir()
        overlay = output / row['overlay_path']
        overlay.rename(pending / overlay.name)
        repository = edit_masks.MaskRepository(output, source)
        document = repository.load(repository.pending()[0])
        document.apply_result(document.mask.copy())
        accepted, history = repository.save(document)
        self.assertEqual(accepted.parent, output / 'overlays/đạt')
        self.assertEqual({p.name for p in history.iterdir()},
                         {'mask_before.png', 'overlay_before.png', 'scribbles.png', 'record.json'})
        record = json.loads((history / 'record.json').read_text())
        self.assertEqual(record['state'], 'saved')
        self.assertEqual(record['overlay_before'], f'overlays/cần sửa/{overlay.name}')
        self.assertEqual(record['overlay_after'], f'overlays/đạt/{overlay.name}')
        self.assertIn(row['filename'], sync_overlays.accepted_manual_edits(output))
        before = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
        result = sync_overlays.sync(output, source, False, False)
        self.assertEqual(result['errors'], [])
        self.assertEqual({p: p.read_bytes() for p in output.rglob('*') if p.is_file()}, before)
        session = review_overlays.ReviewSession(output / 'overlays', review_all=True)
        session.classify('s')
        session.undo()
        self.assertTrue(accepted.is_file())

    def test_auditor_writes_only_the_requested_temporary_output(self):
        source = self.root / 'source'
        output = self.root / 'audit'
        source.mkdir()
        Image.new('RGB', (576, 384), 'orange').save(source / 'test_species_0001.jpg')
        with redirect_stdout(io.StringIO()):
            audit_images.main(['--input-dir', str(source), '--output-dir', str(output)])
        result = json.loads((output / 'kiem_ke.json').read_text())
        self.assertEqual(result['image_count'], 1)
        self.assertTrue((output / 'contact_01.jpg').is_file())


if __name__ == '__main__':
    unittest.main()
