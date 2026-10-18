"""Read existing pip cache; retain compatible, byte-identical wheels for pinned versions."""
import hashlib
import io
import itertools
import json
from pathlib import Path
import shutil
import sys
import zipfile
from email.parser import BytesParser

from pip._vendor import msgpack
from pip._vendor.packaging.tags import sys_tags, parse_tag

AUDIT = Path(__file__).resolve().parent
STAGING = Path('/private/tmp/btl_environment_wheels_20261017')
STAGING.mkdir(exist_ok=True)
CACHE = Path.home() / 'Library/Caches/pip'


def normalize(name):
    return name.lower().replace('_', '-').replace('.', '-')


wanted = set()
for name in ['root_before.json', 'image_tools_before.json']:
    for package, data in json.loads((AUDIT / name).read_text())['packages'].items():
        if package.lower() not in {'pip', 'setuptools'}:
            wanted.add((normalize(package), data['version']))
compatible = set(sys_tags())
found = {}
for path in itertools.chain(CACHE.rglob('*'), Path('/private/tmp/pip-cache').rglob('*')):
    if not path.is_file() or path.stat().st_size > 200 * 1024**2:
        continue
    with path.open('rb') as stream:
        prefix = stream.read(8)
    try:
        raw = None
        if prefix.startswith(b'PK\x03\x04'):
            archive = zipfile.ZipFile(path)
        elif prefix.startswith(b'cc=') and b',' in prefix:
            packed = path.read_bytes().split(b',', 1)[1]
            value = msgpack.unpackb(packed, raw=False)
            raw = value.get('response', {}).get('body')
            if not raw or not raw.startswith(b'PK\x03\x04'):
                continue
            archive = zipfile.ZipFile(io.BytesIO(raw))
        else:
            continue
        with archive:
            metadata = next((n for n in archive.namelist() if n.endswith('.dist-info/METADATA')), None)
            if metadata is None:
                continue
            info = BytesParser().parsebytes(archive.read(metadata))
            key = (normalize(info['Name']), info['Version'])
            if key not in wanted or key in found:
                continue
            wheel = BytesParser().parsebytes(archive.read(metadata.removesuffix('METADATA') + 'WHEEL'))
            tag = next((tag for value in wheel.get_all('Tag', []) for tag in parse_tag(value) if tag in compatible), None)
            if tag is None:
                continue
            # Filename reconstructed from the wheel's own package/version/tag;
            # archive bytes and RECORD stay untouched.
            filename = info['Name'].replace('-', '_') + '-' + info['Version'] + '-' + str(tag) + '.whl'
            target = STAGING / filename
            if raw is None:
                shutil.copyfile(path, target)
            else:
                target.write_bytes(raw)
            found[key] = dict(package=key[0], version=key[1], wheel=filename,
                              cached_at=str(path), sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                              bytes=target.stat().st_size)
    except (zipfile.BadZipFile, ValueError, TypeError, msgpack.exceptions.UnpackException):
        continue
result = dict(staging=str(STAGING), wheels=list(found.values()),
              missing=[dict(package=n, version=v) for n,v in sorted(wanted - set(found))])
(AUDIT / 'cached_wheels.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
