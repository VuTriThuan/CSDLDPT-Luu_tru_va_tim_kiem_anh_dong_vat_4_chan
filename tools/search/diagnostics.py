"""Read-only diagnostics for one saved B400 search, using its frozen scaler.

Mask IoU here measures agreement with the previously approved corpus mask. It
is not segmentation accuracy, and this tool does not infer visual relevance.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import numpy as np
from PIL import Image

from tools.features import b400
from tools.features.inputs import safe_path
from tools.search.query import digest, load_image, load_mask, output_base, write_json


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _json_equal(first, second):
    # A freshly constructed test/index configuration may use tuples where
    # the persisted JSON has arrays; these carry the same configuration.
    return json.loads(json.dumps(first)) == json.loads(json.dumps(second))


def _vectors(directory):
    result = {}
    with np.load(safe_path(directory, 'vectors.npz'), allow_pickle=False) as archive:
        for variant in ('original', 'flipped'):
            result[variant] = {}
            for name in ('raw', 'normalized', 'validity'):
                values = archive[f'{variant}_{name}']
                if values.shape != (400,) or not np.isfinite(values).all():
                    raise ValueError(f'Invalid saved {variant} {name}: expected 400 finite values')
                if name == 'validity':
                    if not np.isin(values, [0, 1]).all():
                        raise ValueError('Saved validity must contain only 0/1')
                    values = values.astype(bool)
                result[variant][name] = values.copy()
    return result


def _exclude_self(result):
    policy = result.get('policies', {}).get('self_match')
    if policy == 'exclude all identical input-byte SHA-256':
        return True
    if policy == 'include self matches':
        return False
    raise ValueError('Saved query has an unknown self-match policy')


def _deduplicate(result):
    policy = result.get('policies', {}).get('duplicates')
    if policy == 'one representative per SHA-256; lowest distance then lexical tie':
        return True
    if policy == 'all eligible files ranked independently, including identical SHA-256':
        return False
    raise ValueError('Saved query has an unknown duplicate policy')


def _brief(hit):
    return {name: hit[name] for name in
            ('rank', 'filename', 'path', 'sha256', 'distance', 'orientation',
             'original_distance', 'flipped_distance')}


def _decompose(query_vector, candidate, query_validity=None, candidate_validity=None):
    squared = np.square(np.asarray(query_vector, dtype=np.float64)-np.asarray(candidate, dtype=np.float64))
    total = float(squared.sum(dtype=np.float64))
    groups = {name: float(squared[start:stop].sum(dtype=np.float64)) for name, start, stop in b400.GROUPS}
    names = {(start, stop): name for name, start, stop in b400.BLOCKS}
    blocks = []
    for (group, _, _), subblocks in zip(b400.GROUPS, b400.SUBBLOCKS):
        for start, stop in subblocks:
            name = names.get((start, stop), f'P_cell_{(start-272)//16}')
            distance = float(squared[start:stop].sum(dtype=np.float64))
            block = dict(name=name, group=group, start=start, stop=stop,
                         distance=distance, fraction=distance/total if total else 0.)
            if query_validity is not None:
                block['query_valid_dimensions'] = int(np.count_nonzero(query_validity[start:stop]))
            if candidate_validity is not None:
                block['candidate_valid_dimensions'] = int(np.count_nonzero(candidate_validity[start:stop]))
            blocks.append(block)
    return dict(distance=total, groups=groups,
                group_fractions={name: value/total if total else 0. for name, value in groups.items()},
                subblocks=blocks,
                contributions_sum_matches=bool(np.isclose(sum(groups.values()), total, rtol=1e-12, atol=1e-14)
                    and np.isclose(sum(block['distance'] for block in blocks), total, rtol=1e-12, atol=1e-14)))


def _reference(index, source_hash, rgb, used_mask, vectors, exclude_self, deduplicate, actual_hits):
    matches = [(i, row) for i, row in enumerate(index.records) if row['sha256'] == source_hash]
    if not matches:
        return dict(available=False, reason='Input SHA-256 does not match a corpus image; no reference-mask metric is available.')
    comparisons, flipped_cache = [], {}
    used = used_mask > 0
    for position, record in matches:
        source = safe_path(index.root, record['path'])
        if digest(source.read_bytes()) != source_hash:
            raise ValueError(f'Corpus source bytes changed: {record["filename"]}')
        mask_path = safe_path(index.root, record['mask_path'])
        if digest(mask_path.read_bytes()) != record['mask_sha256']:
            raise ValueError(f'Approved mask bytes changed: {record["filename"]}')
        approved_mask, _ = load_mask(mask_path, rgb)
        approved = approved_mask > 0
        intersection = int(np.count_nonzero(used & approved))
        union = int(np.count_nonzero(used | approved))
        symmetric = int(np.count_nonzero(used ^ approved))
        # Reuse the stored original vector. The independent flip must pass
        # through the complete feature extractor, never a vector permutation.
        key = record['mask_sha256']
        if key not in flipped_cache:
            _, flipped, _, _ = b400.extract_normalized(
                np.ascontiguousarray(rgb[:, ::-1]),
                np.ascontiguousarray(approved_mask[:, ::-1]), index.normalizer)
            flipped_cache[key] = flipped
        ranked = index.search(index.matrix[position], flipped_cache[key], source_hash, exclude_self,
                              deduplicate=deduplicate)
        old_names = {hit['filename'] for hit in actual_hits}
        new_names = {hit['filename'] for hit in ranked['results']}
        comparisons.append(dict(filename=record['filename'], candidate_row=position,
            mask_path=record['mask_path'], mask_sha256=record['mask_sha256'],
            review_status=record.get('review_status'), review_result=record.get('review_result'),
            agreement=dict(iou=intersection/union, intersection_pixels=intersection,
                union_pixels=union, used_area_pixels=int(used.sum()), approved_area_pixels=int(approved.sum()),
                used_area_fraction=float(used.mean()), approved_area_fraction=float(approved.mean()),
                symmetric_difference_pixels=symmetric, symmetric_difference_fraction=symmetric/used.size,
                identical=bool(np.array_equal(used, approved)),
                interpretation='Agreement with an approved mask; not segmentation accuracy or ground truth.'),
            original_vector_comparison=_decompose(vectors['original']['normalized'], index.matrix[position],
                vectors['original']['validity'], np.asarray(record['validity'], dtype=bool)),
            approved_mask_search=dict(original_vector='stored corpus vector for this candidate row',
                flipped_vector='full horizontal flip of RGB and approved mask, complete frozen B400 extraction',
                exclude_self=exclude_self, excluded_self_files=ranked['excluded_self_files'],
                results=[_brief(hit) for hit in ranked['results']],
                top5_filename_overlap=len(old_names & new_names))))
    return dict(available=True, matching_corpus_rows=len(matches), comparisons=comparisons,
                note='The alternative ranking is a mask-sensitivity check. No automatic relevance judgment is made.')


def diagnose(index, query_directory, destination=None):
    """Diagnose a saved query and write only a new outputs/search directory.

    Structural errors and changed input artifacts fail before publication.
    Scaler/identity/ranking mismatches are reported explicitly. Destination is
    an output parent; each report receives a non-overwriting query subfolder.
    """
    directory = Path(query_directory).resolve()
    if not directory.is_dir():
        raise ValueError(f'Saved query directory does not exist: {directory}')
    result = _json(safe_path(directory, 'result.json'))
    configuration = _json(safe_path(directory, 'configuration.json'))
    query_id = result['query_id']
    if not isinstance(query_id, str) or not query_id or Path(query_id).name != query_id or query_id in {'.', '..'}:
        raise ValueError('Invalid saved query ID')
    vectors = _vectors(directory)
    query = result['query']
    with Image.open(safe_path(directory, 'query_rgb.png')) as image:
        image.load()
        if image.format != 'PNG' or image.mode != 'RGB' or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Saved query RGB must be a single-frame RGB PNG')
        rgb = np.array(image)
    mask, _ = load_mask(safe_path(directory, 'mask.png'), rgb)
    inputs = [directory/name for name in ('input.jpg', 'input.png') if (directory/name).is_file()]
    if len(inputs) != 1:
        raise ValueError('Saved query must contain exactly one input.jpg or input.png')
    source = load_image(safe_path(directory, inputs[0].name))
    integrity = dict(source_sha256=source.sha256 == query['source_sha256'],
        rgb_matches_input=bool(np.array_equal(source.rgb, rgb)),
        rgb_pixels_sha256=digest(rgb.tobytes()) == query['rgb_pixels_sha256'],
        mask_pixels_sha256=digest(mask.tobytes()) == query['mask_pixels_sha256'],
        saved_mask_sha256=digest((directory/'mask.png').read_bytes()) == query['saved_mask_sha256'],
        dimensions=rgb.shape[:2] == (query['height'], query['width']))
    if not all(integrity.values()):
        failed = ', '.join(key for key, value in integrity.items() if not value)
        raise ValueError(f'Saved query artifacts failed integrity checks: {failed}')
    description = index.describe()
    identities = {key: dict(saved=result['index'].get(key), current=description[key],
                           matches=result['index'].get(key) == description[key])
                  for key in ('run_id', 'feature_set_id', 'normalizer_id')}
    configuration_matches = dict(feature_set=_json_equal(configuration.get('feature_set'), index.spec),
        normalizer=_json_equal(configuration.get('normalizer'), index.normalizer),
        selected_run=_json_equal(configuration.get('selected_run'), index.run))
    normalization = {}
    for variant, arrays in vectors.items():
        reproduced = b400.transform(arrays['raw'], arrays['validity'], index.normalizer)
        normalization[variant] = dict(exact_match=bool(np.array_equal(reproduced, arrays['normalized'])),
            max_absolute_difference=float(np.abs(reproduced.astype(float)-arrays['normalized']).max()),
            valid_dimensions=int(arrays['validity'].sum()),
            saved_vector_norm=float(np.linalg.norm(arrays['normalized'].astype(float))))
    exclude_self, deduplicate = _exclude_self(result), _deduplicate(result)
    ranked = index.search(vectors['original']['normalized'], vectors['flipped']['normalized'], source.sha256,
                          exclude_self, deduplicate=deduplicate)
    checks = []
    for position in range(max(len(result['results']), len(ranked['results']))):
        saved = result['results'][position] if position < len(result['results']) else None
        actual = ranked['results'][position] if position < len(ranked['results']) else None
        check = dict(rank=position+1, saved_filename=saved['filename'] if saved else None,
                     actual_filename=actual['filename'] if actual else None)
        for key in ('filename', 'path', 'sha256', 'orientation'):
            check[key+'_matches'] = saved is not None and actual is not None and saved[key] == actual[key]
        for key in ('distance', 'original_distance', 'flipped_distance'):
            check[key+'_matches'] = bool(saved is not None and actual is not None
                and np.isclose(saved[key], actual[key], rtol=1e-12, atol=1e-14))
        checks.append(check)
    row_positions = {(row['filename'], row['path'], row['sha256']): i for i, row in enumerate(index.records)}
    hits = []
    for hit in ranked['results']:
        position = row_positions[(hit['filename'], hit['path'], hit['sha256'])]
        arrays = vectors[hit['orientation']]
        hits.append(dict(**_brief(hit), candidate_row=position,
            decomposition=_decompose(arrays['normalized'], index.matrix[position], arrays['validity'],
                np.asarray(index.records[position]['validity'], dtype=bool))))
    reference = _reference(index, source.sha256, rgb, mask, vectors, exclude_self, deduplicate, ranked['results'])
    report = dict(version=1, created_at_utc=datetime.now(timezone.utc).isoformat(),
        query_id=query_id, query_directory=str(directory), index=description,
        identity=identities, configuration_matches=configuration_matches,
        artifact_integrity=integrity, normalization=normalization,
        reranking=dict(exclude_self=exclude_self, deduplicate=deduplicate,
            excluded_self_files=ranked['excluded_self_files'],
            saved_excluded_self_files=result.get('excluded_self_files'),
            excluded_self_count_matches=ranked['excluded_self_files'] == result.get('excluded_self_files'),
            all_saved_hits_match=all(value for check in checks for key, value in check.items() if key.endswith('_matches')),
            rank_checks=checks), hits=hits, reference_mask=reference,
        interpretation=dict(relevance='No automatic visual relevance, P@5, or label-based quality evaluation is performed.',
            target='Similarity of shape, color, and texture can cross animal labels.',
            mask='Mask agreement compares the saved query mask with an approved corpus mask, not ground truth.',
            vectors='Normalization is reproduced from saved raw/validity arrays; query descriptors are not re-extracted.',
            distance='Fixed squared L2 on frozen B400 vectors; validity counts are explanatory and do not change ranking.'))
    base = output_base(index.root, destination if destination is not None else Path(index.root)/'outputs/search/diagnostics')
    folder = base/query_id
    if folder.exists():
        folder = base/(query_id+'_'+uuid.uuid4().hex[:8])
    folder.mkdir(exist_ok=False)
    report['output_directory'] = str(folder)
    write_json(folder/'diagnostics.json', report)
    return report
