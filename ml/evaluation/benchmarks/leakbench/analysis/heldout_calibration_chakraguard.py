import json,re,numpy as np,collections
TAU=[0.5,0.6,0.7,0.8,0.9,0.95,0.98,0.99,0.995,0.999,0.9995,0.9999]
IND=("test_kvasir","test_clinicdb","test_colondb","test_etis","test_cvc300")
rng=np.random.default_rng(0)
res={}
for s in (42,43,44):
    F=json.load(open(f'r3/ops/e4_negtrain__xattn__s{s}.ops.json'))['frames']
    def mask(x,pos):
        m=np.zeros(len(TAU),bool)
        for a,mp,ov in x['comps']:
            if pos and ov==0: continue
            if a>=1: m|=np.array(TAU)<=mp
        return m
    ind=np.array([mask(x,True) for x in F if x['split'] in IND]).mean(0)
    ext=np.array([mask(x,True) for x in F if x['split']=='test_piccolo_all' or x['split'].startswith('test_polypgen_C')]).mean(0)
    pg=[x for x in F if x['split']=='neg_polypgen']
    seqs=collections.defaultdict(list)
    for x in pg:
        sq=re.search(r'(seq\d+)_neg',x['image']).group(1); seqs[sq].append(mask(x,False))
    names=sorted(seqs); S=[np.array(seqs[n]) for n in names]
    print('seed',s,'n_seq',len(names),'frames',sum(len(v) for v in S))
    allfa=np.concatenate(S).mean(0)
    print(' pooled PG FA by tau',dict(zip(TAU,np.round(allfa,4))))
    out=[]
    for r in range(2000):
        perm=rng.permutation(len(names)); h=len(names)//2
        cal=np.concatenate([S[i] for i in perm[:h]]); te=np.concatenate([S[i] for i in perm[h:]])
        fc=cal.mean(0); ok=fc<=0.05
        if not ok.any(): continue
        t=np.where(ok,ind,-1).argmax()
        out.append((TAU[t],te.mean(0)[t],ind[t],ext[t]))
    o=np.array(out)
    print(' 50/50 seq split x2000: test-half FA mean %.4f  p5 %.4f p95 %.4f  frac>0.05 %.3f | det_in %.4f det_ext %.4f'%(o[:,1].mean(),np.percentile(o[:,1],5),np.percentile(o[:,1],95),(o[:,1]>0.05).mean(),o[:,2].mean(),o[:,3].mean()))
    print(' tau chosen counts',collections.Counter(o[:,0].round(4)).most_common(4))
    # leave-one-sequence-out
    lo=[];tt=[]
    for k in range(len(names)):
        cal=np.concatenate([S[i] for i in range(len(names)) if i!=k]); fc=cal.mean(0); ok=fc<=0.05
        if not ok.any(): continue
        t=np.where(ok,ind,-1).argmax(); lo.append(S[k].mean(0)[t]); tt.append(t)
    # frame-weighted LOSO FA
    num=sum(S[k].shape[0]*S[k].mean(0)[t] for k,t in zip(range(len(names)),tt)); den=sum(len(x) for x in S)
    print(' LOSO: frame-weighted FA %.4f; per-seq mean %.4f; taus %s'%(num/den,np.mean(lo),collections.Counter(TAU[t] for t in tt)))
    # default rule
    print(' default rule (0.5,1px): PG FA %.4f; det_in %.4f det_ext %.4f'%(allfa[0],ind[0],ext[0]))
