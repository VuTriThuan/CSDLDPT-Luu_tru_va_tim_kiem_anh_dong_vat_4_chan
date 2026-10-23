"""Exact replay of saved rankings; never edits historical artifacts."""
from tools.search.policies import search_options


def replay_ranking(index, result, original, flipped):
    options = search_options(result)
    computed = index.search(original, flipped, result['query']['source_sha256'], **options)
    reasons = []
    for field in ('run_id', 'feature_set_id', 'normalizer_id'):
        if result['index'].get(field) != index.describe()[field]:
            reasons.append(dict(field='index.'+field, saved=result['index'].get(field),
                                computed=index.describe()[field]))
    for field in ('excluded_self_files', 'returned'):
        if result.get(field) != computed[field]:
            reasons.append(dict(field=field, saved=result.get(field), computed=computed[field]))
    saved_hits, actual_hits = result['results'], computed['results']
    if len(saved_hits) != len(actual_hits):
        reasons.append(dict(field='results.length', saved=len(saved_hits), computed=len(actual_hits)))
    fields = ('rank', 'filename', 'path', 'sha256', 'distance', 'orientation',
              'original_distance', 'flipped_distance', 'group_distances')
    for position, (saved, actual) in enumerate(zip(saved_hits, actual_hits), 1):
        for field in fields:
            if saved.get(field) != actual[field]:
                reasons.append(dict(rank=position, field=field, saved=saved.get(field), computed=actual[field]))
    return dict(options=options, ranking_reproduces_exactly=not reasons, reasons=reasons,
                saved_results=[{key: hit.get(key) for key in fields} for hit in saved_hits],
                computed_results=[{key: hit[key] for key in fields} for hit in computed['results']])
