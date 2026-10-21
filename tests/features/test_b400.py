import contextlib
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

from tools.features import b400, cli, inputs, storage


class DescriptorTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        self.rgb=np.zeros((384,576,3),np.uint8)
        self.mask=np.zeros((384,576),np.uint8)
        self.mask[80:300,80:500]=255
        self.rgb[self.mask>0]=[255,0,0]

    def test_dimensions_and_order(self):
        names=b400.feature_names()
        self.assertEqual(len(names),400)
        self.assertEqual(len(set(names)),400)
        for block,start,stop in b400.BLOCKS:
            self.assertTrue(all(n.startswith(block+'_') for n in names[start:stop]))
        self.assertEqual([(s,e) for _,s,e in b400.GROUPS],[(0,48),(48,148),(148,272),(272,400)])
        raw,valid,q=b400.extract(self.rgb,self.mask)
        self.assertEqual(raw.shape,(400,))
        self.assertEqual(raw.dtype,np.dtype('<f4'))
        self.assertTrue(np.isfinite(raw).all())
        self.assertEqual(valid.shape,(400,))
        self.assertEqual(q['gabor_support'].__len__(),24)

    def test_foreground_red_histogram_and_undefined_correlation(self):
        raw,valid,q=b400.extract(self.rgb,self.mask)
        np.testing.assert_allclose(raw[:16],np.array([.5,.25]+[0.]*13+[.25]))
        self.assertEqual(raw[23],1)  # last S bin
        self.assertEqual(raw[31],1)  # last V bin
        for k in range(68,100,4):
            np.testing.assert_allclose(raw[k:k+4],[1,0,1,0])
            self.assertFalse(valid[k+3])
        self.assertIn('undefined_glcm_correlation',{x['reason'] for x in q['conventions']})

    def test_background_cannot_change_any_measurement(self):
        rng=np.random.default_rng(81)
        self.mask[100:115,160:180]=0
        self.rgb[self.mask>0]=rng.integers(0,256,(np.count_nonzero(self.mask),3),dtype=np.uint8)
        other=self.rgb.copy()
        other[self.mask==0]=rng.integers(0,256,(np.count_nonzero(self.mask==0),3),dtype=np.uint8)
        a,av,aq=b400.extract(self.rgb,self.mask)
        b,bv,bq=b400.extract(other,self.mask)
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(av,bv)
        self.assertEqual(aq,bq)

    def test_lbp_uniform_and_exact_support(self):
        gray=np.full((9,9),80,np.uint8)
        mask=np.ones((9,9),bool)
        hist,n=b400.lbp_histogram(gray,mask,1)
        self.assertEqual(n,49)
        self.assertEqual(hist[8],1)
        hist,n=b400.lbp_histogram(gray,mask,3)
        self.assertEqual(n,9)
        mask[:]=False
        mask[4,4]=True
        hist,n=b400.lbp_histogram(gray,mask,1)
        self.assertEqual(n,0)
        self.assertEqual(hist.sum(),0)

    def test_glcm_pair_count_and_known_properties(self):
        gray=np.array([[0,4],[0,4]],np.uint8)
        mask=np.ones((2,2),bool)
        props,valid,n=b400.glcm_properties(gray,mask,1,0)
        np.testing.assert_allclose(props,[np.sqrt(.5),1,.5,-1])
        self.assertEqual(n,2)
        self.assertTrue(all(valid))
        mask[:,1]=False
        props,valid,n=b400.glcm_properties(gray,mask,1,0)
        self.assertEqual(n,0)
        self.assertFalse(any(valid))
        self.assertEqual(props.sum(),0)

    def test_gabor_constant_and_directional_response(self):
        k=b400.gabor_kernel(.16,0,1)
        gray=np.ones((100,100),float)*.3
        real=cv2.filter2D(gray,cv2.CV_64F,k.real)
        imag=cv2.filter2D(gray,cv2.CV_64F,k.imag)
        self.assertAlmostEqual(float(np.hypot(real[50,50],imag[50,50])),abs(k.sum())*.3,places=12)
        y,x=np.indices((100,100))
        stripes=.5+.4*np.cos(2*np.pi*.16*x)
        def amplitude(angle):
            kk=b400.gabor_kernel(.16,angle,1)
            re=cv2.filter2D(stripes,cv2.CV_64F,kk.real)
            im=cv2.filter2D(stripes,cv2.CV_64F,kk.imag)
            return np.hypot(re[30:70,30:70],im[30:70,30:70]).mean()
        self.assertGreater(amplitude(0),amplitude(90)*5)

    def test_geometry_preserves_disconnected_parts_and_holes(self):
        self.mask[80:300,80:500]=0
        self.mask[80:250,80:250]=255
        self.mask[100:120,100:120]=0
        self.mask[200:270,400:450]=255
        canvas,m,q=b400.prepare(self.rgb,self.mask)
        self.assertEqual(cv2.connectedComponents(m.astype(np.uint8))[0]-1,2)
        self.assertEqual(q['source_bbox'],[80,80,370,190])
        self.assertLessEqual(abs(q['resized'][0]/q['resized'][1]-370/190),.02)
        raw,valid,quality=b400.extract(self.rgb,self.mask)
        self.assertEqual(quality['component_count'],2)
        self.assertEqual(raw[155],np.float32(370/190))
        self.assertTrue(0<raw[157]<=1)
        self.assertIn('empty_profile_strip',{x['reason'] for x in quality['conventions']})

    def test_rectangle_geometry_has_analytical_values(self):
        raw,valid,q=b400.extract(self.rgb,self.mask)
        width,height=q['resized']
        np.testing.assert_allclose(raw[155:159],[420/220,1,1,
            4*np.pi*width*height/(2*(width+height))**2],rtol=1e-6)
        self.assertTrue(valid[155:160].all())

    def test_thin_foreground_records_missing_texture_support(self):
        self.mask[:]=0
        self.mask[20:360,250:252]=255
        raw,valid,q=b400.extract(self.rgb,self.mask)
        self.assertIn('no_gabor_support',{c['reason'] for c in q['conventions']})
        self.assertFalse(valid[100:148].all())
        self.assertTrue(np.isfinite(raw).all())

    def test_invalid_masks_fail_without_vector(self):
        cases=[np.zeros_like(self.mask),np.full_like(self.mask,255),self.mask[:100],self.mask.astype(float)]
        bad=self.mask.copy(); bad[20,20]=1; cases.append(bad)
        for mask in cases:
            with self.subTest(shape=mask.shape,dtype=mask.dtype):
                with self.assertRaises(ValueError):
                    b400.extract(self.rgb,mask)

    def test_missing_and_achromatic_histograms_have_metadata(self):
        self.rgb[:]=128
        self.mask[:]=0
        self.mask[100:250,250:300]=255
        raw,valid,q=b400.extract(self.rgb,self.mask)
        self.assertEqual(raw[:16].sum(),0)
        self.assertFalse(valid[:16].any())
        self.assertIn('empty_cell',{c['reason'] for c in q['conventions']})
        self.assertIn('zero_hue_saturation',{c['reason'] for c in q['conventions']})

    def test_normalization_valid_only_fit_reusable_and_balanced(self):
        rng=np.random.default_rng(4)
        raw=rng.uniform(0,1,(4,400)).astype('<f4')
        valid=np.ones(raw.shape,bool)
        raw[0,68]=10000
        valid[0,68]=False
        params=b400.fit_normalizer(raw,valid,'test-inputs')
        self.assertAlmostEqual(params['mean'][68],float(raw[1:,68].astype(float).mean()))
        result=b400.transform(raw,valid,params)
        np.testing.assert_allclose(np.linalg.norm(result,axis=1),1,atol=1e-6)
        for _,s,e in b400.GROUPS:
            np.testing.assert_allclose(np.linalg.norm(result[:,s:e],axis=1),.5,atol=1e-6)
        self.assertEqual(result[0,68],0)
        np.testing.assert_array_equal(result[0],b400.transform(raw[0],valid[0],json.loads(json.dumps(params))))
        params['mean'][68]+=1
        with self.assertRaisesRegex(ValueError,'checksum'):
            b400.transform(raw,valid,params)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.source=self.root/'data'/'images'
        self.seg=self.root/'segmentation'
        self.inventory=self.root/'inventory.csv'
        self.out=self.root/'features'
        self.source.mkdir(parents=True)
        (self.seg/'masks').mkdir(parents=True)
        (self.seg/'overlays').mkdir()
        self.name='animal_0001.jpg'
        Image.new('RGB',(576,384),(190,120,80)).save(self.source/self.name)
        mask=np.zeros((384,576),np.uint8); mask[60:320,80:500]=255
        Image.fromarray(mask).save(self.seg/'masks'/(self.name+'.png'))
        Image.new('RGB',(576,384),'red').save(self.seg/'overlays'/(self.name+'.png'))
        self.entry=dict(filename=self.name,source_sha256=inputs.sha256(self.source/self.name),
            mask_path='masks/'+self.name+'.png',overlay_path='overlays/'+self.name+'.png',
            source_width=576,source_height=384,width=576,height=384,total_pixels=576*384,
            mask_pixels=int((mask>0).sum()),mask_ratio=float((mask>0).mean()),
            mask_sha256=inputs.sha256(self.seg/'masks'/(self.name+'.png')),
            status='success',review_status='da_duyet',review_result='dat',suspicious='yes',review_flags='historical_flag')
        self.write_manifest([self.entry])
        with self.inventory.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['filename','is_image_candidate','sha256'])
            w.writeheader();w.writerow(dict(filename=self.name,is_image_candidate=1,sha256=self.entry['source_sha256']))

    def write_manifest(self,rows):
        with (self.seg/'manifest.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.entry));w.writeheader();w.writerows(rows)

    def audit(self):
        return inputs.audit(self.root,self.source,self.seg,self.inventory)

    def command(self,command,*extra):
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.main([command,'--project-root',str(self.root),'--input-dir',str(self.source),
                '--segmentation-dir',str(self.seg),'--inventory-csv',str(self.inventory),
                '--output-dir',str(self.out),*extra])

    def test_preflight_inherits_review_flags_and_is_read_only(self):
        paths=list(self.source.rglob('*'))+list(self.seg.rglob('*'))+[self.inventory]
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths if p.is_file()}
        report=self.audit()
        self.assertEqual(report['success'],1)
        self.assertEqual(report['records'][0]['source_flags']['suspicious'],'yes')
        self.assertEqual(report['records'][0]['review_result'],'dat')
        after={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths if p.is_file()}
        self.assertEqual(before,after)

    def test_preflight_hash_mismatch_is_named(self):
        Image.new('RGB',(576,384),'blue').save(self.source/self.name)
        report=self.audit()
        self.assertEqual(report['failed'],1)
        self.assertEqual(report['records'][0]['filename'],self.name)
        self.assertIn('SHA-256',report['records'][0]['error'])

    def test_preflight_mismatch_binary_duplicates_and_unsafe_paths(self):
        for value in ['../escape.png','/absolute.png']:
            self.entry['mask_path']=value; self.write_manifest([self.entry])
            self.assertIn('Unsafe',self.audit()['records'][0]['error'])
        self.entry['mask_path']='masks/'+self.name+'.png'
        self.write_manifest([self.entry,self.entry])
        self.assertIn('found 2',self.audit()['records'][0]['error'])
        self.write_manifest([self.entry])
        for mask in [np.zeros((10,10),np.uint8),np.full((384,576),80,np.uint8)]:
            Image.fromarray(mask).save(self.seg/'masks'/(self.name+'.png'))
            report=self.audit()
            self.assertEqual(report['failed'],1)
            self.assertRegex(report['records'][0]['error'],'dimensions|binary')

    def test_missing_source_mask_and_unreferenced_mask(self):
        (self.source/self.name).unlink()
        report=self.audit()
        self.assertIn('Missing source',report['records'][0]['error'])
        Image.new('L',(576,384),0).save(self.seg/'masks'/'orphan.png')
        self.assertIn('Unreferenced mask: masks/orphan.png',self.audit()['issues'])

    def test_sqlite_roundtrip_idempotency_verify_and_constraints(self):
        self.assertEqual(self.command('extract'),0)
        first=json.loads((self.out/'summary.json').read_text())
        self.assertEqual(self.command('extract'),0)
        second=json.loads((self.out/'summary.json').read_text())
        self.assertEqual(first['run_id'],second['run_id'])
        db=storage.connect(self.out/'features.sqlite3')
        self.addCleanup(db.close)
        for table in ['images','masks','runs','vectors','normalizers','feature_sets','extraction_status']:
            self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],1)
        row=storage.read_vector(db,second['run_id'],self.name)
        self.assertEqual(row['raw'].shape,(400,))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute('UPDATE vectors SET raw=?',(b'bad',))
        db.rollback()
        self.assertEqual(self.command('verify'),0)
        self.assertEqual(self.command('get','--filename',self.name,'--run-id',second['run_id']),0)
        self.assertEqual(self.command('status'),0)
        db.execute("UPDATE images SET sha256=?",('a'*64,));db.commit()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.command('verify'),2)

    def test_updated_masks_create_isolated_run_without_duplicate_images(self):
        self.assertEqual(self.command('extract'),0)
        first=json.loads((self.out/'summary.json').read_text())
        mask_path=self.seg/self.entry['mask_path']
        mask=np.array(Image.open(mask_path))
        mask[100:140,140:190]=0
        Image.fromarray(mask).save(mask_path)
        self.entry.update(mask_sha256=inputs.sha256(mask_path),mask_pixels=int((mask>0).sum()),
                          mask_ratio=float((mask>0).mean()))
        self.write_manifest([self.entry])
        self.assertEqual(self.command('extract'),0)
        second=json.loads((self.out/'summary.json').read_text())
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertNotEqual(first['normalizer_id'],second['normalizer_id'])
        db=storage.connect(self.out/'features.sqlite3')
        self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT count(*) FROM images').fetchone()[0],1)
        for table in ['masks','runs','vectors','normalizers']:
            self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],2)
        a=storage.read_vector(db,first['run_id'],self.name)
        b=storage.read_vector(db,second['run_id'],self.name)
        self.assertNotEqual(a['mask_sha256'],b['mask_sha256'])
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute('UPDATE vectors SET normalizer_id=? WHERE run_id=?',
                       (first['normalizer_id'],second['run_id']))
        db.rollback()
        self.assertEqual(self.command('verify'),0)

    def test_failed_input_is_stored_without_vector(self):
        (self.source/self.name).write_bytes(b'bad')
        self.assertEqual(self.command('extract'),1)
        summary=json.loads((self.out/'summary.json').read_text())
        self.assertEqual(summary['vector_failed'],1)
        db=storage.connect(self.out/'features.sqlite3',readonly=True)
        self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT count(*) FROM vectors').fetchone()[0],0)
        row=db.execute('SELECT * FROM extraction_status').fetchone()
        self.assertEqual(row['status'],'failed')
        self.assertTrue(row['error'])

    def test_changed_configuration_and_source_are_rejected(self):
        self.assertEqual(self.command('extract'),0)
        Image.new('RGB',(576,384),'blue').save(self.source/self.name)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.command('verify'),2)
        spec=json.loads((self.out/'feature_set.json').read_text());spec['id']='other'
        (self.out/'feature_set.json').write_text(json.dumps(spec))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.command('extract'),2)

    def test_output_overlap_is_rejected_before_writing(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.command('validate','--output-dir',str(self.source/'out')),2)
        self.assertFalse((self.source/'out').exists())


if __name__=='__main__':
    unittest.main()
