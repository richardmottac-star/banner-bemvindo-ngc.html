# Gera a vinheta SEGOV com fundo verde do Estado e escrita em branco.
# Uso: LARGURA=1920 python3 gerar_video_verde.py | ffmpeg -f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i - ... saida.mp4
# (LARGURA define a resolução 16:9; padrão 1280x720)
import sys, os, math, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(AQUI, 'assets')
W = int(os.environ.get('LARGURA', 1280)); H = W * 9 // 16
K = W / 1280                                       # escala das medidas (desenhadas em 1280x720)
FPS, DUR = 30, 10.0
N = int(FPS * DUR)

VERDE_CLARO = np.array([0, 132, 61], np.float32)    # #00843D
VERDE_ESCURO = np.array([0, 72, 34], np.float32)    # #004822
BRANCO = (255, 255, 255)

# ---------- curvas de animação ----------
def clamp(x): return max(0.0, min(1.0, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def ease_out(x): return 1 - (1 - x) ** 3
def ease_in_out(x): return 3 * x * x - 2 * x * x * x if x < 1 else 1.0
def ease_back(x, s=1.6): x -= 1; return 1 + x * x * ((s + 1) * x + s)

# ---------- fundo verde com gradiente radial ----------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dist = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
mix = np.clip(dist, 0, 1)[..., None] ** 1.4
FUNDO = VERDE_CLARO * (1 - mix) + VERDE_ESCURO * mix

def fundo(t):
    bg = FUNDO.copy()
    # faixas de luz diagonais que atravessam a tela (transição de abertura)
    for k, (t0, larg, forca) in enumerate([(0.0, 260 * K, 38), (0.35, 140 * K, 26), (5.6, 320 * K, 18)]):
        p = prog(t, t0, t0 + 1.6)
        if 0 < p < 1:
            pos = -600 * K + p * (W + 1200 * K)
            d = (xx + yy * 0.55 - pos) / larg
            bg += (np.exp(-d * d) * forca * math.sin(p * math.pi))[..., None]
    # entrada: escurecido para o verde
    bg *= 0.35 + 0.65 * ease_out(prog(t, 0.0, 1.0))
    return bg

# ---------- elementos (logotipo oficial em branco, PNG transparente) ----------
logo = Image.open(os.path.join(ASSETS, 'logo_segov_branco.png')).convert('RGBA')
LARG_LOGO = 1000 * K                                   # largura final do logotipo na tela
SC = LARG_LOGO / logo.width
logo_g = logo.resize((round(logo.width * SC), round(logo.height * SC)), Image.LANCZOS)
def s(v): return round(v * SC)

# recortes no PNG original (pixels): bandeira, letras S-E-G-O-V e subtítulo
FLAG_BOX = (0, 1, 209, 153)                        # parte opaca da bandeira
LETRAS_COLS = [(215, 318), (318, 400), (400, 510), (510, 634), (634, 749)]
TIT_ROWS, SUB_ROWS = (0, 116), (116, logo.height)

bandeira = logo.crop(FLAG_BOX).convert('RGB')
bandeira_hd = bandeira.resize((bandeira.width * 3, bandeira.height * 3), Image.LANCZOS)
FLAG_W, FLAG_H = s(FLAG_BOX[2] - FLAG_BOX[0]), s(FLAG_BOX[3] - FLAG_BOX[1])
alfa = logo_g.getchannel('A')
pecas_letras = [(alfa.crop((s(c0), s(TIT_ROWS[0]), s(c1), s(TIT_ROWS[1]))), s(c0)) for c0, c1 in LETRAS_COLS]
peca_sub = alfa.crop((s(215), s(SUB_ROWS[0]), logo_g.width, logo_g.height))

X0 = (W - logo_g.width) // 2
Y0 = (H - logo_g.height) // 2
FX, FY = X0, Y0 + s(FLAG_BOX[1])     # posição final da bandeira
TX = X0 + s(215)                      # x inicial do texto
tit_h = s(TIT_ROWS[1] - TIT_ROWS[0])
tit_w = logo_g.width - s(215)
grupo_w = logo_g.width

def camada_texto(t):
    """Máscara (L) do texto branco do logotipo no instante t."""
    m = Image.new('L', (W, H), 0)
    # título: cada letra sobe de trás de uma "janela", em sequência
    for i, (peca, x) in enumerate(pecas_letras):
        p = ease_out(prog(t, 2.6 + i * 0.11, 3.35 + i * 0.11))
        if p <= 0: continue
        dy = int((1 - p) * (tit_h + 30 * K))
        vis = peca.crop((0, 0, peca.width, max(0, peca.height - dy)))
        if vis.height == 0: continue
        vis = vis.point(lambda v, k=min(1, p * 1.5): int(v * k))
        m.paste(vis, (X0 + x, Y0 + dy), vis)
    # subtítulo: sobe levemente e é revelado por uma cortina da esquerda para a direita
    ps = prog(t, 3.9, 5.0)
    if ps > 0:
        sm = Image.new('L', (W, H), 0)
        sobe = int((1 - ease_out(ps)) * 14 * K)
        sm.paste(peca_sub, (TX, Y0 + s(SUB_ROWS[0]) + sobe))
        frente = TX - 80 * K + ease_in_out(ps) * (tit_w + 160 * K)
        rampa = np.clip((frente - np.arange(W, dtype=np.float32)) / (80.0 * K), 0, 1)
        cort = Image.fromarray((np.tile(rampa, (H, 1)) * 255).astype(np.uint8))
        m = ImageChops.lighter(m, ImageChops.multiply(sm, cort))
    return m

def quadro(i):
    t = i / FPS
    bg = fundo(t)
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))

    # ----- bandeira: gira no próprio eixo (efeito "cartão virando") no centro, depois desliza para a esquerda
    pf = prog(t, 0.6, 1.7)
    pm = ease_in_out(prog(t, 1.9, 2.8))
    alvo_x, alvo_y = FX, FY
    cx0, cy0 = (W - FLAG_W * 1.25) / 2, (H - FLAG_H * 1.25) / 2
    esc = 1.25 + (1.0 - 1.25) * pm
    fx = cx0 + (alvo_x - cx0) * pm
    fy = cy0 + (alvo_y - cy0) * pm
    flag_mask = Image.new('L', (W, H), 0)
    if pf > 0:
        sx = max(0.02, ease_back(pf))
        fw = max(2, int(FLAG_W * esc * min(sx, 1.08)))
        fh = int(FLAG_H * esc)
        b = bandeira_hd.resize((fw, fh), Image.LANCZOS)
        # brilho na face durante o giro
        if pf < 1:
            b = Image.blend(b, Image.new('RGB', b.size, BRANCO), 0.45 * (1 - pf))
        bx = int(fx + (FLAG_W * esc - fw) / 2)
        by = int(fy)
        # sombra suave
        sh = Image.new('L', (W, H), 0)
        ImageDraw.Draw(sh).rectangle((bx + 6 * K, by + 10 * K, bx + fw + 6 * K, by + fh + 10 * K), fill=110)
        sh = sh.filter(ImageFilter.GaussianBlur(14 * K))
        img = Image.composite(Image.new('RGB', (W, H), (0, 30, 12)), img, sh)
        img.paste(b, (bx, by))
        ImageDraw.Draw(flag_mask).rectangle((bx, by, bx + fw - 1, by + fh - 1), fill=255)

    # anel de luz que se expande quando a bandeira termina de virar
    pr = prog(t, 1.45, 2.4)
    if 0 < pr < 1:
        cx, cy = fx + FLAG_W * esc / 2, fy + FLAG_H * esc / 2
        r = (60 + ease_out(pr) * 900) * K
        d = np.abs(np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) - r) / ((18 + 40 * pr) * K)
        anel = np.exp(-d * d) * 120 * (1 - pr)
        a = np.asarray(img, np.float32) + anel[..., None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # ----- texto branco com sombra leve
    tm = camada_texto(t)
    if tm.getbbox():
        sh = tm.filter(ImageFilter.GaussianBlur(6 * K)).point(lambda v: v * 0.45)
        sh = ImageChops.offset(sh, round(3 * K), round(5 * K))
        img = Image.composite(Image.new('RGB', (W, H), (0, 30, 12)), img, sh)
        img = Image.composite(Image.new('RGB', (W, H), BRANCO), img, tm)

    # ----- reflexo de luz que passa sobre o logotipo inteiro
    pb = prog(t, 5.6, 6.7)
    if 0 < pb < 1:
        pos = X0 - 300 * K + pb * (grupo_w + 600 * K)
        d = (xx - pos - (yy - H / 2) * 0.35) / (45 * K)
        faixa = np.exp(-d * d) * 0.75
        alfa = np.maximum(np.asarray(tm, np.float32), np.asarray(flag_mask, np.float32)) / 255.0
        a = np.asarray(img, np.float32)
        a = a + (255 - a) * (faixa * alfa)[..., None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # leve aproximação contínua no final
    z = 1 + 0.035 * ease_in_out(prog(t, 6.0, 10.0))
    if z > 1.0005:
        zw, zh = W / z, H / z
        img = img.resize((W, H), Image.BICUBIC, box=((W - zw) / 2, (H - zh) / 2, (W + zw) / 2, (H + zh) / 2))
    return img

if __name__ == '__main__':
    out = sys.stdout.buffer
    for i in range(N):
        out.write(quadro(i).tobytes())
