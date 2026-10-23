"""Read-only retrieval audit. Write evidence only beside this script."""
import json
from datetime import datetime, timezone
import uuid
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.features import b400
from tools.search.index import SearchIndex
from tools.search.replay import replay_ranking


def parts(a, b, groups=b400.GROUPS):
    return {n: float(np.square(a[s:e].astype(float)-b[s:e]).sum())
            for n, s, e in groups}


def mask_iou(a, b):
    return float(np.count_nonzero((a > 0) & (b > 0)) /
                 np.count_nonzero((a > 0) | (b > 0)))


def main():
    idx = SearchIndex()
    output = dict(index=idx.describe(),
                  purpose='Numerical ranking, mask sensitivity and descriptor audit; no relevance or accuracy claims.',
                  unchanged='B400 code, frozen scaler, SQLite and requirement 1-3 files are read only.',
                  group_norm_ranges={n: [float(np.linalg.norm(idx.matrix[:, s:e], axis=1).min()),
                                         float(np.linalg.norm(idx.matrix[:, s:e], axis=1).max())]
                                     for n, s, e in b400.GROUPS},
                  valid_dimensions_ranges={n: [min(sum(r['validity'][s:e]) for r in idx.records),
                                               max(sum(r['validity'][s:e]) for r in idx.records)]
                                           for n, s, e in b400.BLOCKS},
                  queries=[], perturbations=[])
    # Snapshot the input list before writing; exports count as separate artifacts.
    for path in sorted((ROOT/'outputs/search').rglob('result.json')):
        result = json.loads(path.read_text())
        saved = np.load(path.parent/'vectors.npz')
        q = result['query']
        try:
            replay = replay_ranking(idx, result, saved['original_normalized'], saved['flipped_normalized'])
        except (ValueError, KeyError) as exc:
            replay = dict(ranking_reproduces_exactly=False, reasons=[dict(error=f'{type(exc).__name__}: {exc}')])
        top = result['results'][0]
        candidate_index = next(i for i, r in enumerate(idx.records) if r['filename'] == top['filename'])
        original = saved['original_normalized']
        selected = saved[top['orientation']+'_normalized']
        same = [i for i, r in enumerate(idx.records) if r['sha256'] == q['source_sha256']]
        item = dict(query_id=result['query_id'], source_path=q['source_path'],
                    result_json=path.relative_to(ROOT).as_posix(),
                    **replay,
                    frozen_transform_reproduces_saved_vectors={
                        n: bool(np.array_equal(b400.transform(saved[n+'_raw'], saved[n+'_validity'], idx.normalizer),
                                             saved[n+'_normalized'])) for n in ['original', 'flipped']},
                    mask_statistics=q['mask_statistics'],
                    top1=dict(filename=top['filename'], distance=top['distance'], orientation=top['orientation'],
                              groups=top['group_distances'], blocks=parts(selected, idx.matrix[candidate_index], b400.BLOCKS)),
                    distances_to_same_source=[],
                    original_query_candidate_group_distance_quantiles={
                        n: np.quantile(np.square(idx.matrix[:, s:e].astype(float)-original[s:e]).sum(axis=1),
                                       [0, .25, .5, .75, 1]).tolist() for n, s, e in b400.GROUPS})
        current_mask = np.asarray(Image.open(path.parent/'mask.png').convert('L'))
        for i in same:
            corpus_mask = np.asarray(Image.open(ROOT/idx.records[i]['mask_path']).convert('L'))
            drift = parts(original, idx.matrix[i])
            item['distances_to_same_source'].append(dict(
                filename=idx.records[i]['filename'], mask_iou=mask_iou(current_mask, corpus_mask),
                normalized_vector_squared_distance=sum(drift.values()), group_drift=drift))
        output['queries'].append(item)

    for query_id in ['20261023T014542_632499Z_e8f7fc8d', '20261023T014716_706322Z_da9a4488',
                     '20261023T014901_329947Z_fdf91295', '20261023T014953_653022Z_e870cbcc']:
        path = ROOT/'outputs/search'/query_id
        saved = np.load(path/'vectors.npz')
        rgb = np.asarray(Image.open(path/'query_rgb.png').convert('RGB'))
        mask = np.asarray(Image.open(path/'mask.png').convert('L'))
        raw, normalized, _, _ = b400.extract_normalized(rgb, mask, idx.normalizer)
        item = dict(query_id=query_id, extraction_reproduces_saved_vector=bool(
            np.array_equal(normalized, saved['original_normalized'])), measurements=[])
        for name, function in [('erode1', cv2.erode), ('dilate1', cv2.dilate)]:
            altered = function(mask, np.ones((3, 3), np.uint8))
            r, n, _, _ = b400.extract_normalized(rgb, altered, idx.normalizer)
            drift = parts(n, normalized)
            item['measurements'].append(dict(operation=name, changed_pixels=int(np.count_nonzero(mask != altered)),
                mask_iou=mask_iou(mask, altered), normalized_vector_squared_distance=sum(drift.values()),
                group_drift=drift, block_drift=parts(n, normalized, b400.BLOCKS),
                s3_bits_changed=int(np.count_nonzero(r[160:208] != raw[160:208])),
                s2e_before=float(raw[159]), s2e_after=float(r[159])))
        output['perturbations'].append(item)
    output['summary'] = dict(checked=len(output['queries']),
        matched=sum(q['ranking_reproduces_exactly'] for q in output['queries']),
        mismatched=sum(not q['ranking_reproduces_exactly'] for q in output['queries']),
        scope='All result.json files under outputs/search, including separate exported/copied artifacts')
    target = Path(__file__).with_name('evidence_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+uuid.uuid4().hex[:6]+'.json')
    target.write_text(json.dumps(output, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(dict(output=str(target), **output['summary'],
                          sensitivity_cases=len(output['perturbations']))))
    return int(output['summary']['mismatched'] > 0)


if __name__ == '__main__':
    sys.exit(main())
