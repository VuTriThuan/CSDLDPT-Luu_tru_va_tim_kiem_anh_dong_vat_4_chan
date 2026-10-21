"""B400 v1: CPU foreground descriptors; no labels, filenames or source writes."""
from functools import lru_cache
import hashlib
import json
import math

import cv2
import numpy as np

BLOCKS = [('C1', 0, 32), ('C2', 32, 48), ('T1', 48, 68),
          ('T2', 68, 100), ('T3', 100, 148), ('S1', 148, 155),
          ('S2', 155, 160), ('S3', 160, 208), ('S4', 208, 272), ('P', 272, 400)]
GROUPS = [('color', 0, 48), ('texture', 48, 148), ('shape', 148, 272), ('layout', 272, 400)]
SUBBLOCKS = [[(0, 32), (32, 48)], [(48, 68), (68, 100), (100, 148)],
             [(148, 155), (155, 160), (160, 208), (208, 272)],
             [(272 + 16*i, 288 + 16*i) for i in range(8)]]
HISTOGRAM_INDICES = list(range(68)) + list(range(272, 400))
CONTINUOUS_INDICES = list(range(68, 272))


def feature_names():
    names = [f'C1_hsv_{c}_{i:02}' for c, n in [('h', 16), ('s', 8), ('v', 8)] for i in range(n)]
    names += [f'C2_lab_{c}_{i:02}' for c in ['a', 'b'] for i in range(8)]
    names += [f'T1_lbp_r{r}_{i:02}' for r in [1, 3] for i in range(10)]
    names += [f'T2_glcm_d{d}_a{a}_{stat}' for d in [1, 3] for a in [0, 45, 90, 135]
              for stat in ['energy', 'contrast', 'homogeneity', 'correlation']]
    names += [f'T3_gabor_f{f:.2f}_a{a}_bw{b}_{stat}' for f in [.08, .16, .24]
              for a in [0, 45, 90, 135] for b in [1, 2] for stat in ['mean', 'std']]
    names += [f'S1_hu_{i}' for i in range(7)]
    names += [f'S2_{s}' for s in ['aspect', 'extent', 'solidity', 'circularity', 'eccentricity']]
    names += [f'S3_mask_r{r}_c{c}' for r in range(6) for c in range(8)]
    names += [f'S4_{side}_{i:02}' for side in ['upper', 'lower'] for i in range(32)]
    names += [f'P_r{r}_c{c}_{ch}_{i:02}' for r in range(2) for c in range(4)
              for ch, n in [('h', 8), ('s', 4), ('v', 4)] for i in range(n)]
    return names


def configuration():
    return dict(name='b400_v1', dimensions=400, dtype='<f4', blocks=[dict(name=n, start=s, stop=e, version=1)
        for n, s, e in BLOCKS], feature_names=feature_names(), canvas=[288, 192],
        resize='bbox all components; uniform scale min(288/w,192/h), round sizes; centered; nearest mask; '
               'RGB masked normalized INTER_LINEAR, uint8 round; nearest RGB fallback if alpha0; no background interpolation',
        color='OpenCV uint8 HSV/Lab; channel L1; hue weighted S/255 and circular smoothing [1,2,1]/4; '
              'H [0,180), S/V/a/b [0,256)',
        lbp='P8 uniform rotation invariant; R1,R3; bilinear circular samples, neighbor>=center; '
            'all contributing interpolation pixels in foreground; <=2 transitions maps to popcount, else bin9',
        glcm='gray_uint8//4; d1,3; angles0,45,90,135; dy=round(d*sin),dx=round(d*cos); '
             'both endpoints in mask; symmetric L1; energy=sqrt(ASM); contrast=sum(p*(i-j)^2); '
             'homogeneity=sum(p/(1+(i-j)^2)); correlation variance<=1e-15 is undefined',
        gabor=dict(frequencies=[.08,.16,.24], angles=[0,45,90,135], bandwidths=[1,2], n_stds=2,
            sigma='sqrt(log(2)/2)/pi*(2**bw+1)/(2**bw-1)/frequency; sigma_x=sigma_y',
            kernel='complex Gaussian exp(-r²/(2sigma²)+2pi*i*f*x_rot)/(2pi*sigma²); '
                   'rotated bounding rectangle at n_stds=2; no DC subtraction',
            measurement='gray/255; full rectangular support must be foreground; magnitude mean/population std',
            order='frequency,angle,bandwidth,stat',
            design_resolution='12 filters x 2 statistics was 24, not 48; two fixed bandwidths resolve design ambiguity'),
        shape='Hu binary canvas all components, signed log floor1e-12, zero->zero; aspect original bbox; '
              'remaining geometry canvas; A=pixel count; hull=raster filled convex hull of all pixel centers; '
              'P=exposed pixel edges including holes; eccentricity covariance pixel centers ddof0; '
              'mask grid row-major6x8; profiles32 x-strips upper=min_y/H,lower=(max_y+1)/H',
        missing='empty histogram/texture support/profile or undefined denominator -> raw0, validity=false, '
                'explicit reason outside vector; valid observations alone fit scaler; transformed missing=0; '
                'empty/full source mask, shape mismatch, nonbinary or nonfinite -> fail without vector',
        direction='stored input orientation; requirement4 must compare original and horizontal flip queries '
                  'through same frozen pipeline, min distance for every label; retrieval not implemented',
        normalization=dict(version=1, histogram='sqrt per-channel L1 (already L1 in raw)',
            continuous='per-coordinate population zscore using valid development observations; std<=1e-12 ->1; no clipping',
            subblocks=SUBBLOCKS, groups=GROUPS, weights=[.25]*4,
            concatenate='each subblock L2, concatenate subblocks then group L2; '
                        'each group times sqrt(weight); final L2; zero norms remain zero',
            fit_scope='all successful current images as development corpus, no labels; not a held-out evaluation'))


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_arrays(rgb, mask):
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('RGB must be HxWx3 uint8')
    if mask.ndim != 2 or mask.shape != rgb.shape[:2]:
        raise ValueError('Image-mask dimensions mismatch')
    if mask.dtype != np.uint8 or not np.isin(mask, [0, 255]).all():
        raise ValueError('Mask must be binary uint8 0/255')
    if not mask.any() or (mask == 255).all():
        raise ValueError('Empty or full-frame foreground mask')


def prepare(rgb, mask):
    validate_arrays(rgb, mask)
    ys, xs = np.nonzero(mask)
    x, y, w, h = int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)
    crop = rgb[y:y+h, x:x+w].astype(np.float64)
    m = (mask[y:y+h, x:x+w] != 0).astype(np.float64)
    scale = min(288/w, 192/h)
    nw, nh = max(1, round(w*scale)), max(1, round(h*scale))
    alpha = cv2.resize(m, (nw, nh), interpolation=cv2.INTER_LINEAR)
    numerator = cv2.resize(crop*m[..., None], (nw, nh), interpolation=cv2.INTER_LINEAR)
    resized = np.divide(numerator, alpha[..., None], out=np.zeros_like(numerator), where=alpha[..., None] > 0)
    cm = cv2.resize(m.astype(np.uint8), (nw, nh), interpolation=cv2.INTER_NEAREST).astype(bool)
    # Nearest mask and linear RGB may sample different positions during reduction.
    fallback = cm & (alpha <= 0)
    if fallback.any():
        nearest_rgb = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_NEAREST)
        resized[fallback] = nearest_rgb[fallback]
    canvas = np.zeros((192, 288, 3), np.uint8)
    foreground = np.zeros((192, 288), bool)
    ox, oy = (288-nw)//2, (192-nh)//2
    canvas[oy:oy+nh, ox:ox+nw] = np.clip(np.rint(resized), 0, 255).astype(np.uint8)
    foreground[oy:oy+nh, ox:ox+nw] = cm
    canvas[~foreground] = 0
    if not foreground.any():
        raise ValueError('Foreground vanished on canvas')
    return canvas, foreground, dict(source_bbox=[x,y,w,h], scale=scale, resized=[nw,nh], offset=[ox,oy],
        nearest_rgb_fallback_pixels=int(fallback.sum()),
        source_component_count=int(cv2.connectedComponents((mask>0).astype(np.uint8))[0]-1))


def histogram(values, bins, upper, weights=None, circular=False):
    counts = np.histogram(values, bins=bins, range=(0,upper), weights=weights)[0].astype(float)
    if circular:
        counts = (np.roll(counts, 1) + 2*counts + np.roll(counts, -1))/4
    total = counts.sum()
    return counts/total if total else counts, bool(total)


def lbp_histogram(gray, mask, radius):
    """Require every nonzero bilinear weight to read a foreground source pixel."""
    h, w = gray.shape
    yy, xx = np.indices((h,w))
    valid = mask.copy()
    bits = []
    for p in range(8):
        dx = round(radius*math.cos(2*math.pi*p/8), 12)
        dy = round(-radius*math.sin(2*math.pi*p/8), 12)
        ix, iy = math.floor(dx), math.floor(dy)
        fx, fy = dx-ix, dy-iy
        sample = np.zeros_like(gray, dtype=float)
        for sx, sy, weight in [(ix,iy,(1-fx)*(1-fy)), (ix+1,iy,fx*(1-fy)),
                               (ix,iy+1,(1-fx)*fy), (ix+1,iy+1,fx*fy)]:
            if weight <= 1e-12:
                continue
            tx, ty = xx+sx, yy+sy
            inside = (tx>=0)&(tx<w)&(ty>=0)&(ty<h)
            cx, cy = np.clip(tx,0,w-1), np.clip(ty,0,h-1)
            valid &= inside & mask[cy,cx]
            sample += weight*gray[cy,cx]
        bits.append(sample >= gray - 1e-9)
    bits = np.stack(bits)
    transitions = np.count_nonzero(bits != np.roll(bits,1,axis=0), axis=0)
    codes = np.where(transitions<=2, bits.sum(axis=0), 9)
    counts = np.bincount(codes[valid], minlength=10).astype(float)
    n = int(valid.sum())
    return counts/n if n else counts, n


def glcm_properties(gray, mask, distance, angle):
    dx = round(distance*math.cos(math.radians(angle)))
    dy = round(distance*math.sin(math.radians(angle)))
    h,w = gray.shape
    a = (slice(max(0,-dy), min(h,h-dy)), slice(max(0,-dx), min(w,w-dx)))
    b = (slice(max(0,dy), min(h,h+dy)), slice(max(0,dx), min(w,w+dx)))
    valid = mask[a] & mask[b]
    n = int(valid.sum())
    if not n:
        return np.zeros(4), [False]*4, n
    q = gray.astype(np.int64)//4
    pairs = q[a][valid]*64+q[b][valid]
    matrix = np.bincount(pairs, minlength=4096).reshape(64,64).astype(float)
    matrix += matrix.T.copy()
    matrix /= matrix.sum()
    i,j = np.indices((64,64))
    mu_i,mu_j = (matrix*i).sum(), (matrix*j).sum()
    vi,vj = (matrix*(i-mu_i)**2).sum(), (matrix*(j-mu_j)**2).sum()
    ok = vi > 1e-15 and vj > 1e-15
    corr = float((matrix*(i-mu_i)*(j-mu_j)).sum()/math.sqrt(vi*vj)) if ok else 0.
    return np.array([math.sqrt((matrix**2).sum()), (matrix*(i-j)**2).sum(),
                     (matrix/(1+(i-j)**2)).sum(), corr]), [True,True,True,ok], n


@lru_cache(maxsize=24)
def gabor_kernel(frequency, angle, bandwidth):
    sigma = math.sqrt(math.log(2)/2)/math.pi*(2**bandwidth+1)/(2**bandwidth-1)/frequency
    theta = math.radians(angle)
    ct,st = math.cos(theta),math.sin(theta)
    rx = math.ceil(max(abs(2*sigma*ct),abs(2*sigma*st),1))
    ry = rx  # isotropic Gaussian
    y,x = np.mgrid[-ry:ry+1, -rx:rx+1]
    rotated = x*ct+y*st
    return np.exp(-(x*x+y*y)/(2*sigma*sigma)+2j*np.pi*frequency*rotated)/(2*np.pi*sigma*sigma)


def extract(rgb, mask):
    canvas,m,quality = prepare(rgb,mask)
    hsv = cv2.cvtColor(canvas,cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(canvas,cv2.COLOR_RGB2LAB)
    gray = cv2.cvtColor(canvas,cv2.COLOR_RGB2GRAY)
    vector = np.zeros(400, dtype=float)
    valid = np.ones(400, dtype=bool)
    conventions = []

    def missing(start, stop, reason):
        valid[start:stop] = False
        conventions.append(dict(start=start, stop=stop, reason=reason))

    def hsv_block(start, hh, mm, bins):
        for ch, n in enumerate(bins):
            weights = hh[:,:,1][mm].astype(float)/255 if ch==0 else None
            hist,ok = histogram(hh[:,:,ch][mm],n,180 if ch==0 else 256,weights,ch==0)
            vector[start:start+n] = hist
            if not ok:
                missing(start,start+n,'empty_cell' if not mm.any() else 'zero_hue_saturation')
            start += n

    hsv_block(0,hsv,m,(16,8,8))
    for idx,ch in [(32,1),(40,2)]:
        vector[idx:idx+8] = histogram(lab[:,:,ch][m],8,256)[0]
    lbp_counts = []
    for i,r in enumerate([1,3]):
        hist,n = lbp_histogram(gray,m,r)
        vector[48+10*i:58+10*i] = hist
        lbp_counts.append(n)
        if not n:
            missing(48+10*i,58+10*i,'no_lbp_support')
    glcm_counts = []
    k = 68
    for d in [1,3]:
        for a in [0,45,90,135]:
            props,ok,n = glcm_properties(gray,m,d,a)
            vector[k:k+4] = props
            glcm_counts.append(n)
            for j,state in enumerate(ok):
                if not state:
                    missing(k+j,k+j+1,'undefined_glcm_correlation' if n else 'no_glcm_pairs')
            k+=4
    gabor_counts = []
    g = gray.astype(float)/255
    for f in [.08,.16,.24]:
        for a in [0,45,90,135]:
            for bw in [1,2]:
                kernel = gabor_kernel(f,a,bw)
                support = cv2.erode(m.astype(np.uint8),np.ones(kernel.shape,np.uint8),
                                    borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
                n = int(support.sum())
                gabor_counts.append(n)
                if n:
                    real = cv2.filter2D(g,cv2.CV_64F,kernel.real,borderType=cv2.BORDER_CONSTANT)
                    imag = cv2.filter2D(g,cv2.CV_64F,kernel.imag,borderType=cv2.BORDER_CONSTANT)
                    amplitude = np.hypot(real[support],imag[support])
                    vector[k:k+2] = amplitude.mean(),amplitude.std()
                else:
                    missing(k,k+2,'no_gabor_support')
                k+=2
    moments = cv2.moments(m.astype(np.uint8),binaryImage=True)
    hu = cv2.HuMoments(moments).ravel()
    vector[148:155] = -np.sign(hu)*np.log10(np.maximum(np.abs(hu),1e-12))
    ys,xs = np.nonzero(m)
    area = len(xs)
    width,height = int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)
    points = np.column_stack([xs,ys]).astype(np.int32)
    hull = cv2.convexHull(points)
    raster = np.zeros(m.shape,np.uint8)
    cv2.fillConvexPoly(raster,hull,1)
    hull_area = int(raster.sum())
    pad = np.pad(m.astype(np.int32),1)
    perimeter = np.abs(np.diff(pad,axis=0)).sum()+np.abs(np.diff(pad,axis=1)).sum()
    eig = np.linalg.eigvalsh(np.cov(points.astype(float).T,bias=True)) if area>1 else np.zeros(2)
    vector[155:160] = [quality['source_bbox'][2]/quality['source_bbox'][3],area/(width*height),
        area/hull_area if hull_area else 0,4*np.pi*area/perimeter**2 if perimeter else 0,
        math.sqrt(max(0,1-eig[0]/eig[1])) if eig[1]>1e-15 else 0]
    if not hull_area:
        missing(157,158,'zero_hull_area')
    if not perimeter:
        missing(158,159,'zero_perimeter')
    if eig[1]<=1e-15:
        missing(159,160,'undefined_eccentricity')
    vector[160:208] = [cell.mean() for band in np.array_split(m,6) for cell in np.array_split(band,8,axis=1)]
    occupancy = []
    for i,columns in enumerate(np.array_split(np.arange(288),32)):
        yy,_ = np.nonzero(m[:,columns])
        occupancy.append(int(len(yy)))
        if len(yy):
            vector[208+i],vector[240+i] = yy.min()/192,(yy.max()+1)/192
        else:
            missing(208+i,209+i,'empty_profile_strip')
            missing(240+i,241+i,'empty_profile_strip')
    k=272
    for rows in np.array_split(np.arange(192),2):
        for cols in np.array_split(np.arange(288),4):
            hsv_block(k,hsv[np.ix_(rows,cols)],m[np.ix_(rows,cols)],(8,4,4))
            k+=16
    quality.update(conventions=conventions, valid_dimensions=int(valid.sum()),
        lbp_support=lbp_counts, glcm_pairs=glcm_counts, gabor_support=gabor_counts,
        profile_occupancy=occupancy, foreground_pixels=area,
        component_count=int(cv2.connectedComponents(m.astype(np.uint8),connectivity=8)[0]-1))
    result = vector.astype('<f4')
    if result.shape!=(400,) or not np.isfinite(result).all():
        raise ValueError('Invalid B400 dimensions or NaN/Inf')
    return result,valid,quality


def fit_normalizer(raw, valid, fit_digest):
    raw,valid = np.asarray(raw,dtype=float),np.asarray(valid,dtype=bool)
    if raw.ndim!=2 or raw.shape[1]!=400 or valid.shape!=raw.shape or not len(raw) or not np.isfinite(raw).all():
        raise ValueError('Invalid normalizer training matrix')
    counts = valid.sum(axis=0)
    mean = np.divide(np.where(valid,raw,0).sum(axis=0),counts,out=np.zeros(400),where=counts>0)
    variance = np.divide(np.where(valid,(raw-mean)**2,0).sum(axis=0),counts,out=np.zeros(400),where=counts>0)
    scale = np.sqrt(variance)
    constant = scale<=1e-12
    scale[constant]=1
    params = dict(version=1, feature_config_sha256=digest_json(configuration()), fit_digest=fit_digest,
                  fit_rows=len(raw), valid_counts=counts.tolist(), mean=mean.tolist(), scale=scale.tolist(),
                  constant=constant.tolist(), rules=configuration()['normalization'])
    params['id']=digest_json(params)
    return params


def transform(raw, valid, params):
    if params['feature_config_sha256']!=digest_json(configuration()):
        raise ValueError('Normalizer configuration differs')
    check = dict(params)
    saved_id = check.pop('id')
    if digest_json(check)!=saved_id:
        raise ValueError('Normalizer checksum differs')
    x = np.asarray(raw,dtype=float).copy()
    valid = np.asarray(valid,dtype=bool)
    if x.shape[-1:]!=(400,) or x.shape!=valid.shape or not np.isfinite(x).all():
        raise ValueError('Invalid vector for normalization')
    x[...,HISTOGRAM_INDICES] = np.sqrt(np.maximum(x[...,HISTOGRAM_INDICES],0))
    cont = CONTINUOUS_INDICES
    mean,scale = np.array(params['mean']),np.array(params['scale'])
    x[...,cont] = (x[...,cont]-mean[cont])/scale[cont]
    x[~valid]=0

    def unit(part):
        norm = np.linalg.norm(part,axis=-1,keepdims=True)
        return np.divide(part,norm,out=np.zeros_like(part),where=norm>1e-15)

    for (_,start,stop),subblocks,weight in zip(GROUPS,params['rules']['subblocks'],params['rules']['weights']):
        for s,e in subblocks:
            x[...,s:e] = unit(x[...,s:e])
        x[...,start:stop] = unit(x[...,start:stop])*math.sqrt(weight)
    return unit(x).astype('<f4')


def extract_normalized(rgb, mask, normalizer):
    """Reuse frozen requirement-3 parameters for a future query; never refit."""
    raw, valid, quality = extract(rgb, mask)
    return raw, transform(raw, valid, normalizer), valid, quality
