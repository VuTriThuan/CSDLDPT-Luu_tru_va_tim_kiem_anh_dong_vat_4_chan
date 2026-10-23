"""Batch retrieval and human visual relevance; labels are a separate diagnostic."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import time
import uuid

from tools.search.index import read_json
from tools.search.query import load_image, load_mask, create_mask, refine, retrieve, output_base, write_json
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
            record.update(status='success', result_json=str(query_folder/'result.json'),
                          returned=result['returned'], timings=result['timings'])
            for hit in result['results']:
                judging.append(dict(query_id=record['query_id'], purpose=record['purpose'], group=record['group'],
                    query_label=record['query_label'], rank=hit['rank'], filename=hit['filename'], sha256=hit['sha256'],
                    result_image=str(query_folder/hit['artifact_image']), query_image=str(query_folder/'query_rgb.png'),
                    query_mask=str(query_folder/'mask.png'), result_label=hit['label'], distance=hit['distance'],
                    orientation=hit['orientation'], same_label=int(hit['label'] == record['query_label']) if record['query_label'] else '',
                    visual_relevant='', notes=''))
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
        record['elapsed_seconds'] = time.perf_counter()-start
        records.append(record)
    report = dict(manifest=str(manifest), index=index.describe(), queries=records,
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


def score_batch(batch_path, judgments_path, destination, project_root=PROJECT_ROOT):
    """Only visual_relevant (0/1/blank) and notes may be changed in the sheet."""
    batch = read_json(batch_path)
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
    for query in batch['queries']:
        record = dict(query, visual_p_at_5=None, same_label_at_5=None, judged_results=0,
                      metric_status='query_failed' if query['status'] != 'success' else 'incomplete_top5_or_judgments')
        if query['status'] == 'success':
            result = read_json(query['result_json'])
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
