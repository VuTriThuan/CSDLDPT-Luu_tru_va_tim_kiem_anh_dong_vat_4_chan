"""Independent read-only check of actual query artifacts and protected inputs.

Never invokes requirement-3 CLI verify (which writes into B400). Never fits.
Usage: .venv/bin/python -B tests/search/verify_real_run.py
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np
from PIL import Image

from tools.features import b400
from tools.features.inputs import sha256
from tools.project_paths import PROJECT_ROOT, B400_OUTPUT_DIR
from tools.search.query import write_json


def main():
    cv2.setNumThreads(1)
    root = PROJECT_ROOT
    output = root/'outputs/search/verification'
    before = json.loads((output/'protected_before.json').read_text())
    changed = [name for name, value in before.items() if not (root/name).is_file() or sha256(root/name) != value]
    assert not changed, f'Protected files changed: {changed}'
    protected_roots = ['data', 'outputs/inventory', 'outputs/segmentation', 'outputs/features/b400_v1',
                       'docs', 'tools/features', 'tools/segmentation']
    current = {p.relative_to(root).as_posix() for directory in protected_roots for p in (root/directory).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.name != '.DS_Store'}
    authorized_additions = {'docs/reports/search_implementation.md', 'docs/reports/search_quality_audit.md'}
    unexpected_added = sorted(current-set(before)-authorized_additions)
    assert not unexpected_added, f'Unexpected protected additions: {unexpected_added}'
    db = sqlite3.connect(f'{(B400_OUTPUT_DIR/"features.sqlite3").as_uri()}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    checked = []
    folders = sorted((root/'outputs/search').rglob('result.json'))
    try:
        for path in folders:
            result = json.loads(path.read_text())
            folder = path.parent
            identity = result['index']
            params = json.loads(db.execute('SELECT params_json FROM normalizers WHERE id=?', (identity['normalizer_id'],)).fetchone()[0])
            rows = db.execute('''SELECT v.normalized,i.filename,i.path,i.sha256 FROM vectors v
                JOIN extraction_status s USING(run_id,filename) JOIN images i ON i.id=s.image_id
                WHERE v.run_id=? AND v.feature_set_id=? AND v.normalizer_id=?''',
                (identity['run_id'], identity['feature_set_id'], identity['normalizer_id'])).fetchall()
            with Image.open(folder/'query_rgb.png') as im: rgb = np.array(im)
            with Image.open(folder/'mask.png') as im: mask = np.array(im)
            b400.validate_arrays(rgb, mask)
            with np.load(folder/'vectors.npz', allow_pickle=False) as arrays:
                for name, image, m in [('original', rgb, mask), ('flipped', rgb[:, ::-1].copy(), mask[:, ::-1].copy())]:
                    raw, norm, valid, quality = b400.extract_normalized(image, m, params)
                    assert np.array_equal(raw, arrays[name+'_raw'])
                    assert np.array_equal(norm, arrays[name+'_normalized'])
                    assert np.array_equal(valid, arrays[name+'_validity'])
                    assert quality == result['query']['quality'][name]
                    canvas, _, _ = b400.prepare(image, m)
                    with Image.open(folder/f'foreground_{name}.png') as im: assert np.array_equal(canvas, np.array(im))
                q0, q1 = arrays['original_normalized'].astype(float), arrays['flipped_normalized'].astype(float)
            # Independent scalar sums and loop, with no call to search.rank.
            candidates, excluded = [], 0
            for row in rows:
                if result['policies']['self_match'].startswith('exclude') and row['sha256'] == result['query']['source_sha256']:
                    excluded += 1
                    continue
                x = np.frombuffer(row['normalized'], dtype='<f4').astype(float)
                d0 = sum(float(a-b)**2 for a, b in zip(q0, x))
                d1 = sum(float(a-b)**2 for a, b in zip(q1, x))
                candidates.append((min(d0, d1), row['filename'], row['path'], row['sha256'], 'flipped' if d1 < d0 else 'original'))
            policy = result['policies']['duplicates']
            assert policy in {'one representative per SHA-256; lowest distance then lexical tie',
                              'all eligible files ranked independently, including identical SHA-256'}
            deduplicate = policy.startswith('one representative')
            chosen, seen = [], set()
            for row in sorted(candidates):
                if deduplicate and row[3] in seen: continue
                seen.add(row[3]); chosen.append(row)
                if len(chosen) == 5: break
            assert excluded == result['excluded_self_files']
            assert len(chosen) == len(result['results'])
            for expected, hit in zip(chosen, result['results']):
                assert expected[1] == hit['filename'] and expected[3] == hit['sha256'] and expected[4] == hit['orientation']
                assert abs(expected[0]-hit['distance']) < 1e-12
                assert abs(sum(hit['group_distances'].values())-hit['distance']) < 1e-12
                assert sha256(folder/hit['artifact_image']) == hit['sha256']
            checked.append(dict(result_json=path.relative_to(root).as_posix(), returned=len(chosen), excluded_self_files=excluded,
                                frozen_extraction_exact=True, scalar_ranking_verified=True, copied_hashes_verified=True))
    finally:
        db.close()
    assert checked, 'No real queries to verify'
    report = dict(passed=True, protected_files_checked=len(before), modified_or_missing=changed,
                  unexpected_added=unexpected_added, authorized_added=sorted((current-set(before)) & authorized_additions),
                  query_artifacts_checked=len(checked), queries=checked,
                  scaler_refitted=False, requirement_1_to_3_unchanged=True,
                  protected_scope=['data/', 'outputs/inventory/', 'outputs/segmentation/', 'outputs/features/b400_v1/',
                                   'all pre-existing docs/', 'tools/features/', 'tools/segmentation/'])
    write_json(output/'delivery_checks.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
