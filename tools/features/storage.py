"""Versioned local SQLite B400 storage. All writes belong to one transaction."""
import json
import sqlite3

import numpy as np

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS feature_sets (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, dimensions INTEGER NOT NULL CHECK(dimensions=400),
 dtype TEXT NOT NULL CHECK(dtype='<f4'), config_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS images (
 id INTEGER PRIMARY KEY, path TEXT NOT NULL CHECK(path NOT LIKE '/%' AND path NOT LIKE '../%'),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), filename TEXT NOT NULL, label TEXT NOT NULL,
 width INTEGER NOT NULL, height INTEGER NOT NULL, UNIQUE(path,sha256));
CREATE TABLE IF NOT EXISTS masks (
 id INTEGER PRIMARY KEY, image_id INTEGER NOT NULL REFERENCES images(id), path TEXT NOT NULL,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), pixels INTEGER NOT NULL CHECK(pixels>0),
 UNIQUE(image_id,path,sha256), UNIQUE(id,image_id));
CREATE TABLE IF NOT EXISTS normalizers (
 id TEXT PRIMARY KEY, feature_set_id TEXT NOT NULL REFERENCES feature_sets(id),
 params_json TEXT NOT NULL, UNIQUE(id,feature_set_id));
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, feature_set_id TEXT NOT NULL REFERENCES feature_sets(id),
 normalizer_id TEXT, input_digest TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('running','complete','partial','failed')),
 audit_json TEXT NOT NULL, UNIQUE(id,feature_set_id,normalizer_id),
 FOREIGN KEY(normalizer_id,feature_set_id) REFERENCES normalizers(id,feature_set_id));
CREATE TABLE IF NOT EXISTS extraction_status (
 run_id TEXT NOT NULL REFERENCES runs(id), filename TEXT NOT NULL,
 image_id INTEGER REFERENCES images(id), mask_id INTEGER,
 status TEXT NOT NULL CHECK(status IN ('success','failed')), error TEXT NOT NULL,
 metadata_json TEXT NOT NULL, PRIMARY KEY(run_id,filename),
 FOREIGN KEY(mask_id,image_id) REFERENCES masks(id,image_id),
 CHECK(status!='success' OR (image_id IS NOT NULL AND mask_id IS NOT NULL AND error='')));
CREATE TABLE IF NOT EXISTS vectors (
 run_id TEXT NOT NULL, filename TEXT NOT NULL, feature_set_id TEXT NOT NULL, normalizer_id TEXT NOT NULL,
 dimensions INTEGER NOT NULL CHECK(dimensions=400), dtype TEXT NOT NULL CHECK(dtype='<f4'),
 raw BLOB NOT NULL CHECK(length(raw)=1600), normalized BLOB NOT NULL CHECK(length(normalized)=1600),
 validity BLOB NOT NULL CHECK(length(validity)=400), PRIMARY KEY(run_id,filename),
 FOREIGN KEY(run_id,filename) REFERENCES extraction_status(run_id,filename),
 FOREIGN KEY(run_id,feature_set_id,normalizer_id) REFERENCES runs(id,feature_set_id,normalizer_id));
CREATE INDEX IF NOT EXISTS status_by_image ON extraction_status(image_id,run_id);
CREATE TRIGGER IF NOT EXISTS vector_requires_success BEFORE INSERT ON vectors
 WHEN (SELECT status FROM extraction_status WHERE run_id=NEW.run_id AND filename=NEW.filename)!='success'
 BEGIN SELECT RAISE(ABORT,'Vector requires successful extraction'); END;
'''


def dumps(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)


def connect(path, readonly=False):
    db=sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro' if readonly else str(path),uri=readonly)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    if not readonly:
        db.executescript(SCHEMA)
    return db


def save(db, feature_set, run, records, raw, normalized, validity, normalizer):
    with db:
        db.execute('INSERT OR IGNORE INTO feature_sets VALUES(?,?,?,?,?)',
                   (feature_set['id'],'b400_v1',400,'<f4',dumps(feature_set)))
        if normalizer:
            db.execute('INSERT OR IGNORE INTO normalizers VALUES(?,?,?)',
                       (normalizer['id'],feature_set['id'],dumps(normalizer)))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                   'completed_at=excluded.completed_at,status=excluded.status,audit_json=excluded.audit_json',
                   (run['id'],feature_set['id'],normalizer['id'] if normalizer else None,
                    run['input_digest'],run['created_at'],run['completed_at'],run['status'],dumps(run['audit'])))
        index=0
        for row in records:
            image_id=mask_id=None
            if row['validation_status']=='success':
                db.execute('INSERT OR IGNORE INTO images(path,sha256,filename,label,width,height) VALUES(?,?,?,?,?,?)',
                    (row['source_path'],row['source_sha256'],row['filename'],row['label'],row['width'],row['height']))
                image_id=db.execute('SELECT id FROM images WHERE path=? AND sha256=?',
                                     (row['source_path'],row['source_sha256'])).fetchone()[0]
                db.execute('INSERT OR IGNORE INTO masks(image_id,path,sha256,pixels) VALUES(?,?,?,?)',
                           (image_id,row['mask_path'],row['mask_sha256'],row['mask_pixels']))
                mask_id=db.execute('SELECT id FROM masks WHERE image_id=? AND path=? AND sha256=?',
                                  (image_id,row['mask_path'],row['mask_sha256'])).fetchone()[0]
            db.execute('INSERT INTO extraction_status VALUES(?,?,?,?,?,?,?) ON CONFLICT(run_id,filename) '
                       'DO UPDATE SET image_id=excluded.image_id,mask_id=excluded.mask_id,status=excluded.status,'
                       'error=excluded.error,metadata_json=excluded.metadata_json',
                       (run['id'],row['filename'],image_id,mask_id,row['feature_status'],row['error'],dumps(row)))
            if row['feature_status']=='success':
                for v in [raw[index],normalized[index]]:
                    if v.shape!=(400,) or not np.isfinite(v).all():
                        raise ValueError('Invalid database vector')
                db.execute('INSERT INTO vectors VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,filename) '
                           'DO UPDATE SET raw=excluded.raw,normalized=excluded.normalized,validity=excluded.validity',
                    (run['id'],row['filename'],feature_set['id'],normalizer['id'],400,'<f4',
                     raw[index].astype('<f4').tobytes(),normalized[index].astype('<f4').tobytes(),
                     validity[index].astype(np.uint8).tobytes()))
                index+=1
            else:
                db.execute('DELETE FROM vectors WHERE run_id=? AND filename=?',(run['id'],row['filename']))
        if index!=len(raw):
            raise ValueError('Vector count differs from successful records')


def read_vector(db, run_id, filename):
    row=db.execute('SELECT v.*,s.metadata_json,i.path,i.sha256 AS source_sha256,m.sha256 AS mask_sha256 '
                   'FROM vectors v JOIN extraction_status s USING(run_id,filename) '
                   'JOIN images i ON i.id=s.image_id JOIN masks m ON m.id=s.mask_id '
                   'WHERE v.run_id=? AND v.filename=?',(run_id,filename)).fetchone()
    if row is None:
        raise KeyError(f'No vector for {filename} in run {run_id}')
    result=dict(row)
    for key in ['raw','normalized']:
        result[key]=np.frombuffer(result[key],dtype='<f4').copy()
        if result[key].shape!=(400,) or not np.isfinite(result[key]).all():
            raise ValueError(f'Corrupt stored {key} vector: {filename}')
    result['validity']=np.frombuffer(result['validity'],dtype=np.uint8).astype(bool)
    return result


def status(db):
    return [dict(r) for r in db.execute('SELECT r.id,r.feature_set_id,r.normalizer_id,r.status,'
        'count(s.filename) AS images,sum(s.status="success") AS success,sum(s.status="failed") AS failed,'
        '(SELECT count(*) FROM vectors v WHERE v.run_id=r.id) AS vectors '
        'FROM runs r LEFT JOIN extraction_status s ON s.run_id=r.id GROUP BY r.id ORDER BY r.created_at')]
