# Versões extras da vinheta SEGOV (fundo verde, logotipo oficial em branco).
# Uso: LARGURA=1920 python3 gerar_vinhetas_extras.py <zoom|paineis|mosaico> | ffmpeg -f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i - ... saida.mp4
import sys, os, math, random, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFilter
import gerar_video_verde as base
from gerar_video_verde import W, H, K, FPS, N, xx, yy, prog, ease_out, ease_in_out, ease_back

LOGO = base.logo_g                     # logotipo já na escala final (RGBA)
LX, LY = base.X0, base.Y0              # posição final do logotipo
TX = base.TX                           # início do texto (depois da bandeira)
SOMBRA = (0, 30, 12)

def fundo_img(t, luzes=True):
    bg = base.fundo(t) if luzes else base.FUNDO * (0.35 + 0.65 * ease_out(prog(t, 0.0, 1.0)))
    return Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))

def colar(img, camada, pos, sombra=True):
    """Cola uma camada RGBA com sombra suave em verde escuro."""
    if sombra:
        a = camada.getchannel('A').point(lambda v: v * 0.45)
        sh = Image.new('L', img.size, 0)
        sh.paste(a, (pos[0] + round(4 * K), pos[1] + round(7 * K)))
        sh = sh.filter(ImageFilter.GaussianBlur(7 * K))
        img = Image.composite(Image.new('RGB', img.size, SOMBRA), img, sh)
    img.paste(camada, pos, camada)
    return img

def brilho(img, alfa, p, larg=45, inclin=0.35):
    """Faixa de luz que atravessa o logotipo (só onde há logotipo)."""
    if not 0 < p < 1:
        return img
    pos = LX - 300 * K + p * (LOGO.width + 600 * K)
    d = (xx - pos - (yy - H / 2) * inclin) / (larg * K)
    faixa = np.exp(-d * d) * 0.75 * np.asarray(alfa, np.float32) / 255.0
    a = np.asarray(img, np.float32)
    return Image.fromarray(np.clip(a + (255 - a) * faixa[..., None], 0, 255).astype(np.uint8))

def alfa_logo():
    m = Image.new('L', (W, H), 0)
    m.paste(LOGO.getchannel('A'), (LX, LY))
    return m
ALFA_FINAL = alfa_logo()

def zoom_lento(img, t, t0=5.0):
    z = 1 + 0.03 * ease_in_out(prog(t, t0, 10.0))
    if z <= 1.0005:
        return img
    zw, zh = W / z, H / z
    return img.resize((W, H), Image.BICUBIC, box=((W - zw) / 2, (H - zh) / 2, (W + zw) / 2, (H + zh) / 2))

def flash(img, intensidade):
    if intensidade <= 0:
        return img
    return Image.blend(img, Image.new('RGB', img.size, (255, 255, 255)), min(1, intensidade))

# ------------------------------------------------------------------
# Versão 1 — ZOOM: o logotipo vem de muito perto, desfocado, e "pousa"
# na tela com um clarão; depois dois reflexos de luz.
# ------------------------------------------------------------------
def quadro_zoom(i):
    t = i / FPS
    img = fundo_img(t, luzes=False)
    p = prog(t, 0.5, 2.3)
    if p > 0:
        e = ease_out(p)
        esc = 1 + 3.5 * (1 - e)
        lw, lh = int(LOGO.width * esc), int(LOGO.height * esc)
        camada = LOGO.resize((lw, lh), Image.BILINEAR)
        raio = 14 * K * (1 - e)
        if raio > 0.3:
            camada = camada.filter(ImageFilter.GaussianBlur(raio))
        a = camada.getchannel('A').point(lambda v, k=min(1, p * 2.2): int(v * k))
        camada.putalpha(a)
        img = colar(img, camada, ((W - lw) // 2, LY + (LOGO.height - lh) // 2), sombra=p > 0.85)
    # clarão e anel quando o logotipo pousa
    img = flash(img, 0.55 * (1 - prog(t, 2.25, 2.9)) * (t >= 2.25))
    pr = prog(t, 2.25, 3.3)
    if 0 < pr < 1:
        r = (80 + ease_out(pr) * 1000) * K
        d = np.abs(np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2 * 2.2) - r) / ((20 + 50 * pr) * K)
        a = np.asarray(img, np.float32) + (np.exp(-d * d) * 90 * (1 - pr))[..., None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    img = brilho(img, ALFA_FINAL, prog(t, 3.6, 4.6))
    img = brilho(img, ALFA_FINAL, prog(t, 7.0, 8.0), larg=30, inclin=-0.35)
    return zoom_lento(img, t)

# ------------------------------------------------------------------
# Versão 2 — PAINÉIS: faixas diagonais branca e verdes varrem a tela;
# a bandeira entra pela esquerda, SEGOV pela direita e o subtítulo sobe.
# ------------------------------------------------------------------
BANDEIRA = LOGO.crop((0, 0, base.s(212), LOGO.height))
TITULO = LOGO.crop((base.s(212), 0, LOGO.width, base.s(base.TIT_ROWS[1])))
SUBT = LOGO.crop((base.s(212), base.s(base.SUB_ROWS[0]), LOGO.width, LOGO.height))
PAINEIS = [  # (início, cor, largura)
    (0.0, (255, 255, 255), 1.0),
    (0.18, (120, 190, 60), 1.0),
    (0.36, (0, 96, 44), 1.0),
]

def quadro_paineis(i):
    t = i / FPS
    img = fundo_img(t, luzes=False)
    # faixas diagonais que atravessam a tela (passam e saem pela direita)
    for t0, cor, _ in PAINEIS:
        p = ease_in_out(prog(t, t0, t0 + 1.3))
        if 0 < p < 1:
            frente = -500 * K + p * (W + 1300 * K)
            tras = frente - (420 + 380 * math.sin(p * math.pi)) * K
            m = Image.new('L', (W, H), 0)
            ImageDraw.Draw(m).polygon([(tras, 0), (frente, 0), (frente - 300 * K, H), (tras - 300 * K, H)], fill=255)
            img = Image.composite(Image.new('RGB', (W, H), cor), img, m)
    # bandeira entra pela esquerda
    pb = prog(t, 1.3, 2.3)
    if pb > 0:
        x = int(LX + (-BANDEIRA.width - LX - 40 * K) * (1 - ease_back(pb, 1.2)))
        img = colar(img, BANDEIRA, (x, LY))
    # SEGOV entra pela direita
    pt = prog(t, 1.55, 2.55)
    if pt > 0:
        x0 = LX + base.s(212)
        x = int(x0 + (W + 40 * K - x0) * (1 - ease_out(pt)))
        img = colar(img, TITULO, (x, LY))
    # subtítulo sobe e aparece
    ps = prog(t, 2.5, 3.3)
    if ps > 0:
        e = ease_out(ps)
        c = SUBT.copy()
        c.putalpha(c.getchannel('A').point(lambda v, k=e: int(v * k)))
        img = colar(img, c, (LX + base.s(212), LY + base.s(base.SUB_ROWS[0]) + int((1 - e) * 40 * K)))
    # uma faixa branca fina corta o logotipo como reflexo
    img = brilho(img, ALFA_FINAL, prog(t, 4.0, 5.0), larg=60, inclin=0.6)
    img = brilho(img, ALFA_FINAL, prog(t, 7.2, 8.2), larg=35, inclin=0.6)
    return zoom_lento(img, t)

# ------------------------------------------------------------------
# Versão 3 — MOSAICO: o logotipo se monta em blocos que "estalam"
# em sequência, da bandeira para o texto; depois um reflexo de luz.
# ------------------------------------------------------------------
TAM = round(34 * K)
random.seed(7)
BLOCOS = []
alfa_logo_arr = np.asarray(LOGO.getchannel('A'))
for by in range(0, LOGO.height, TAM):
    for bx in range(0, LOGO.width, TAM):
        if alfa_logo_arr[by:by + TAM, bx:bx + TAM].max() == 0:
            continue
        ordem = bx / LOGO.width
        t0 = 0.8 + ordem * 2.0 + random.uniform(0, 0.45)
        BLOCOS.append((bx, by, t0, LOGO.crop((bx, by, bx + TAM, by + TAM))))

def quadro_mosaico(i):
    t = i / FPS
    img = fundo_img(t, luzes=False)
    camada = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    montado = t >= max(b[2] for b in BLOCOS) + 0.5
    if montado:
        camada.paste(LOGO, (LX, LY), LOGO)
    else:
        for bx, by, t0, bloco in BLOCOS:
            p = prog(t, t0, t0 + 0.45)
            if p <= 0:
                continue
            e = min(1.0, ease_back(p, 2.2))
            lado = max(1, int(TAM * e))
            b = bloco.resize((lado, lado), Image.BILINEAR) if lado != TAM else bloco
            if p < 1:
                b.putalpha(b.getchannel('A').point(lambda v, k=min(1, p * 2): int(v * k)))
            off = (TAM - lado) // 2
            camada.alpha_composite(b, (LX + bx + off, LY + by + off - int((1 - p) * 18 * K)))
    # brilho branco nos blocos que acabaram de chegar
    if camada.getbbox():
        img = colar(img, camada, (0, 0))
    img = brilho(img, ALFA_FINAL, prog(t, 3.9, 4.9))
    img = brilho(img, ALFA_FINAL, prog(t, 7.2, 8.2), larg=30, inclin=-0.35)
    return zoom_lento(img, t)

VERSOES = {'zoom': quadro_zoom, 'paineis': quadro_paineis, 'mosaico': quadro_mosaico}

if __name__ == '__main__':
    f = VERSOES[sys.argv[1]]
    out = sys.stdout.buffer
    for i in range(N):
        out.write(f(i).tobytes())
