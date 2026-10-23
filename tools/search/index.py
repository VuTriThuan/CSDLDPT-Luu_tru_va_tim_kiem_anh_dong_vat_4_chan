"""Read one completed SQLite run once; rank without labels or extra weights."""
import json
from pathlib import Path
import sqlite3
import time

import numpy as np

from tools.features import b400, storage
from tools.features.compatibility import check_feature_set
from tools.features.publication import recover_output
from tools.file_lock import file_lock
from tools.features.inputs import safe_path
from tools.project_paths import B400_OUTPUT_DIR, PROJECT_ROOT


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check_normalizer(params, run):
    check = dict(params)
    identifier = check.pop('id')
    if identifier != run['normalizer_id'] or b400.digest_json(check) != identifier:
        raise ValueError('Normalizer ID/checksum differs from selected run')
    if params['feature_config_sha256'] != b400.digest_json(b400.configuration()):
        raise ValueError('Normalizer B400 configuration differs')
    if params['version'] != 1:
        raise ValueError('Unsupported normalizer version')
    canonical = lambda x: json.loads(json.dumps(x))
    if canonical(params['rules']) != canonical(b400.configuration()['normalization']):
        raise ValueError('Normalizer rules differ')
    for name in ['mean', 'scale', 'valid_counts', 'constant']:
        values = np.asarray(params[name])
        if values.shape != (400,) or not np.isfinite(values).all():
            raise ValueError(f'Invalid scaler {name}: expected 400 finite values')
    if (np.asarray(params['scale']) <= 0).any():
        raise ValueError('Scaler scale must be positive')
    if params['fit_digest'] != run['input_digest'] or params['fit_rows'] <= 0:
        raise ValueError('Scaler fit provenance differs from selected run')


def rank(matrix, records, original, flipped, query_hash=None, exclude_self=True, k=5, deduplicate=False):
    """Exact squared L2, float64 accumulation; ties: filename, path, hash.

    Each eligible file is a candidate by default, including byte-identical
    copies. The former SHA-256 grouping remains available for checking saved
    historical results. Equal original/flip distances choose original.
    Validity is explanatory metadata, never a pair-dependent distance mask.
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    original, flipped = (np.asarray(v, dtype=np.float64) for v in [original, flipped])
    if matrix.ndim != 2 or matrix.shape[1] != 400 or len(records) != len(matrix):
        raise ValueError('Expected aligned Nx400 candidate matrix and records')
    if original.shape != (400,) or flipped.shape != (400,):
        raise ValueError('Expected two 400-dimensional query vectors')
    if not all(np.isfinite(v).all() for v in [matrix, original, flipped]):
        raise ValueError('Non-finite search vector')
    if k != 5:
        raise ValueError('This retrieval contract uses top 5')
    d0 = np.square(matrix-original).sum(axis=1, dtype=np.float64)
    d1 = np.square(matrix-flipped).sum(axis=1, dtype=np.float64)
    distances = np.minimum(d0, d1)
    excluded = [exclude_self and query_hash is not None and r['sha256'] == query_hash for r in records]
    order = sorted((i for i in range(len(records)) if not excluded[i]),
                   key=lambda i: (distances[i], records[i]['filename'], records[i]['path'], records[i]['sha256']))
    seen, results = set(), []
    for i in order:
        row = records[i]
        if deduplicate and row['sha256'] in seen:
            continue
        seen.add(row['sha256'])
        variant = 'flipped' if d1[i] < d0[i] else 'original'
        q = flipped if variant == 'flipped' else original
        parts = {name: float(np.square(q[start:stop]-matrix[i, start:stop]).sum(dtype=np.float64))
                 for name, start, stop in b400.GROUPS}
        if not np.isclose(sum(parts.values()), distances[i], rtol=1e-12, atol=1e-14):
            raise ValueError('Distance contributions do not sum to total')
        results.append(dict(rank=len(results)+1, **row, distance=float(distances[i]),
                            orientation=variant, group_distances=parts,
                            original_distance=float(d0[i]), flipped_distance=float(d1[i])))
        if len(results) == k:
            break
    eligible = [r for i, r in enumerate(records) if not excluded[i]]
    unique = len({r['sha256'] for r in eligible})
    available = unique if deduplicate else len(eligible)
    return dict(results=results, candidate_files=len(records),
                candidate_unique_contents=len({r['sha256'] for r in records}),
                excluded_self_files=sum(excluded), eligible_files=len(eligible), eligible_unique_contents=unique,
                returned=len(results), requested=k,
                shortfall_reason=(f'Only {available} eligible {"SHA-256 contents" if deduplicate else "files"} '
                                  f'after self exclusion' if available < k else None),
                policies=dict(distance='sum((q-x)**2), no additional group weights',
                              orientation='min(original, flipped); original wins exact orientation ties',
                              ties='distance, filename (Unicode lexical), path, sha256',
                              duplicates=('one representative per SHA-256; lowest distance then lexical tie' if deduplicate
                                          else 'all eligible files ranked independently, including identical SHA-256'),
                              self_match='exclude all identical input-byte SHA-256' if exclude_self else 'include self matches',
                              validity='fixed normalized vector, no pair-specific validity reweighting',
                              labels='display/evaluation only'))


class SearchIndex:
    def __init__(self, feature_dir=B400_OUTPUT_DIR, run_id=None, project_root=PROJECT_ROOT):
        feature_dir = Path(feature_dir).resolve()
        with file_lock(feature_dir.parent/f'.{feature_dir.name}.lock'):
            recover_output(feature_dir)
            self._load(feature_dir, run_id, project_root)

    def _load(self, feature_dir, run_id, project_root):
        start = time.perf_counter()
        self.root, self.feature_dir = Path(project_root).resolve(), Path(feature_dir).resolve()
        summary = read_json(self.feature_dir/'summary.json')
        selected = run_id or summary['run_id']
        current = selected == summary['run_id']
        db = storage.connect(self.feature_dir/'features.sqlite3', readonly=True)
        try:
            # One consistent snapshot, even if another process publishes a new run.
            db.execute('BEGIN')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('SQLite integrity/foreign keys failed')
            run = db.execute('SELECT * FROM runs WHERE id=?', (selected,)).fetchone()
            if run is None or run['status'] != 'complete' or not run['completed_at']:
                raise ValueError(f'Selected run is missing or not complete: {selected}')
            self.run = dict(run)
            spec_row = db.execute('SELECT * FROM feature_sets WHERE id=?', (run['feature_set_id'],)).fetchone()
            self.spec = json.loads(spec_row['config_json'])
            if self.spec['id'] != run['feature_set_id'] or (spec_row['dimensions'], spec_row['dtype']) != (400, '<f4'):
                raise ValueError('B400 configuration/code/runtime differs from selected feature set; no automatic rebuild')
            self.compatibility = check_feature_set(self.spec)
            if read_json(self.feature_dir/'feature_set.json') != self.spec:
                raise ValueError('Feature configuration sidecar differs from SQLite')
            scaler_row = db.execute('SELECT * FROM normalizers WHERE id=? AND feature_set_id=?',
                                    (run['normalizer_id'], run['feature_set_id'])).fetchone()
            if scaler_row is None:
                raise ValueError('Missing scaler for selected run/feature set')
            self.normalizer = json.loads(scaler_row['params_json'])
            check_normalizer(self.normalizer, run)
            if current:
                if (summary['status'], summary['feature_set_id'], summary['normalizer_id']) != ('complete', run['feature_set_id'], run['normalizer_id']):
                    raise ValueError('Current summary run/scaler/configuration mismatch')
                if read_json(self.feature_dir/'normalizer.json') != self.normalizer:
                    raise ValueError('Scaler sidecar differs from selected SQLite scaler')
            rows = db.execute('''SELECT v.*, s.status AS extraction_state, s.metadata_json,
                i.path, i.sha256, i.label, i.width, i.height, m.path AS mask_path, m.sha256 AS mask_sha256
                FROM vectors v JOIN extraction_status s USING(run_id,filename)
                JOIN images i ON i.id=s.image_id JOIN masks m ON m.id=s.mask_id AND m.image_id=i.id
                WHERE v.run_id=? ORDER BY v.filename''', (selected,)).fetchall()
            counts = db.execute('SELECT count(*),sum(status="success") FROM extraction_status WHERE run_id=?', (selected,)).fetchone()
            vector_count = db.execute('SELECT count(*) FROM vectors WHERE run_id=?', (selected,)).fetchone()[0]
            if not rows or len(rows) != counts[0] or len(rows) != counts[1] or len(rows) != vector_count:
                raise ValueError('Completed run has missing vectors or failed/missing status records')
            if current and len(rows) != summary['vector_success']:
                raise ValueError('Summary vector count differs from SQLite')
            if self.normalizer['fit_rows'] != len(rows):
                raise ValueError('Scaler fit row count differs from completed run')
            self.records, vectors = [], []
            for row in rows:
                if (row['feature_set_id'], row['normalizer_id'], row['dimensions'], row['dtype'], row['extraction_state']) != (run['feature_set_id'], run['normalizer_id'], 400, '<f4', 'success'):
                    raise ValueError(f'Incompatible vector: {row["filename"]}')
                decoded = {}
                for key in ['raw', 'normalized', 'validity']:
                    dtype = np.uint8 if key == 'validity' else '<f4'
                    decoded[key] = np.frombuffer(row[key], dtype=dtype)
                    if decoded[key].shape != (400,) or not np.isfinite(decoded[key]).all():
                        raise ValueError(f'Corrupt {key}: {row["filename"]}')
                if not np.isin(decoded['validity'], [0, 1]).all():
                    raise ValueError('Validity must contain only 0/1')
                valid = decoded['validity'].astype(bool)
                if not np.array_equal(b400.transform(decoded['raw'], valid, self.normalizer), decoded['normalized']):
                    raise ValueError(f'Frozen scaler does not reproduce stored vector: {row["filename"]}')
                metadata = json.loads(row['metadata_json'])
                for key, expected in [('filename', row['filename']), ('source_path', row['path']),
                                      ('source_sha256', row['sha256']), ('mask_sha256', row['mask_sha256'])]:
                    if metadata[key] != expected:
                        raise ValueError(f'Inconsistent {key} metadata: {row["filename"]}')
                for key in ['path', 'mask_path']:
                    if not safe_path(self.root, row[key]).is_file():
                        raise ValueError(f'Missing candidate {key}: {row[key]}')
                self.records.append(dict(filename=row['filename'], path=row['path'], sha256=row['sha256'],
                    label=row['label'], mask_path=row['mask_path'], mask_sha256=row['mask_sha256'],
                    width=row['width'], height=row['height'], validity=valid.tolist(),
                    quality=metadata.get('quality', {}), source_flags=metadata.get('source_flags', {}),
                    review_status=metadata.get('review_status'), review_result=metadata.get('review_result')))
                vectors.append(decoded['normalized'])
            self.matrix = np.stack(vectors).astype('<f4')
            self.matrix.setflags(write=False)
        except (KeyError, TypeError, sqlite3.Error) as exc:
            raise ValueError(f'Incompatible B400 database/configuration: {exc}') from exc
        finally:
            db.close()
        self.load_seconds = time.perf_counter()-start

    def describe(self):
        return dict(run_id=self.run['id'], feature_set_id=self.run['feature_set_id'],
                    normalizer_id=self.run['normalizer_id'], database=str(self.feature_dir/'features.sqlite3'),
                    candidate_files=len(self.records), candidate_unique_contents=len({r['sha256'] for r in self.records}),
                    dimensions=400, dtype=self.matrix.dtype.str, load_seconds=self.load_seconds,
                    compatibility=self.compatibility)

    def search(self, original, flipped, query_hash=None, exclude_self=True, deduplicate=False):
        return rank(self.matrix, self.records, original, flipped, query_hash, exclude_self,
                    deduplicate=deduplicate)
