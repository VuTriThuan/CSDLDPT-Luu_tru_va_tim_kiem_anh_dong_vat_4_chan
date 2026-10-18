"""Import and --help each active tool with its documented interpreter."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
TOOLS = {
    'tools.image_processing.auto_crop': '.venv-image-tools',
    'tools.image_processing.rename_images': '.venv',
    'tools.image_processing.review_images': '.venv-image-tools',
    'tools.segmentation.run_grabcut': '.venv',
    'tools.segmentation.review_overlays': '.venv',
    'tools.segmentation.edit_masks': '.venv',
    'tools.segmentation.sync_overlays': '.venv',
    'tools.segmentation.regenerate_masks': '.venv-image-tools',
    'tools.validation.audit_images': '.venv',
    'tools.validation.verify_grabcut_results': '.venv',
    'tools.validation.verify_regenerated_masks': '.venv',
}


def main():
    results = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
    with tempfile.TemporaryDirectory(prefix='btl_environment_smoke_') as tmp:
        for module, environment in TOOLS.items():
            python = ROOT / environment / 'bin/python'
            imported = subprocess.run([str(python), '-B', '-c',
                'import sys,importlib,json;sys.path.insert(0,sys.argv[1]);'
                'm=importlib.import_module(sys.argv[2]);'
                'print(json.dumps(dict(prefix=sys.prefix,module=m.__file__)))', str(ROOT), module],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=60)
            assert imported.returncode == 0, (module, imported.stderr)
            metadata = json.loads(imported.stdout)
            assert Path(metadata['prefix']) == ROOT / environment
            path = ROOT / (module.replace('.', '/') + '.py')
            checks = []
            for command, cwd in [([str(python), '-B', str(path), '--help'], tmp),
                                 ([str(python), '-B', '-m', module, '--help'], str(ROOT))]:
                result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
                assert result.returncode == 0 and 'usage:' in result.stdout, (command, result.stderr)
                checks.append(dict(command=command, cwd=cwd, exit_code=result.returncode))
            results.append(dict(module=module, environment=environment, imported=metadata, help_checks=checks))
        # The two launchers must use the new environment even when started via shared Python.
        bootstrap = []
        for name in ['auto_crop', 'review_images']:
            command = [str(ROOT / '.venv/bin/python'), '-B', str(ROOT / f'tools/image_processing/{name}.py'), '--help']
            result = subprocess.run(command, cwd=tmp, env=env, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0 and 'usage:' in result.stdout, result.stderr
            bootstrap.append(dict(command=command, exit_code=result.returncode))
        assert list(Path(tmp).iterdir()) == [], 'Help/import created files in current directory'
    (AUDIT / 'smoke_checks.json').write_text(json.dumps(dict(verified=True, tools=results,
        tool_imports=len(results), direct_and_module_help_checks=2*len(results),
        shared_interpreter_bootstrap_checks=bootstrap), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(verified=True, tool_imports=len(results), help_checks=2*len(results), bootstrap_checks=2)))


if __name__ == '__main__':
    main()
