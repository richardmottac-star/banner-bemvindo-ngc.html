# Deixa o fundo do vídeo em branco absoluto (#FFFFFF) e remove o reflexo espelhado no chão.
# Uso: ffmpeg -i entrada.mp4 -f rawvideo -pix_fmt rgb24 raw.rgb
#      python3 fundo_branco.py raw.rgb saida.rgb   (1280x720)
import sys, numpy as np
from PIL import Image, ImageFilter
raw, outp = sys.argv[1], sys.argv[2]
W,H=1280,720
v=np.memmap(raw,np.uint8,'r').reshape(-1,H,W,3)
N=len(v)

def ss(x,lo,hi):
    t=np.clip((x-lo)/(hi-lo),0,1); return t*t*(3-2*t)
def img(m): return Image.fromarray((m*255).astype(np.uint8))
def dil1d(m,k):
    c=np.cumsum(np.pad(m.astype(np.int32),((0,0),(k//2+1,k//2))),1)
    return (c[:,k:]-c[:,:-k])>0

out=open(outp,'wb')
for i in range(N):
    a=v[i].astype(np.float32); mn=a.min(2)
    # 1) fundo claro e neutro vira branco
    t=ss(mn,150,195)
    strong=(mn<110)|((a.max(2)-mn)>90)
    # 2) faixa do logotipo: liga horizontalmente as letras escuras (onde o brilho passa, a letra clareia)
    zone=~dil1d(~dil1d(strong,151),151)
    zone=np.asarray(img(zone).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2)),np.float32)/255
    # nível de branco local (máximo da vizinhança) -> letras iluminadas continuam mais escuras que ele
    q=Image.fromarray(np.clip(mn,0,255).astype(np.uint8)).resize((W//4,H//4),Image.BOX)
    lmax=np.asarray(q.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(3)).resize((W,H),Image.BILINEAR),np.float32)
    keep=ss(lmax-mn,4,14)*zone
    t=t*(1-keep)
    # 3) reflexo no chão: tudo abaixo do logotipo vira branco
    ys=np.where(strong.sum(1)>3)[0]
    if len(ys):
        cut=ys[-1]+25
        t=np.maximum(t,np.clip((np.arange(H)-cut)/15.0,0,1)[:,None])
    o=a+(255-a)*t[...,None]
    out.write(np.clip(o+0.5,0,255).astype(np.uint8).tobytes())
out.close()
