"""Read-only single-group and leave-one-group-out analysis of saved B400 vectors.

Run: .venv/bin/python -B -m tools.search.group_analysis
No extraction, fitting, renormalization, or additional group weights.
"""
from datetime import datetime, timezone
from pathlib import Path
import uuid

import numpy as np
from PIL import Image, ImageDraw

from tools.features import b400
from tools.features.inputs import safe_path
from tools.project_paths import PROJECT_ROOT
from tools.search.diagnostics import _vectors, _json_equal
from tools.search.index import SearchIndex, read_json
from tools.search.mask_quality import analyze_mask
from tools.search.policies import search_options
from tools.search.query import digest, output_base, write_json
from tools.search.evaluation import write_csv
from tools.search.replay import replay_ranking


CONFIGURATIONS = {'full': [(0, 400)]}
CONFIGURATIONS.update({f'only_{name}': [(start, stop)] for name, start, stop in b400.GROUPS})
CONFIGURATIONS.update({f'without_{name}': [(s, e) for other, s, e in b400.GROUPS if other != name]
                       for name, _, _ in b400.GROUPS})


def projected_ranking(matrix, records, original, flipped, ranges, query_hash, exclude_self, deduplicate):
    """Return the complete eligible order for a fixed coordinate subset.

    D_S = min(sum_S((q_original-x)^2), sum_S((q_flipped-x)^2)).
    Orientation is chosen again for EACH subset and candidate; never sum the
    per-group orientation minima. Original wins exact orientation ties.
    """
    coordinates = [i for start, stop in ranges for i in range(start, stop)]
    if not coordinates or len(set(coordinates)) != len(coordinates) or min(coordinates) < 0 or max(coordinates) >= 400:
        raise ValueError('Expected nonempty disjoint B400 ranges')
    x = np.asarray(matrix, dtype=np.float64)[:, coordinates]
    a, b = [np.asarray(q, dtype=np.float64)[coordinates] for q in (original, flipped)]
    if len(x) != len(records) or not all(np.isfinite(v).all() for v in (x, a, b)):
        raise ValueError('Invalid analysis vectors')
    d0, d1 = [np.square(x-q).sum(axis=1, dtype=np.float64) for q in (a, b)]
    distances = np.minimum(d0, d1)
    order = sorted((i for i, r in enumerate(records) if not (exclude_self and r['sha256'] == query_hash)),
                   key=lambda i: (distances[i], records[i]['filename'], records[i]['path'], records[i]['sha256']))
    seen, hits = set(), []
    for i in order:
        r = records[i]
        if deduplicate and r['sha256'] in seen:
            continue
        seen.add(r['sha256'])
        hits.append(dict(rank=len(hits)+1, candidate_row=i, filename=r['filename'], path=r['path'], sha256=r['sha256'],
                         distance=float(distances[i]), orientation='flipped' if d1[i] < d0[i] else 'original',
                         original_distance=float(d0[i]), flipped_distance=float(d1[i])))
    return hits


def select_queries(base):
    """Earliest saved query ID for each prespecified source-name family.

    Inspect only direct child queries, avoiding exports/duplicates of runs.
    Include ngua_ (Vietnamese horse input), Equus_caballus, Bos_taurus and
    Canis_familiaris. Selection uses no distance, rank, or mask-quality score.
    """
    eligible = dict(horse=[], cow=[], dog=[])
    for path in sorted(Path(base).glob('*/result.json')):
        result = read_json(path)
        name = Path(result['query']['source_path']).name.lower()
        group = ('horse' if name.startswith(('ngua_', 'equus_caballus_')) else
                 'cow' if name.startswith('bos_taurus_') else
                 'dog' if name.startswith('canis_familiaris_') else None)
        if group is not None:
            # Missing artifacts are errors, never an excuse to skip a bad case.
            for filename in ('vectors.npz', 'mask.png', 'query_rgb.png', 'configuration.json'):
                if not (path.parent/filename).is_file():
                    raise ValueError(f'Missing selected-family artifact: {path.parent/filename}')
            eligible[group].append(path)
    if any(not paths for paths in eligible.values()):
        raise ValueError('Need saved horse, cow and dog queries')
    return eligible, {group: paths[0] for group, paths in eligible.items()}


def _sheet(index, directory, experiments, target):
    width, height = 224, 180
    sheet = Image.new('RGB', (5*width, height*(len(experiments)+1)), 'white')
    draw = ImageDraw.Draw(sheet)
    def tile(path, x, y, title, subtitle=''):
        with Image.open(path) as image:
            thumb = image.convert('RGB'); thumb.thumbnail((220, 140))
            sheet.paste(thumb, (x+(width-thumb.width)//2, y+20))
        draw.text((x+2, y+2), title, fill='black')
        draw.text((x+2, y+160), subtitle, fill='black')
    for i, name in enumerate(('query_rgb.png', 'overlay.png', 'mask.png')):
        tile(directory/name, i*width, 0, name)
    for row, (name, experiment) in enumerate(experiments.items(), 1):
        for column, hit in enumerate(experiment['top5']):
            tile(safe_path(index.root, hit['path']), column*width, row*height,
                 f'{name} #{hit["rank"]}', f'{hit["filename"][:24]} D={hit["distance"]:.4f}')
    sheet.save(target)


def main():
    index = SearchIndex()
    base = PROJECT_ROOT/'outputs/search'
    eligible, selected = select_queries(base)
    parent = output_base(PROJECT_ROOT, base/'diagnostics/group_analysis')
    folder = parent/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+uuid.uuid4().hex[:6])
    folder.mkdir(exist_ok=False)
    report = dict(index=index.describe(),
        selection_rule='Earliest directory query_id in each source family; direct children of outputs/search; no ranking/mask filtering.',
        source_families=dict(horse=['ngua_', 'equus_caballus_'], cow=['bos_taurus_'], dog=['canis_familiaris_']),
        eligible={group: [p.parent.name for p in paths] for group, paths in eligible.items()},
        distance='D_S=min(sum over S (q_original-x)^2, sum over S (q_flipped-x)^2), float64 on saved normalized float32; no extra weights or renormalization.',
        comparison='Rank delta = subset rank minus full rank (negative rises). Distances across coordinate subsets have different scales; distance delta is arithmetic only, never probability or relevance.',
        candidate_rule='Track union of top5 over all 9 configurations; this is a review pool, not automatic relevance.',
        configurations=CONFIGURATIONS, queries=[])
    top_rows, candidate_rows = [], []
    for group, path in selected.items():
        directory = path.parent
        saved = read_json(path)
        arrays = _vectors(directory)
        configuration = read_json(directory/'configuration.json')
        for key, expected in (('feature_set', index.spec), ('normalizer', index.normalizer), ('selected_run', index.run)):
            if not _json_equal(configuration.get(key), expected):
                raise ValueError(f'Saved configuration mismatch: {directory}, {key}')
        original, flipped = [arrays[n]['normalized'] for n in ('original', 'flipped')]
        replay = replay_ranking(index, saved, original, flipped)
        if not replay['ranking_reproduces_exactly']:
            raise ValueError(f'Selected baseline cannot be reproduced: {path}: {replay["reasons"]}')
        for n in ('original', 'flipped'):
            if not np.array_equal(b400.transform(arrays[n]['raw'], arrays[n]['validity'], index.normalizer), arrays[n]['normalized']):
                raise ValueError(f'Saved vector/scaler mismatch: {path}, {n}')
        options = search_options(saved)
        rankings = {name: projected_ranking(index.matrix, index.records, original, flipped, ranges,
                    saved['query']['source_sha256'], **options) for name, ranges in CONFIGURATIONS.items()}
        full = {h['filename']: h for h in rankings['full']}
        for actual, stored in zip(rankings['full'][:5], saved['results']):
            if (actual['filename'] != stored['filename'] or actual['orientation'] != stored['orientation']
                    or not np.isclose(actual['distance'], stored['distance'], rtol=1e-12, atol=1e-14)):
                raise ValueError(f'Analysis full ranking differs from saved baseline: {directory}')
        tracked = sorted({h['filename'] for hits in rankings.values() for h in hits[:5]})
        experiments = {}
        for name, hits in rankings.items():
            by_name = {h['filename']: h for h in hits}
            anchors = []
            for filename in tracked:
                h, baseline = by_name[filename], full[filename]
                row = dict(query_id=saved['query_id'], family=group, configuration=name, **h,
                           full_rank=baseline['rank'], rank_delta=h['rank']-baseline['rank'],
                           full_distance=baseline['distance'], distance_delta=h['distance']-baseline['distance'],
                           visual_relevant='', notes='')
                anchors.append(row); candidate_rows.append(row)
            top5 = [next(r for r in anchors if r['filename'] == h['filename']) for h in hits[:5]]
            top_rows.extend(top5)
            common = len({h['filename'] for h in hits[:5]} & {h['filename'] for h in rankings['full'][:5]})
            experiments[name] = dict(top5=top5, tracked_candidates=anchors, top5_overlap_full=common,
                top5_positions_changed=sum(a['filename'] != b['filename'] for a, b in zip(hits[:5], rankings['full'][:5])),
                eligible_candidates=len(hits))
        with Image.open(directory/'mask.png') as image:
            mask = np.array(image.convert('L'))
        with Image.open(directory/'query_rgb.png') as image:
            rgb = np.array(image.convert('RGB'))
        if (digest(rgb.tobytes()) != saved['query']['rgb_pixels_sha256']
                or digest(mask.tobytes()) != saved['query']['mask_pixels_sha256']):
            raise ValueError(f'Saved pixel checksum mismatch: {directory}')
        if digest((directory/'mask.png').read_bytes()) != saved['query']['saved_mask_sha256']:
            raise ValueError(f'Saved mask checksum mismatch: {directory}')
        reference = []
        for record in index.records:
            if record['sha256'] == saved['query']['source_sha256']:
                mask_path = safe_path(index.root, record['mask_path'])
                if digest(mask_path.read_bytes()) != record['mask_sha256']:
                    raise ValueError('Corpus mask checksum mismatch')
                with Image.open(mask_path) as image:
                    approved = np.array(image.convert('L')) > 0
                used = mask > 0
                reference.append(dict(filename=record['filename'], iou=float((used & approved).sum()/(used | approved).sum()),
                                      identical=bool(np.array_equal(used, approved)), review_status=record['review_status']))
        item = dict(family=group, query_id=saved['query_id'], source_filename=Path(saved['query']['source_path']).name,
                    query_directory=directory.relative_to(PROJECT_ROOT).as_posix(), policies=saved['policies'],
                    artifacts_sha256={n: digest((directory/n).read_bytes()) for n in
                        ('result.json', 'configuration.json', 'vectors.npz', 'mask.png', 'query_rgb.png')},
                    mask_method=saved['query']['mask'], mask_diagnostics=analyze_mask(mask, saved['query']['mask'].get('initial_bbox')),
                    reference_mask_comparisons=reference,
                    reference_note='IoU is agreement with corpus mask, not segmentation accuracy. Empty means no exact source hash in corpus.',
                    experiments=experiments, contact_sheet=group+'.png')
        report['queries'].append(item)
        _sheet(index, directory, experiments, folder/(group+'.png'))
    write_json(folder/'analysis.json', report)
    fields = list(candidate_rows[0])
    write_csv(folder/'top5.csv', top_rows, fields)
    write_csv(folder/'candidate_ranks.csv', candidate_rows, fields)
    print(folder.relative_to(PROJECT_ROOT))


if __name__ == '__main__':
    main()
