"""Check active local Markdown links and linked images without modifying targets.

Run from any cwd with: .venv/bin/python -B docs/documentation_migration_audit/check_links.py
HTTP links and bare historical path mentions are listed separately, not fetched.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shlex
import urllib.parse

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)')


def main():
    files = [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md')),
             *sorted((ROOT / 'docs/reports').glob('*.md')),
             *sorted((ROOT / 'docs/guides').glob('*.md'))]
    rows, errors, external, images, commands = [], [], [], {}, []
    counts = Counter()
    for document in files:
        text = document.read_text()
        for match in LINK.finditer(text):
            raw = match[1].strip('<>')
            url = urllib.parse.urlsplit(raw)
            line = text.count('\n', 0, match.start()) + 1
            if url.scheme in ['http', 'https', 'mailto']:
                external.append(dict(document=str(document.relative_to(ROOT)), line=line,
                                     destination=raw, status='unchanged_not_fetched'))
                continue
            destination = urllib.parse.unquote(url.path)
            target = ((document.parent / destination).resolve() if destination
                      else document.resolve())
            category = ('image' if target.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] else
                        'code' if target.suffix == '.py' else
                        'directory' if target.is_dir() else 'document_or_artifact')
            row = dict(document=str(document.relative_to(ROOT)), line=line, destination=raw,
                       target=str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target),
                       category=category, exists=target.exists())
            if not target.exists():
                errors.append(row)
            elif not target.is_relative_to(ROOT):
                errors.append(dict(row, error='active local link escapes project'))
            elif category == 'image' and str(target) not in images:
                try:
                    with Image.open(target) as image:
                        image.load()
                        images[str(target)] = dict(path=str(target.relative_to(ROOT)),
                                                  format=image.format, size=image.size,
                                                  sha256=hashlib.sha256(target.read_bytes()).hexdigest())
                except Exception as exc:
                    errors.append(dict(row, error=str(exc)))
            if url.fragment and url.scheme == '' and target.is_file() and target.suffix == '.md':
                # No local fragments occur in the active files in this stage.
                errors.append(dict(row, error='fragment needs explicit validation'))
            counts[category] += 1
            rows.append(row)
        # Commands stay relative to BTL, independently of the document location.
        for number, line in enumerate(text.splitlines(), 1):
            if not re.match(r'^(?:python(?:3)?|py|(?:\.venv|bo_tool_anh_576x384)/[^\s]*python)\s', line):
                continue
            try:
                tokens = shlex.split(line)
            except ValueError:
                continue
            for token in tokens[1:]:
                if token.endswith('.py'):
                    row = dict(document=str(document.relative_to(ROOT)), line=number,
                               script=token, exists=(ROOT / token).is_file())
                    if not row['exists']:
                        errors.append(dict(row, error='command script missing from project root'))
                    commands.append(row)
    result = dict(verified=not errors, documents_checked=len(files),
                  local_links_checked=len(rows), categories=dict(counts),
                  unique_images_decoded=len(images), command_script_references_checked=len(commands),
                  external_http_links_not_fetched=len(external), errors=errors)
    (AUDIT / 'local_links.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (AUDIT / 'linked_images.json').write_text(json.dumps(list(images.values()), indent=2) + '\n')
    (AUDIT / 'command_references.json').write_text(json.dumps(commands, indent=2) + '\n')
    (AUDIT / 'external_links.json').write_text(json.dumps(external, indent=2) + '\n')
    (AUDIT / 'link_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['verified'] else 1)


if __name__ == '__main__':
    main()
