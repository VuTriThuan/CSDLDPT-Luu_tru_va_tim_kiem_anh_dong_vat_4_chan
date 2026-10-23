"""Verify real relocated batches and pre-edit hashes without rebuilding B400.

Run after the real batch CLI recorded in new_portable_batch.log.
"""
import json
from pathlib import Path
import shutil
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.project_paths import PROJECT_ROOT
from tools.search.evaluation import resolve_result, score_batch
from tools.search.index import read_json
from tools.search.query import digest, write_json


def hashes(folder):
    return {p.relative_to(folder).as_posix(): digest(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}


def main():
    root = PROJECT_ROOT
    base = root/'outputs/search/portability_checks'
    modern_sources = sorted((base/'new_batches').glob('batch_*/batch.json'))
    if len(modern_sources) != 1:
        raise ValueError('Expected exactly one real new batch in portability_checks/new_batches')
    modern = modern_sources[0].parent
    moved = base/'new_batch_moved_20261023'
    if not moved.exists():
        shutil.copytree(modern, moved)
    cases = [('legacy', root/'outputs/search/functional_checks/batch_20261022T154444_232219Z_9268a9',
              base/'legacy_batch_moved_20261023'), ('relative_v2', modern, moved)]
    evidence = []
    for kind, source, target in cases:
        before = hashes(source)
        # Every original batch file must have survived copying byte-for-byte.
        copied = hashes(target)
        assert all(copied.get(name) == sha for name, sha in before.items())
        batch = read_json(target/'batch.json')
        resolved = []
        for q in batch['queries']:
            if q['status'] == 'success':
                local, result = resolve_result(target/'batch.json', batch, q)
                assert local.is_relative_to(target)
                resolved.append(dict(query_id=q['query_id'], artifact_query_id=result['query_id'],
                                     stored_path=q['result_json'], resolved_path=local.relative_to(root).as_posix()))
        result = score_batch(target/'batch.json', target/'judgments.csv', target/'rescored', root)
        assert result['overall'] == read_json(source/'evaluation.json')['overall']
        assert hashes(source) == before
        copied_after = hashes(target)
        assert all(copied_after.get(name) == sha for name, sha in before.items())
        evidence.append(dict(format=kind, original_files=len(before), original_and_copied_files_unchanged=True,
                             overall_matches_original=True, overall=result['overall'], local_artifacts=resolved))
    snapshot = read_json(root/'outputs/search/verification/completion_before.json')
    changed = [name for name, sha in snapshot.items() if not (root/name).is_file() or digest((root/name).read_bytes()) != sha]
    assert not changed, changed
    report = dict(passed=True, protected_files_checked=len(snapshot), changed=changed,
                  protected_scope='See completion_before.json: data, inventory, segmentation, B400 artifacts/code, saved result.json and historical batch query artifacts.',
                  relocated_batches=evidence)
    write_json(root/'outputs/search/verification/completion_checks.json', report)
    print(json.dumps(dict(passed=True, protected_files_checked=len(snapshot), relocated_batches=len(evidence))))


if __name__ == '__main__':
    main()
