"""Emit installed runtime metadata and verify imports without creating a GUI."""
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sys

modules = {}
for name in ['numpy', 'PIL', 'cv2', 'onnxruntime', 'certifi', 'tkinter', 'ssl', 'venv', 'fcntl']:
    try:
        module = importlib.import_module(name)
        modules[name] = dict(imported=True, file=getattr(module, '__file__', None),
                             version=str(getattr(module, '__version__', getattr(module, 'TkVersion', 'stdlib'))))
    except ImportError as exc:
        modules[name] = dict(imported=False, error=str(exc))

print(json.dumps(dict(python=platform.python_version(), python_build=sys.version,
      executable=sys.executable, resolved_executable=str(Path(sys.executable).resolve()),
      prefix=sys.prefix, base_prefix=sys.base_prefix, platform=platform.platform(),
      packages={d.metadata['Name']: dict(version=d.version, requires=d.requires)
                for d in metadata.distributions()}, imports=modules), ensure_ascii=False, indent=2))
