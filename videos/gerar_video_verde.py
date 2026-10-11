# Gera a vinheta SEGOV com fundo verde do Estado e escrita em branco.
# Uso: python3 gerar_video_verde.py | ffmpeg -f rawvideo -pix_fmt rgb24 -s 1280x720 -r 30 -i - ... saida.mp4
import sys, os, math, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(AQUI, 'assets')
W, H, FPS, DUR = 1280, 720, 30, 10.0
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
    for k, (t0, larg, forca) in enumerate([(0.0, 260, 38), (0.35, 140, 26), (5.6, 320, 18)]):
        p = prog(t, t0, t0 + 1.6)
        if 0 < p < 1:
            pos = -600 + p * (W + 1200)
            d = (xx + yy * 0.55 - pos) / larg
            bg += (np.exp(-d * d) * forca * math.sin(p * math.pi))[..., None]
    # entrada: escurecido para o verde
    bg *= 0.35 + 0.65 * ease_out(prog(t, 0.0, 1.0))
    return bg

# ---------- elementos ----------
bandeira = Image.open(os.path.join(ASSETS, 'bandeira_sc.png')).convert('RGB')
f_black = ImageFont.truetype(os.path.join(ASSETS, 'Montserrat-Black.ttf'), 168)
f_bold = ImageFont.truetype(os.path.join(ASSETS, 'Montserrat-Bold.ttf'), 40)

TITULO, SUB = 'SEGOV', 'SECRETARIA DE GOVERNO'
asc, desc = f_black.getmetrics()
tb = f_black.getbbox(TITULO)
tit_w, tit_top, tit_h = tb[2] - tb[0], tb[1], tb[3] - tb[1]

# subtítulo com espaçamento entre letras ajustado à largura do título
sub_letras = list(SUB)
larg_sem = sum(f_bold.getlength(c) for c in sub_letras)
track = (tit_w - larg_sem) / (len(sub_letras) - 1)
sb = f_bold.getbbox('S')
sub_h = sb[3] - sb[1]

GAP_LINHA, GAP_SUB = 22, 20
texto_h = tit_h + GAP_LINHA + 4 + GAP_SUB + sub_h
FLAG_H = texto_h
FLAG_W = round(FLAG_H * bandeira.width / bandeira.height)
GAP_FT = 46
grupo_w = FLAG_W + GAP_FT + tit_w
X0 = (W - grupo_w) // 2
Y0 = (H - texto_h) // 2
FX, FY = X0, Y0                       # posição final da bandeira
TX = X0 + FLAG_W + GAP_FT             # x do texto
LINHA_Y = Y0 + tit_h + GAP_LINHA
SUB_Y = LINHA_Y + 4 + GAP_SUB

# letras do título (posição de cada uma, com kerning)
letras = []
for i, c in enumerate(TITULO):
    x = TX - tb[0] + f_black.getlength(TITULO[:i])
    letras.append((c, x))

def camada_texto(t):
    """Desenha título, linha e subtítulo em branco (máscara L) para o instante t."""
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    # título: cada letra sobe de trás de uma "janela" (máscara), em sequência
    for i, (c, x) in enumerate(letras):
        p = ease_out(prog(t, 2.6 + i * 0.11, 3.35 + i * 0.11))
        if p <= 0: continue
        dy = (1 - p) * (tit_h + 30)
        lm = Image.new('L', (W, H), 0)
        ImageDraw.Draw(lm).text((x, Y0 - tit_top + dy), c, font=f_black, fill=int(255 * min(1, p * 1.5)))
        jan = Image.new('L', (W, H), 0)
        ImageDraw.Draw(jan).rectangle((0, 0, W, Y0 + tit_h + 2), fill=255)
        m = ImageChops.lighter(m, ImageChops.multiply(lm, jan))
    d = ImageDraw.Draw(m)
    # linha fina que cresce da esquerda para a direita
    pl = ease_in_out(prog(t, 3.5, 4.3))
    if pl > 0:
        d.rectangle((TX, LINHA_Y, TX + int(tit_w * pl), LINHA_Y + 3), fill=255)
    # subtítulo: revelado por uma cortina suave da esquerda para a direita
    ps = prog(t, 4.0, 5.1)
    if ps > 0:
        sm = Image.new('L', (W, H), 0)
        sd = ImageDraw.Draw(sm)
        x = TX
        sobe = (1 - ease_out(ps)) * 14
        for c in sub_letras:
            sd.text((x, SUB_Y - sb[1] + sobe), c, font=f_bold, fill=255)
            x += f_bold.getlength(c) + track
        frente = TX - 80 + ease_in_out(ps) * (tit_w + 160)
        rampa = np.clip((frente - np.arange(W, dtype=np.float32)) / 80.0, 0, 1)
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
        b = bandeira.resize((fw, fh), Image.LANCZOS)
        # brilho na face durante o giro
        if pf < 1:
            b = Image.blend(b, Image.new('RGB', b.size, BRANCO), 0.45 * (1 - pf))
        bx = int(fx + (FLAG_W * esc - fw) / 2)
        by = int(fy)
        # sombra suave
        sh = Image.new('L', (W, H), 0)
        ImageDraw.Draw(sh).rectangle((bx + 6, by + 10, bx + fw + 6, by + fh + 10), fill=110)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        img = Image.composite(Image.new('RGB', (W, H), (0, 30, 12)), img, sh)
        img.paste(b, (bx, by))
        ImageDraw.Draw(flag_mask).rectangle((bx, by, bx + fw - 1, by + fh - 1), fill=255)

    # anel de luz que se expande quando a bandeira termina de virar
    pr = prog(t, 1.45, 2.4)
    if 0 < pr < 1:
        cx, cy = fx + FLAG_W * esc / 2, fy + FLAG_H * esc / 2
        r = 60 + ease_out(pr) * 900
        d = np.abs(np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) - r) / (18 + 40 * pr)
        anel = np.exp(-d * d) * 120 * (1 - pr)
        a = np.asarray(img, np.float32) + anel[..., None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # ----- texto branco com sombra leve
    tm = camada_texto(t)
    if tm.getbbox():
        sh = tm.filter(ImageFilter.GaussianBlur(6)).point(lambda v: v * 0.45)
        sh = ImageChops.offset(sh, 3, 5)
        img = Image.composite(Image.new('RGB', (W, H), (0, 30, 12)), img, sh)
        img = Image.composite(Image.new('RGB', (W, H), BRANCO), img, tm)

    # ----- reflexo de luz que passa sobre o logotipo inteiro
    pb = prog(t, 5.6, 6.7)
    if 0 < pb < 1:
        pos = X0 - 300 + pb * (grupo_w + 600)
        d = (xx - pos - (yy - H / 2) * 0.35) / 45
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
