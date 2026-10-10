import sys, numpy as np
from PIL import Image, ImageFilter
raw, outp = sys.argv[1], sys.argv[2]
W,H=1280,720
v=np.memmap(raw,np.uint8,'r').reshape(-1,H,W,3)
N=len(v); R=10
def ss(x,lo,hi):
    t=np.clip((x-lo)/(hi-lo),0,1); return t*t*(3-2*t)
strong=np.zeros((N,H,W),bool)
for i in range(N):
    a=v[i].astype(np.int16); mn=a.min(2)
    strong[i]=(mn<110)|((a.max(2)-mn)>90)
out=open(outp,'wb')
for i in range(N):
    a=v[i].astype(np.float32); mn=a.min(2)
    t=ss(mn,150,195)
    # pixels que pertencem ao logotipo em quadros vizinhos (brilho passando) usam limiar mais rígido
    # só usa quadros vizinhos onde o logotipo não se deslocou (o quadro atual fica coberto pelo vizinho)
    u=strong[i].copy(); mi=strong[i]; ni=max(mi.sum(),1)
    for j in range(max(0,i-R),min(N,i+R+1)):
        if j==i: continue
        dj=np.asarray(Image.fromarray((strong[j]*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)))>0
        if (mi&dj).sum()/ni>0.97: u|=strong[j]
    m=Image.fromarray((u*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2))
    p=np.asarray(m,np.float32)/255.0
    t2=ss(mn,215,245)
    t=t*(1-p)+np.minimum(t,t2)*p
    o=a+(255-a)*t[...,None]
    out.write(np.clip(o+0.5,0,255).astype(np.uint8).tobytes())
out.close()
