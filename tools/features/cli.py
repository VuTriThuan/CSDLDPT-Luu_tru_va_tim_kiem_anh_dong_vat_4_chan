"""Requirement 3: validate, extract/upsert, verify and inspect local B400 SQLite."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import time

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

import cv2
import numpy as np

from tools.features import b400, inputs, storage
from tools.features.compatibility import feature_set, check_feature_set
from tools.features.publication import exchange_directories, recover_output
from tools.file_lock import file_lock
from tools.image_processing.tool_common import configure_console

from tools.project_paths import PROJECT_ROOT, CROPPED_IMAGES_DIR, GRABCUT_OUTPUT_DIR, INVENTORY_DIR, B400_OUTPUT_DIR
from tools.validation.audit_images import write_csv


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path,value):
    # Atomic publication: interruption leaves the previous complete file readable.
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def prepare_output(args):
    root=args.project_root.resolve()
    output=args.output_dir.resolve()
    if not output.is_relative_to(root):
        raise ValueError('Output must be inside project root')
    for source in [args.input_dir,args.segmentation_dir,args.inventory_csv,root/'data',root/'tools',root/'tests',root/'docs']:
        source=source.resolve()
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError(f'Input/protected directory and output overlap: {source}')
    if any(p.is_symlink() for p in [args.output_dir,*args.output_dir.parents]):
        raise ValueError('Output symlinks are not supported')
    output.parent.mkdir(parents=True,exist_ok=True)
    return root,output


def validate(args):
    report=inputs.audit(args.project_root,args.input_dir,args.segmentation_dir,args.inventory_csv)
    write_json(args.output_dir/'input_validation.json',report)
    return report


def extract_all(args):
    start=time.monotonic()
    root,output=args.project_root.resolve(),args.output_dir.resolve()
    spec=feature_set()
    check_feature_set(spec)
    config_path=output/'feature_set.json'
    if config_path.exists() and json.loads(config_path.read_text(encoding='utf-8'))!=spec:
        raise ValueError('Feature configuration/code/runtime changed; use extract --rebuild to replace safely')
    write_json(config_path,spec)
    report=validate(args)
    created=now()
    # Audit includes manifest decisions, hashes and all failed entries.
    input_digest=b400.digest_json(report)
    run_id=b400.digest_json(dict(feature_set=spec['id'],inputs=input_digest))
    records=report['records']
    vectors=[]
    validities=[]
    for i,row in enumerate(records):
        row['feature_status']='failed'
        if row['validation_status']=='success':
            try:
                rgb,mask,sh,mh=inputs.load_pair(root/row['source_path'],root/row['mask_path'])
                if sh!=row['source_sha256'] or mh!=row['mask_sha256']:
                    raise ValueError('Input changed after preflight')
                vector,valid,quality=b400.extract(rgb,mask)
                row.update(feature_status='success',quality=quality)
                vectors.append(vector)
                validities.append(valid)
            except Exception as exc:
                row['error']=f'{type(exc).__name__}: {exc}'
        if (i+1)%25==0 or i+1==len(records):
            print(f'{i+1}/{len(records)} success={len(vectors)} elapsed={time.monotonic()-start:.1f}s',flush=True)
    raw=np.stack(vectors) if vectors else np.empty((0,400),dtype='<f4')
    validity=np.stack(validities) if validities else np.empty((0,400),dtype=bool)
    normalizer=b400.fit_normalizer(raw,validity,input_digest) if len(raw) else None
    normalized=b400.transform(raw,validity,normalizer) if normalizer else raw.copy()
    success=[r for r in records if r['feature_status']=='success']
    failures=[r for r in records if r['feature_status']!='success']
    # A second read-only audit proves the exact source set and content stayed unchanged.
    final_audit=inputs.audit(root,args.input_dir,args.segmentation_dir,args.inventory_csv)
    if b400.digest_json(final_audit)!=input_digest:
        write_json(output/'input_changed.json',final_audit)
        raise ValueError('Inputs changed during extraction; results not published to database')
    run=dict(id=run_id,feature_set_id=spec['id'],input_digest=input_digest,created_at=created,completed_at=now(),
             status='complete' if success and not failures and not report['issues'] else ('partial' if success else 'failed'),
             audit={k:v for k,v in report.items() if k!='records'})
    db=storage.connect(output/'features.sqlite3')
    try:
        storage.save(db,spec,run,records,raw,normalized,validity,normalizer)
    finally:
        db.close()
    names=np.array([r['filename'] for r in success],dtype=str)
    np.savez_compressed(output/'vectors.npz',filenames=names,raw=raw,normalized=normalized,validity=validity,
        feature_names=np.array(b400.feature_names()),source_sha256=np.array([r['source_sha256'] for r in success],dtype=str),
        mask_sha256=np.array([r['mask_sha256'] for r in success],dtype=str),run_id=np.array(run_id),
        feature_set_id=np.array(spec['id']),normalizer_id=np.array(normalizer['id'] if normalizer else ''))
    write_json(output/'normalizer.json',normalizer)
    write_json(output/'extraction_records.json',records)
    csv_rows=[{k:r.get(k,'') for k in ['filename','label','source_path','mask_path','source_sha256','mask_sha256',
        'validation_status','feature_status','error']}|dict(valid_dimensions=r.get('quality',{}).get('valid_dimensions',''),
        convention_count=len(r.get('quality',{}).get('conventions',[]))) for r in records]
    fields=list(csv_rows[0]) if csv_rows else ['filename','feature_status','error']
    write_csv(output/'status.csv',fields,csv_rows)
    conventions=Counter(c['reason'] for r in success for c in r['quality']['conventions'])
    summary=dict(run_id=run_id,feature_set_id=spec['id'],normalizer_id=normalizer['id'] if normalizer else None,
        input_images=report['image_files'],manifest_rows=report['manifest_rows'],mask_png_files=report['mask_png_files'],
        validation_success=report['success'],validation_failed=report['failed'],vector_success=len(success),
        vector_failed=len(failures),dimensions=400,dtype='<f4',finite_raw=bool(np.isfinite(raw).all()),
        finite_normalized=bool(np.isfinite(normalized).all()),
        images_with_conventions=sum(bool(r['quality']['conventions']) for r in success),
        images_all_measurements_valid=sum(not r['quality']['conventions'] for r in success),
        convention_reason_counts=dict(conventions),invalid_dimensions=int((~validity).sum()),
        source_suspicious_flags=sum(r['source_flags'].get('suspicious')=='yes' for r in records),
        failures=failures,input_issues=report['issues'],elapsed_seconds=round(time.monotonic()-start,3),
        created_at_utc=created,completed_at_utc=now(),machine=platform.machine(),database='features.sqlite3',status=run['status'])
    write_json(output/'summary.json',summary)
    verification=verify(args,write_report=True)
    print(json.dumps(dict(summary=summary,verification=verification),ensure_ascii=False,indent=2))
    return 0 if run['status']=='complete' else 1


def rebuild(args):
    output=args.output_dir
    # Extraction/verification close their DB and NPZ handles before publication.
    # macOS/Linux swap atomically; Windows uses a sibling backup and rollback.
    with tempfile.TemporaryDirectory(prefix=f'.{output.name}-build-',dir=output.parent) as temporary:
        stage=Path(temporary)/'result'
        stage.mkdir()
        staged=argparse.Namespace(**vars(args))
        staged.output_dir=stage
        code=extract_all(staged)
        if code:
            return code
        verify(staged)
        exchange_directories(stage,output)
    return 0


def verify(args, write_report=False):
    output,root=args.output_dir.resolve(),args.project_root.resolve()
    summary=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    spec=json.loads((output/'feature_set.json').read_text(encoding='utf-8'))
    compatibility = check_feature_set(spec)
    audit=inputs.audit(root,args.input_dir,args.segmentation_dir,args.inventory_csv)
    saved_audit=json.loads((output/'input_validation.json').read_text(encoding='utf-8'))
    if audit!=saved_audit:
        raise ValueError('Source/mask/manifest/inventory changed after preflight')
    records=json.loads((output/'extraction_records.json').read_text(encoding='utf-8'))
    expected=[r for r in records if r['feature_status']=='success']
    db=storage.connect(output/'features.sqlite3',readonly=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite integrity/foreign key check failed')
        run=db.execute('SELECT * FROM runs WHERE id=?',(summary['run_id'],)).fetchone()
        if not run or run['input_digest']!=b400.digest_json(audit) or run['feature_set_id']!=spec['id']:
            raise ValueError('Run identity differs from source audit')
        stored_spec=db.execute('SELECT config_json FROM feature_sets WHERE id=?',(spec['id'],)).fetchone()
        if json.loads(stored_spec[0])!=spec:
            raise ValueError('SQLite feature set differs')
        statuses=[dict(r) for r in db.execute('SELECT * FROM extraction_status WHERE run_id=? ORDER BY filename',(summary['run_id'],))]
        if [r['filename'] for r in statuses]!=[r['filename'] for r in records]:
            raise ValueError('SQLite status filenames differ')
        for status,row in zip(statuses,records):
            if status['status']!=row['feature_status'] or json.loads(status['metadata_json'])!=row or status['error']!=row['error']:
                raise ValueError(f'SQLite metadata differs: {row["filename"]}')
        count=db.execute('SELECT count(*) FROM vectors WHERE run_id=?',(summary['run_id'],)).fetchone()[0]
        if count!=len(expected) or count!=summary['vector_success'] or len(records)-count!=summary['vector_failed']:
            raise ValueError('SQLite vector/status counts differ')
        params=json.loads((output/'normalizer.json').read_text(encoding='utf-8'))
        if params:
            db_params=db.execute('SELECT params_json FROM normalizers WHERE id=?',(params['id'],)).fetchone()
            if not db_params or json.loads(db_params[0])!=params or run['normalizer_id']!=params['id']:
                raise ValueError('SQLite normalizer differs')
        with np.load(output/'vectors.npz',allow_pickle=False) as arrays:
            for key in ['raw','normalized','validity']:
                if arrays[key].shape!=(len(expected),400):
                    raise ValueError(f'NPZ dimensions differ: {key}')
            if arrays['filenames'].tolist()!=[r['filename'] for r in expected] or arrays['feature_names'].tolist()!=b400.feature_names():
                raise ValueError('NPZ names/order differ')
            if str(arrays['run_id'])!=summary['run_id'] or str(arrays['feature_set_id'])!=spec['id']:
                raise ValueError('NPZ version differs')
            if str(arrays['normalizer_id'])!=(params['id'] if params else ''):
                raise ValueError('NPZ normalizer differs')
            if params:
                from tools.search.index import check_normalizer
                check_normalizer(params,run)
                if params['fit_rows']!=len(expected) or params['valid_counts']!=arrays['validity'].sum(axis=0).tolist():
                    raise ValueError('Scaler fit row/validity counts differ')
            if len(expected) and not np.isin(arrays['raw'][:,160:208],[0,1]).all():
                raise ValueError('Raw S3 must contain only binary bits')
            if params and not np.array_equal(b400.transform(arrays['raw'],arrays['validity'],params),arrays['normalized']):
                raise ValueError('Frozen normalization not reproducible')
            for i,row in enumerate(expected):
                stored=storage.read_vector(db,summary['run_id'],row['filename'])
                if stored['feature_set_id']!=spec['id'] or stored['normalizer_id']!=params['id']:
                    raise ValueError('SQLite vector configuration/scaler differs')
                for key in ['raw','normalized','validity']:
                    if not np.array_equal(stored[key],arrays[key][i]):
                        raise ValueError(f'SQLite/NPZ {key} differs: {row["filename"]}')
                for key in ['source_sha256','mask_sha256']:
                    if stored[key]!=row[key] or arrays[key][i]!=row[key]:
                        raise ValueError(f'Source identity differs: {row["filename"]}')
                if stored['path']!=row['source_path']:
                    raise ValueError('SQLite source path differs')
            if len(expected) and (not np.isfinite(arrays['raw']).all() or not np.isfinite(arrays['normalized']).all()
                                or not np.allclose(np.linalg.norm(arrays['normalized'],axis=1),1,atol=1e-6)):
                raise ValueError('Invalid finite values or normalization norms')
        result=dict(verified=True,run_id=summary['run_id'],sqlite_vectors_checked=count,
            source_hashes_checked=audit['success'],mask_hashes_checked=audit['success'],
            input_validation_failed=audit['failed'],sqlite_integrity='ok',sqlite_foreign_keys='ok',
            frozen_normalization_reproduced=True,source_audit_unchanged=True,checked_at_utc=now())
        result.update(scaler_checksum_verified=True,raw_s3_binary=True,compatibility=compatibility)
    finally:
        db.close()
    if write_report:
        write_json(output/'verification.json',result)
    return result


def main(argv=None):
    configure_console()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','extract','verify','init','status','get'])
    parser.add_argument('--project-root',type=Path,default=PROJECT_ROOT)
    parser.add_argument('--input-dir',type=Path,default=CROPPED_IMAGES_DIR)
    parser.add_argument('--segmentation-dir',type=Path,default=GRABCUT_OUTPUT_DIR)
    parser.add_argument('--inventory-csv',type=Path,default=INVENTORY_DIR/'image_processing.csv')
    parser.add_argument('--output-dir',type=Path,default=B400_OUTPUT_DIR)
    parser.add_argument('--filename')
    parser.add_argument('--run-id')
    parser.add_argument('--rebuild',action='store_true',help='Build and verify staging, then replace output (Windows: two renames with rollback)')
    args=parser.parse_args(argv)
    try:
        cv2.setNumThreads(1)
        if args.rebuild and args.command!='extract':
            raise ValueError('--rebuild requires extract')
        if args.command in {'status','get'}:
            with file_lock(args.output_dir.parent/f'.{args.output_dir.name}.lock'):
                recover_output(args.output_dir)
                return inspect_database(args)
        args.project_root,args.output_dir=prepare_output(args)
        with file_lock(args.output_dir.parent/f'.{args.output_dir.name}.lock'):
            recover_output(args.output_dir)
            args.output_dir.mkdir(exist_ok=True)
            if args.command=='extract':
                return rebuild(args) if args.rebuild else extract_all(args)
            if args.command=='init':
                storage.connect(args.output_dir/'features.sqlite3').close()
                result={'initialized':True}
            elif args.command=='validate':
                report=validate(args)
                print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))
                return int(bool(report['failed'] or report['issues'] or not report['image_files']))
            else:
                result=verify(args)
            print(json.dumps(result,indent=2))
            return 0
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as exc:
        print(f'B400 error: {exc}',file=sys.stderr)
        return 2


def inspect_database(args):
    db=storage.connect(args.output_dir/'features.sqlite3',readonly=True)
    try:
        if args.command=='status':
            value=storage.status(db)
        else:
            if not args.filename or not args.run_id:
                raise ValueError('get requires --filename and --run-id (explicit version)')
            value=storage.read_vector(db,args.run_id,args.filename)
            value={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in value.items()}
    finally:
        db.close()
    print(json.dumps(value,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    sys.exit(main())
