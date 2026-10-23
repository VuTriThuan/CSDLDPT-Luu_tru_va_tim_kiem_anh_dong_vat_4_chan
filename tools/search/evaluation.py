"""Batch retrieval and human visual relevance; labels are a separate diagnostic."""
import csv
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
import time
import uuid

from tools.search.index import read_json
from tools.search.query import load_image, load_mask, create_mask, refine, retrieve, output_base, write_json, digest
from tools.features.inputs import safe_path
from tools.project_paths import PROJECT_ROOT

FIELDS = ['query_id', 'purpose', 'group', 'query_label', 'rank', 'filename', 'sha256',
          'result_image', 'query_image', 'query_mask', 'result_label', 'distance', 'orientation',
          'same_label', 'visual_relevant', 'notes']
PURPOSES = {'independent', 'functional_check', 'unverified'}


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def run_batch(index, manifest, destination=None):
    """Relative image/mask/strokes paths are relative to manifest, not cwd."""
    manifest = Path(manifest).resolve()
    rows = read_csv(manifest)
    if not rows:
        raise ValueError('Empty query manifest')
    ids = [r.get('query_id', '').strip() for r in rows]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('Manifest requires unique, nonempty query_id values')
    base = output_base(index.root, destination)
    folder = base/('batch_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+uuid.uuid4().hex[:6])
    folder.mkdir(exist_ok=False)
    records, judging = [], []
    corpus_hashes = {r['sha256'] for r in index.records}
    resolve = lambda text: (manifest.parent/Path(text).expanduser()).resolve()
    for entry in rows:
        start = time.perf_counter()
        record = dict(query_id=entry['query_id'], group=entry.get('group') or entry.get('label') or '(unlabelled)',
                      query_label=entry.get('label', ''), purpose=entry.get('purpose') or 'unverified',
                      status='failed', error='', result_json=None, returned=0)
        try:
            if record['purpose'] not in PURPOSES:
                raise ValueError(f'purpose must be one of {sorted(PURPOSES)}')
            if not entry.get('image'):
                raise ValueError('Missing image path')
            query = load_image(resolve(entry['image']))
            if query.sha256 in corpus_hashes:
                record['purpose'] = 'functional_check'
            if entry.get('mask'):
                mask, info = load_mask(resolve(entry['mask']), query.rgb)
            else:
                bbox = tuple(int(entry[k]) for k in ['x', 'y', 'width', 'height']) if entry.get('x') else None
                mask, info = create_mask(query.rgb, bbox)
            if entry.get('strokes'):
                from PIL import Image
                import numpy as np
                with Image.open(resolve(entry['strokes'])) as image:
                    strokes = np.array(image)
                mask, seconds = refine(query.rgb, mask, strokes)
                info.update(mask_seconds=info['mask_seconds']+seconds, refinement='hard strokes')
            else:
                strokes = None
            result = retrieve(index, query, mask, info, folder/'queries', strokes=strokes)
            query_folder = Path(result['output_directory'])
            record.update(status='success', result_json=(query_folder/'result.json').relative_to(folder).as_posix(),
                          artifact_query_id=result['query_id'],
                          result_sha256=digest((query_folder/'result.json').read_bytes()),
                          returned=result['returned'], timings=result['timings'])
            for hit in result['results']:
                judging.append(dict(query_id=record['query_id'], purpose=record['purpose'], group=record['group'],
                    query_label=record['query_label'], rank=hit['rank'], filename=hit['filename'], sha256=hit['sha256'],
                    result_image=(query_folder/hit['artifact_image']).relative_to(folder).as_posix(),
                    query_image=(query_folder/'query_rgb.png').relative_to(folder).as_posix(),
                    query_mask=(query_folder/'mask.png').relative_to(folder).as_posix(),
                    result_label=hit['label'], distance=hit['distance'],
                    orientation=hit['orientation'], same_label=int(hit['label'] == record['query_label']) if record['query_label'] else '',
                    visual_relevant='', notes=''))
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
        record['elapsed_seconds'] = time.perf_counter()-start
        records.append(record)
    report = dict(artifact_paths_version=2, manifest=str(manifest), index=index.describe(), queries=records,
                  purpose_note='Only purpose=independent enters retrieval metrics; corpus hash queries are always functional_check.',
                  visual_note='Blank human relevance is unjudged, never inferred from labels.')
    write_json(folder/'batch.json', report)
    write_csv(folder/'judgments.csv', judging, FIELDS)
    score_batch(folder/'batch.json', folder/'judgments.csv', folder, index.root)
    return folder


def summarize(queries):
    """Macro mean over fully judged top-5 independent queries only."""
    independent = [r for r in queries if r['purpose'] == 'independent']
    visual = [r['visual_p_at_5'] for r in independent if r['visual_p_at_5'] is not None]
    labelled = [r['same_label_at_5'] for r in independent if r['same_label_at_5'] is not None]
    return dict(queries=len(queries), independent_queries=len(independent),
                functional_queries=sum(r['purpose'] == 'functional_check' for r in queries),
                unverified_queries=sum(r['purpose'] == 'unverified' for r in queries),
                errors=sum(r['status'] != 'success' for r in queries),
                fully_judged_independent_queries=len(visual),
                visual_p_at_5=sum(visual)/len(visual) if visual else None,
                labelled_independent_queries=len(labelled),
                same_label_at_5=sum(labelled)/len(labelled) if labelled else None,
                mean_elapsed_seconds=sum(r['elapsed_seconds'] for r in queries)/len(queries) if queries else None)


def resolve_result(batch_path, batch, query):
    """Resolve only canonical artifacts inside this batch, never open old roots.

    Legacy absolute paths are evidence of the old location, not file access
    authority. Map only .../outputs/search/.../batch_*/queries/ID/result.json,
    then cross-check the local result's ID, original directory and index IDs.
    """
    folder = Path(batch_path).resolve().parent
    text = query['result_json']
    # Persisted paths are protocol text, independent of the current host OS.
    stored = PureWindowsPath(text) if PureWindowsPath(text).is_absolute() else PurePosixPath(text)
    if '..' in stored.parts:
        raise ValueError(f'Unsafe batch artifact path: {stored}')
    legacy = stored.is_absolute()
    if legacy:
        parts = stored.parts
        if (batch.get('artifact_paths_version') == 2 or len(parts) < 7
                or parts[-3] != 'queries' or parts[-1] != 'result.json'
                or not parts[-4].startswith('batch_')
                or not any(parts[i:i+2] == ('outputs', 'search') for i in range(len(parts)-4))):
            raise ValueError(f'Cannot safely map legacy batch artifact: {stored}')
        relative = Path(*parts[-3:])
    else:
        relative = stored
    if len(relative.parts) != 3 or relative.parts[0] != 'queries' or relative.name != 'result.json':
        raise ValueError(f'Artifact must be queries/QUERY_ID/result.json inside batch: {stored}')
    local = safe_path(folder, relative)
    if not local.is_file():
        raise ValueError(f'Missing artifact inside opened batch: {relative}; original absolute path is never opened')
    result = read_json(local)
    artifact_id = relative.parts[1]
    if batch.get('artifact_paths_version') == 2 and not query.get('artifact_query_id'):
        raise ValueError(f'Missing artifact query_id binding: {relative}')
    if result.get('query_id') != artifact_id or query.get('artifact_query_id', artifact_id) != artifact_id:
        raise ValueError(f'Artifact query_id mismatch: {query["query_id"]}, {relative}')
    if legacy and result.get('output_directory') != str(stored.parent):
        raise ValueError(f'Legacy artifact original directory mismatch: {relative}')
    for key in ('run_id', 'feature_set_id', 'normalizer_id'):
        if result.get('index', {}).get(key) != batch.get('index', {}).get(key) or key not in result.get('index', {}):
            raise ValueError(f'Artifact index metadata mismatch: {key}, {relative}')
    if query.get('returned') != len(result['results']):
        raise ValueError(f'Artifact returned metadata mismatch: {relative}')
    if [h['rank'] for h in result['results']] != list(range(1, len(result['results'])+1)):
        raise ValueError(f'Artifact rank metadata mismatch: {relative}')
    if batch.get('artifact_paths_version') == 2 and not query.get('result_sha256'):
        raise ValueError(f'Missing result checksum: {relative}')
    if query.get('result_sha256') and digest(local.read_bytes()) != query['result_sha256']:
        raise ValueError(f'Artifact checksum mismatch: {relative}')
    return local, result


def score_batch(batch_path, judgments_path, destination, project_root=PROJECT_ROOT):
    """Only visual_relevant (0/1/blank) and notes may be changed in the sheet."""
    batch = read_json(batch_path)
    ids = [q['query_id'] for q in batch['queries']]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError('Batch requires unique nonempty query_id values')
    rows = read_csv(judgments_path)
    keyed = {}
    for row in rows:
        key = (row['query_id'], int(row['rank']))
        if key in keyed:
            raise ValueError(f'Duplicate judgment: {key}')
        if row['visual_relevant'].strip() not in {'', '0', '1'}:
            raise ValueError(f'Visual relevance must be blank, 0 or 1: {key}')
        keyed[key] = row
    expected = set()
    reports = []
    artifacts = set()
    for query in batch['queries']:
        record = dict(query, visual_p_at_5=None, same_label_at_5=None, judged_results=0,
                      metric_status='query_failed' if query['status'] != 'success' else 'incomplete_top5_or_judgments')
        if query['status'] == 'success':
            artifact, result = resolve_result(batch_path, batch, query)
            if artifact in artifacts:
                raise ValueError(f'Duplicate batch artifact: {artifact}')
            artifacts.add(artifact)
            hits = result['results']
            relevant = []
            for hit in hits:
                key = (query['query_id'], hit['rank'])
                expected.add(key)
                row = keyed.get(key)
                if row is None:
                    raise ValueError(f'Missing judgment row: {key}; leave relevance blank instead of deleting rows')
                for field, value in [('sha256', hit['sha256']), ('filename', hit['filename']),
                                     ('purpose', query['purpose']), ('group', query['group']),
                                     ('query_label', query['query_label']), ('result_label', hit['label'])]:
                    if row[field] != value:
                        raise ValueError(f'Judgment identity/metadata changed: {key}, {field}')
                # Never open paths from the judging sheet. Check immutable fields
                # against the saved artifact (legacy paths remain literal evidence).
                text = query['result_json']
                stored_folder = (PureWindowsPath(text) if PureWindowsPath(text).is_absolute()
                                 else PurePosixPath(text)).parent
                for field, value in (
                    ('result_image', str(stored_folder/hit['artifact_image'])),
                    ('query_image', str(stored_folder/'query_rgb.png')),
                    ('query_mask', str(stored_folder/'mask.png')),
                    ('distance', str(hit['distance'])), ('orientation', hit['orientation']),
                    ('same_label', str(int(hit['label'] == query['query_label'])) if query['query_label'] else '')):
                    if row[field] != value:
                        raise ValueError(f'Judgment identity/metadata changed: {key}, {field}')
                value = row['visual_relevant'].strip()
                if value:
                    relevant.append(int(value))
            record['judged_results'] = len(relevant)
            if query['purpose'] != 'independent':
                record['metric_status'] = 'excluded_'+query['purpose']
            elif len(hits) == 5:
                if len(relevant) == 5:
                    record['visual_p_at_5'] = sum(relevant)/5
                    record['metric_status'] = 'fully_judged'
                if query['query_label']:
                    record['same_label_at_5'] = sum(h['label'] == query['query_label'] for h in hits)/5
        reports.append(record)
    if set(keyed) != expected:
        raise ValueError('Judgment contains unknown query/rank rows')
    groups = sorted({r['group'] for r in reports})
    report = dict(overall=summarize(reports),
                  by_group={g: summarize([r for r in reports if r['group'] == g]) for g in groups},
                  queries=reports,
                  definitions=dict(visual_p_at_5='sum of 5 manually judged binary visual relevance values / 5; all 5 required',
                                   same_label_at_5='metadata label agreement / 5; separate from visual relevance',
                                   overall='macro mean of eligible independent query scores; missing scores excluded, never zero-filled'))
    destination = output_base(project_root, destination)
    write_json(destination/'evaluation.json', report)
    fields = ['query_id', 'purpose', 'group', 'status', 'returned', 'judged_results', 'visual_p_at_5',
              'same_label_at_5', 'metric_status', 'elapsed_seconds', 'error']
    write_csv(destination/'per_query.csv', reports, fields)
    write_csv(destination/'per_group.csv', [dict(group=g, **r) for g, r in report['by_group'].items()],
              ['group', *report['overall'].keys()])
    return report
