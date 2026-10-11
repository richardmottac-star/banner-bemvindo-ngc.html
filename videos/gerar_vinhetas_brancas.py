# Vinhetas SEGOV no estilo "fundo branco": logotipo com texto escuro em relevo e bandeira colorida.
# Uso: LARGURA=1920 [RELEVO=0] python3 gerar_vinhetas_brancas.py <linha|queda|circulo|persiana> \
#        | ffmpeg -f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i - -an ... saida.mp4
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFilter
import gerar_video_verde as base
from gerar_video_verde import W, H, K, FPS, N, xx, yy, prog, ease_out, ease_in_out, ease_back

BRANCO = (255, 255, 255)
TEXTO = np.array([0, 0, 0], np.float32)             # base preto absoluto (#000000)
VERMELHO, VERDE = (225, 11, 24), (152, 196, 40)     # cores da bandeira

# ---------- logotipo escuro (a partir do PNG branco: texto pintado de preto absoluto) ----------
def logo_escuro():
    a = np.asarray(base.logo_g).astype(np.float32)
    texto = np.zeros(a.shape[:2], bool)
    texto[:, base.s(212):] = True
    # degradê sutil como no vídeo original: cinza muito escuro no topo da letra -> preto absoluto embaixo
    linhas = np.arange(a.shape[0], dtype=np.float32)
    cor = np.zeros(a.shape[0], np.float32)
    for y0, y1 in ((0, base.s(base.TIT_ROWS[1])), (base.s(base.SUB_ROWS[0]), a.shape[0])):
        u = np.clip((linhas - y0) / max(1, y1 - y0), 0, 1)
        dentro = (linhas >= y0) & (linhas < y1)
        cor[dentro] = (48 * (1 - u) ** 2)[dentro]          # topo ~#303030, metade inferior ~#000000
    cor = TEXTO + cor[:, None, None]
    rgb = np.where(texto[..., None], np.broadcast_to(cor, a[..., :3].shape), a[..., :3])
    return Image.fromarray(np.dstack([rgb, a[..., 3]]).astype(np.uint8), 'RGBA')

LOGO = logo_escuro()
LX, LY = base.X0, base.Y0
# profundidade do relevo 3D da bandeira (px); RELEVO=0 gera o logotipo plano
PROF = round(float(os.environ.get('RELEVO', 7)) * K)

def relevo(peca, prof):
    """Peça RGBA com espessura 3D (camadas escurecidas para baixo/direita)."""
    prof = int(prof)
    if prof <= 0:
        return peca.copy()                           # cópia: quem chama pode alterar a transparência
    out = Image.new('RGBA', (peca.width + prof, peca.height + prof), (0, 0, 0, 0))
    lado = np.asarray(peca).astype(np.float32)
    # só a bandeira (partes coloridas/brancas) ganha espessura; o texto preto mantém o desenho oficial
    lado[..., 3] *= lado[..., :3].max(-1) > 60
    lado[..., :3] *= 0.35
    lado = Image.fromarray(lado.astype(np.uint8), 'RGBA')
    for k in range(prof, 0, -1):
        out.alpha_composite(lado, (int(k * 0.6), k))
    out.alpha_composite(peca, (0, 0))
    return out

def colar(img, camada, pos, sombra=1.0):
    """Cola com sombra cinza suave projetada no fundo branco."""
    if sombra > 0:
        a = camada.getchannel('A').point(lambda v, k=0.28 * sombra: int(v * k))
        sh = Image.new('L', img.size, 0)
        sh.paste(a, (pos[0] + round(10 * K), pos[1] + round(16 * K)))
        sh = sh.filter(ImageFilter.GaussianBlur(14 * K))
        img = Image.composite(Image.new('RGB', img.size, (0, 0, 0)), img, sh)
    img.paste(camada, pos, camada)
    return img

def brilho(img, alfa, p, larg=45, inclin=0.35, forca=0.6):
    if not 0 < p < 1:
        return img
    pos = LX - 300 * K + p * (LOGO.width + 600 * K)
    d = (xx - pos - (yy - H / 2) * inclin) / (larg * K)
    faixa = np.exp(-d * d) * forca * np.asarray(alfa, np.float32) / 255.0
    a = np.asarray(img, np.float32)
    return Image.fromarray(np.clip(a + (255 - a) * faixa[..., None], 0, 255).astype(np.uint8))

LOGO_3D = relevo(LOGO, PROF)
ALFA_FINAL = Image.new('L', (W, H), 0)
ALFA_FINAL.paste(LOGO.getchannel('A'), (LX, LY))

def zoom_lento(img, t, t0=5.0):
    z = 1 + 0.03 * ease_in_out(prog(t, t0, 10.0))
    if z <= 1.0005:
        return img
    zw, zh = W / z, H / z
    return img.resize((W, H), Image.BICUBIC, box=((W - zw) / 2, (H - zh) / 2, (W + zw) / 2, (H + zh) / 2))

def branco():
    return Image.new('RGB', (W, H), BRANCO)

def logo_com_relevo(t, t0, t1):
    """Logotipo inteiro com o relevo e a sombra crescendo entre t0 e t1."""
    p = ease_out(prog(t, t0, t1))
    return relevo(LOGO, PROF * p), p

# pedaços do logotipo (mesmos recortes do PNG oficial)
s = base.s
BANDEIRA = LOGO.crop((0, 0, s(212), LOGO.height))
LETRAS = [(LOGO.crop((s(c0), 0, s(c1), s(base.TIT_ROWS[1]))), s(c0)) for c0, c1 in base.LETRAS_COLS]
SUBT = LOGO.crop((s(212), s(base.SUB_ROWS[0]), LOGO.width, LOGO.height))

# ------------------------------------------------------------------
# LINHA: um traço fino se desenha no centro e se abre como uma janela,
# revelando o logotipo, que ganha relevo e sombra.
# ------------------------------------------------------------------
def quadro_linha(i):
    t = i / FPS
    img = branco()
    cy = LY + LOGO.height // 2
    meia = LOGO.width / 2 + 40 * K
    pl = ease_in_out(prog(t, 0.3, 1.1))
    pa = ease_in_out(prog(t, 1.1, 2.0))
    abre = pa * (LOGO.height / 2 + 30 * K)
    if pa > 0:
        cam, pr = logo_com_relevo(t, 2.0, 2.9)
        janela = Image.new('L', (W, H), 0)
        ImageDraw.Draw(janela).rectangle((0, cy - abre, W, cy + abre), fill=255)
        tmp = colar(branco(), cam, (LX, LY), sombra=pr)
        img = Image.composite(tmp, img, janela)
    # traços (um que se desenha; depois dois que se afastam e somem)
    d = ImageDraw.Draw(img)
    esp = max(2, round(3 * K))
    if pl > 0 and t < 2.4:
        alfa = 1 - prog(t, 1.8, 2.4)
        cor = tuple(int(255 - (255 - c) * alfa) for c in TEXTO)
        x0, x1 = W / 2 - meia * pl, W / 2 + meia * pl
        for y in ({cy} if pa == 0 else {cy - abre, cy + abre}):
            d.rectangle((x0, y - esp / 2, x1, y + esp / 2), fill=cor)
    img = brilho(img, ALFA_FINAL, prog(t, 3.6, 4.6))
    img = brilho(img, ALFA_FINAL, prog(t, 7.0, 8.0), larg=30, inclin=-0.35)
    return zoom_lento(img, t)

# ------------------------------------------------------------------
# QUEDA: a bandeira vira no lugar e as letras de SEGOV caem do alto
# com quique; o subtítulo desliza da esquerda.
# ------------------------------------------------------------------
def quique(x):
    n, d = 7.5625, 2.75
    if x < 1 / d: return n * x * x
    if x < 2 / d: x -= 1.5 / d; return n * x * x + 0.75
    if x < 2.5 / d: x -= 2.25 / d; return n * x * x + 0.9375
    x -= 2.625 / d; return n * x * x + 0.984375

def quadro_queda(i):
    t = i / FPS
    img = branco()
    pf = prog(t, 0.5, 1.5)
    if pf > 0:
        sx = min(1.0, max(0.02, ease_back(pf)))
        b = relevo(BANDEIRA, PROF * ease_out(prog(t, 1.2, 1.8)))
        bw = max(2, int(b.width * sx))
        b = b.resize((bw, b.height), Image.LANCZOS)
        img = colar(img, b, (LX + (BANDEIRA.width - bw) // 2, LY), sombra=sx)
    for k, (peca, x) in enumerate(LETRAS):
        p = prog(t, 1.3 + k * 0.2, 2.2 + k * 0.2)
        if p <= 0:
            continue
        y = LY - (1 - quique(p)) * (LY + peca.height + 40 * K)
        img = colar(img, relevo(peca, PROF), (LX + x, int(y)), sombra=quique(p))
    ps = ease_out(prog(t, 3.0, 3.8))
    if ps > 0:
        c = relevo(SUBT, PROF // 3)
        c.putalpha(c.getchannel('A').point(lambda v, k=ps: int(v * k)))
        img = colar(img, c, (LX + s(212) - int((1 - ps) * 120 * K), LY + s(base.SUB_ROWS[0])), sombra=ps * 0.6)
    img = brilho(img, ALFA_FINAL, prog(t, 4.6, 5.6))
    img = brilho(img, ALFA_FINAL, prog(t, 7.6, 8.6), larg=30, inclin=-0.35)
    return zoom_lento(img, t, 5.5)

# ------------------------------------------------------------------
# CÍRCULO: círculos vermelho, verde e branco (cores da bandeira) se
# expandem do centro; o logotipo aparece dentro do círculo branco.
# ------------------------------------------------------------------
RAIO_MAX = math.hypot(W, H) / 2 + 20

def circulo(r):
    m = Image.new('L', (W, H), 0)
    if r > 0:
        ImageDraw.Draw(m).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=255)
    return m.filter(ImageFilter.GaussianBlur(1.2 * K))

def quadro_circulo(i):
    t = i / FPS
    img = branco()
    cam, pr = logo_com_relevo(t, 2.1, 2.9)
    final = colar(branco(), cam, (LX, LY), sombra=pr)
    camadas = [(0.2, VERMELHO), (0.45, VERDE), (0.75, None)]   # None = branco com o logotipo
    for t0, cor in camadas:
        p = ease_in_out(prog(t, t0, t0 + 1.2))
        if p <= 0:
            continue
        m = circulo(p * RAIO_MAX)
        topo = final if cor is None else Image.new('RGB', (W, H), cor)
        img = Image.composite(topo, img, m)
    # escala suave do logotipo enquanto o círculo branco abre
    img = brilho(img, ALFA_FINAL, prog(t, 3.6, 4.6))
    img = brilho(img, ALFA_FINAL, prog(t, 7.0, 8.0), larg=30, inclin=-0.35)
    return zoom_lento(img, t)

# ------------------------------------------------------------------
# PERSIANA: o logotipo aparece em tiras verticais que giram e se abrem
# em sequência, da esquerda para a direita; depois ganha relevo.
# ------------------------------------------------------------------
TIRAS = 16

def quadro_persiana(i):
    t = i / FPS
    img = branco()
    cam, pr = logo_com_relevo(t, 2.6, 3.4)
    larg_tira = cam.width / TIRAS
    tudo_aberto = t >= 0.6 + (TIRAS - 1) * 0.08 + 0.6
    if tudo_aberto:
        img = colar(img, cam, (LX, LY), sombra=pr)
    else:
        camada = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for k in range(TIRAS):
            p = prog(t, 0.6 + k * 0.08, 1.2 + k * 0.08)
            if p <= 0:
                continue
            e = min(1.0, ease_back(p, 1.3))
            x0, x1 = int(k * larg_tira), int((k + 1) * larg_tira)
            tira = cam.crop((x0, 0, x1, cam.height))
            w = max(1, int(tira.width * e))
            tira = tira.resize((w, tira.height), Image.BILINEAR)
            # tira escurece enquanto está "de lado"
            if p < 1:
                arr = np.asarray(tira).astype(np.float32)
                arr[..., :3] *= 0.55 + 0.45 * p
                arr[..., 3] *= min(1, p * 2)
                tira = Image.fromarray(arr.astype(np.uint8), 'RGBA')
            camada.alpha_composite(tira, (LX + x0 + (x1 - x0 - w) // 2, LY + int((1 - p) * 20 * K)))
        img = colar(img, camada, (0, 0), sombra=0.5)
    img = brilho(img, ALFA_FINAL, prog(t, 4.0, 5.0))
    img = brilho(img, ALFA_FINAL, prog(t, 7.2, 8.2), larg=30, inclin=-0.35)
    return zoom_lento(img, t)

VERSOES = {'linha': quadro_linha, 'queda': quadro_queda, 'circulo': quadro_circulo, 'persiana': quadro_persiana}

if __name__ == '__main__':
    f = VERSOES[sys.argv[1]]
    out = sys.stdout.buffer
    for i in range(N):
        out.write(f(i).tobytes())
