#!/usr/bin/env python3
"""
人在讲渲染器（KF 视觉语言 · 两套版式）
=====================================
给「没有定稿 KF 覆盖的抽象段」做人在讲画面，视觉语言严格沿用 gen_keyframes.py：
纸底 #efe9dd / 墨 #2b2722 / 深红 #9e2b25 / 白卡 #fffdf8 / 重黑体。

版式
----
A · 上下结构：方形(或圆形)人像满宽占上半屏，文字排下半屏并垂直居中。
              适合句短字少的过渡段。
B · 角落画中画：人像块放右上角，其余版面排 标题 / 关键句 / 白卡列表 / 底部色条。
              适合内容多的段。

动效（design_principles.md §3）
-------------------------------
入场 20px 上浮 + expoOut，按体量分级 small 0.30s / mid 0.50s / hero 0.80s；
出场 0.25s expoIn（快于入场）；相邻元素 stagger 60ms；同镜切换留 0.10s 硬间隙由 cue 保证。

用法
----
python3 render_kf.py --source clean.mp4 --ss 27.366 --t 4.6 --layout A \
  --content '{"blocks":[{"kind":"label","text":"对甲方来说","t0":0},
                         {"kind":"strike","text":"没人可用","t0":0.97},
                         {"kind":"bigred","text":"选谁","t0":3.03}]}' \
  --out u05.mp4

python3 render_kf.py --source clean.mp4 --ss 32.0 --t 6.5 --layout B \
  --content '{"title":["满市场的人都说","自己能做内容"],"cues":{"title":0,"sub":0},
              "sub":"能带货，能涨粉","sub_t0":2.366,
              "cards":[{"label":"说自己能做","t0":0.5},
                       {"label":"说自己能带货","t0":2.366},
                       {"label":"说自己能涨粉","t0":2.866}],
              "bottom":["你分不清","谁真谁假"],"bottom_t0":4.133}' \
  --out u06.mp4
"""
import argparse, json, math, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30

PAPER = (239, 233, 221)
INK = (43, 39, 34)
RED = (158, 43, 37)
CREAM = (246, 238, 224)
WHITE = (255, 253, 248)
MUT = (111, 103, 84)          # #6f6754 灰字，纸面上 4.64:1

FONT_DIR = "/System/Library/Fonts/Supplemental"
FONTS = {
    "black": os.path.join(FONT_DIR, "NotoSansCJKsc-Black.otf"),
    "bold": os.path.join(FONT_DIR, "NotoSansCJKsc-Bold.otf"),
    "medium": os.path.join(FONT_DIR, "NotoSansCJKsc-Medium.otf"),
}
_cache = {}


def font(kind, size):
    key = (kind, int(size))
    if key not in _cache:
        p = FONTS.get(kind, FONTS["medium"])
        _cache[key] = ImageFont.truetype(p, int(size))
    return _cache[key]


# ---------- 动效曲线（§3.0 只允许这四条）----------
def expoOut(x):
    x = min(1.0, max(0.0, x))
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def expoIn(x):
    x = min(1.0, max(0.0, x))
    return 0.0 if x <= 0 else 2 ** (10 * (x - 1))


DIN = {"small": 0.30, "mid": 0.50, "hero": 0.80}
DOUT = 0.25
RISE = 20


def anim(t, t0, t1, tier="mid", out=True):
    """返回 (alpha, yoff)。t1=None 表示常驻到段尾。"""
    tin = DIN.get(tier, 0.50)
    if t < t0:
        return 0.0, RISE
    if t1 is not None and t > t1:
        p = (t - t1) / DOUT
        if out and p >= 1:
            return 0.0, -RISE * 0.6
        return (1 - expoIn(p)) if out else 1.0, -RISE * 0.6 * (1 - expoIn(p))
    p = (t - t0) / tin
    return expoOut(p), RISE * (1 - expoOut(p))


def col(c, a):
    return (c[0], c[1], c[2], int(255 * max(0.0, min(1.0, a))))


# ---------- 素材 ----------
def person_tile(frame_path, size, shape="square", cx=0.5, cy=0.63, zoom=1.0):
    """从原帧裁出人像块。裁切以「头—颈—肩完整」为准，具体位置由 cx/cy/zoom 按素材定。"""
    im = Image.open(frame_path).convert("RGB")
    sw, sh = im.size
    side = max(64, int(min(sw, sh) * zoom))
    x0 = int(sw * cx - side / 2)
    y0 = int(sh * cy - side / 2)
    x0 = max(0, min(x0, sw - side))
    y0 = max(0, min(y0, sh - side))
    im = im.crop((x0, y0, x0 + side, y0 + side)).resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if shape == "circle":
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        out.paste(im, (0, 0), mask)
    else:
        out.paste(im, (0, 0))
    return out


def paper_bg():
    bg = Image.new("RGBA", (W, H), PAPER + (255,))
    noise = Image.effect_noise((W // 2, H // 2), 9).convert("L").resize((W, H), Image.BILINEAR)
    bg = Image.composite(Image.new("RGBA", (W, H), (255, 255, 255, 255)), bg,
                         noise.point(lambda v: max(0, min(255, int((v - 128) * 0.18 + 128)))))
    return bg


# ---------- 版式 A：上下结构 ----------
A_SIZES = {
    "label": (44, "medium", 66, 22),     # (字号, 字重, 行高, 前置间距)
    "strike": (128, "black", 158, 6),
    "big": (200, "black", 248, 6),
    "bigred": (248, "black", 300, 10),
}


def layout_a(canvas, frame, t, blocks, opts):
    size = W
    tile = person_tile(frame, size, opts["shape"], opts["cx"], opts["cy"], opts["zoom"])
    if opts["shape"] == "circle":
        d = ImageDraw.Draw(canvas)
        cy = size // 2
        d.ellipse([W / 2 - size / 2, cy - size / 2, W / 2 + size / 2, cy + size / 2],
                  outline=INK + (255,), width=8)
    canvas.alpha_composite(tile, (0, 0))
    d = ImageDraw.Draw(canvas)

    # 按 beat 分组：同一拍内元素共用一个垂直居中的版块；
    # 换拍 = 同镜切换，上一拍在下一拍入场前 0.10s 撤净（硬间隙）。
    beats = []
    for b in blocks:
        bid = b.get("beat", 0)
        if not beats or beats[-1][0] != bid:
            beats.append((bid, []))
        beats[-1][1].append(b)
    starts = [min(b.get("t0", 0) for b in items) for _, items in beats]

    area_top, area_h = 1080, H - 1080
    for bi, (bid, items) in enumerate(beats):
        bstart = starts[bi]
        bend = (starts[bi + 1] - 0.10) if bi + 1 < len(starts) else None
        if t < bstart - 0.02 or (bend is not None and t > bend + DOUT):
            continue
        laid = []
        for b in items:
            fs0, fk, lh0, gap = A_SIZES[b.get("kind", "label")]
            fs = b.get("size", fs0)
            lines = b["text"].split("\n")
            laid.append((b, fs, fk, fs * 0 + lh0 * len(lines), gap))
        total = sum(x[3] + x[4] for x in laid)
        y = area_top + (area_h - total) / 2
        for b, fs, fk, h, gap in laid:
            y += gap
            a, off = anim(t, b.get("t0", 0), bend, b.get("tier", "mid"))
            if a > 0:
                f = font(fk, fs)
                kind = b.get("kind", "label")
                color = b.get("color")
                if kind == "strike":
                    c = MUT
                elif kind == "bigred":
                    c = RED
                else:
                    c = INK if not color else color
                lh = A_SIZES[kind][2]
                for i, ln in enumerate(b["text"].split("\n")):
                    tw = d.textlength(ln, font=f)
                    tx = (W - tw) / 2
                    ty = y + off + i * lh
                    d.text((tx, ty), ln, font=f, fill=col(c, a))
                    if kind == "strike" and i == 0:
                        sy = ty + fs * 0.55
                        d.rectangle([tx - 6, sy, tx + tw + 6, sy + max(8, fs * 0.07)],
                                    fill=col((140, 130, 112), a * 0.85))
            y += h


# ---------- 版式 B：角落画中画 ----------
def layout_b(canvas, frame, t, c, opts):
    d = ImageDraw.Draw(canvas)
    S, M = 440, 60
    x0 = W - M - S
    tile = person_tile(frame, S, opts["shape"], opts["cx"], opts["cy"], opts["zoom"])
    if opts["shape"] == "circle":
        canvas.alpha_composite(tile, (x0, M))
        d.ellipse([x0, M, x0 + S, M + S], outline=INK + (255,), width=6)
    else:
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=24, fill=255)
        canvas.alpha_composite(Image.composite(tile, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask),
                               (x0, M))

    # 标题（左栏，与方窗同起）
    t0 = c.get("cues", {}).get("title", 0)
    tsize = c.get("title_size", 88)
    tlh = int(tsize * 1.18)
    y = 112
    for i, ln in enumerate(c.get("title", [])):
        a, off = anim(t, t0 + i * 0.06, None, "mid")
        if a > 0:
            f = font("black", tsize)
            d.text((M, y + off), ln, font=f, fill=col(INK, a))
        y += tlh

    # 关键句（深红）
    sub = c.get("sub")
    if sub:
        a, off = anim(t, c.get("sub_t0", 0), None, "mid")
        if a > 0:
            d.text((M + 4, y + 18 + off), sub, font=font("black", 52), fill=col(RED, a))
        y += 92

    # 白卡列表：左标签 + 右判词，卡片撑满整宽
    cards = c.get("cards", [])
    cy0, chh, gap = 600, 250, 62
    for i, card in enumerate(cards):
        a, off = anim(t, card.get("t0", 0), None, "mid")
        if a <= 0:
            continue
        yy = cy0 + i * (chh + gap) + off
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([M, yy, W - M, yy + chh], radius=18, fill=col(WHITE, a))
        # 右侧「判定」色块：用色块分组填掉中段空洞，不画细线
        xr = W - M - 300
        tint = (158, 43, 37, int(255 * a * 0.08))
        ld.rounded_rectangle([xr, yy, W - M, yy + chh], radius=18, fill=tint)
        ld.rectangle([xr, yy, xr + 24, yy + chh], fill=tint)
        ld.text((M + 40, yy + chh / 2), card["label"], font=font("medium", 56),
                fill=col((43, 39, 34), a), anchor="lm")
        ld.text((xr + (W - M - xr) / 2, yy + chh / 2), card.get("verdict", "凭什么？"),
                font=font("black", 56), fill=col(RED, a), anchor="mm")
        canvas.alpha_composite(layer)

    # 底部整块深红条
    bottom = c.get("bottom")
    if bottom:
        a, off = anim(t, c.get("bottom_t0", 0), None, "mid")
        if a > 0:
            bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            bd = ImageDraw.Draw(bar)
            bd.rectangle([0, 1560 + off, W, H + off], fill=col(RED, a))
            bh = len(bottom) * 112
            by = 1560 + off + (H - 1560 - bh) / 2
            for ln in bottom:
                tw = bd.textlength(ln, font=font("black", 92))
                bd.text(((W - tw) / 2, by), ln, font=font("black", 92), fill=col(CREAM, a))
                by += 112
            canvas.alpha_composite(bar)


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="干净版源片（无烧录字幕）")
    ap.add_argument("--ss", type=float, required=True)
    ap.add_argument("--t", type=float, required=True)
    ap.add_argument("--out", default=None, help="输出 mp4（--preview 时可省）")
    ap.add_argument("--layout", choices=["A", "B"], default="B")
    ap.add_argument("--content", required=True, help="版式内容 JSON")
    ap.add_argument("--shape", choices=["square", "circle"], default="square")
    ap.add_argument("--cx", type=float, default=0.5)
    ap.add_argument("--cy", type=float, default=0.63)
    ap.add_argument("--zoom", type=float, default=0.95)
    ap.add_argument("--preview", action="store_true", help="只出一张静态图")
    ap.add_argument("--pt", type=float, default=1.0)
    ap.add_argument("--preview-out", default=None)
    a = ap.parse_args()

    c = json.loads(a.content)
    opts = dict(shape=a.shape, cx=a.cx, cy=a.cy, zoom=a.zoom)
    n = int(round(a.t * FPS))

    if a.preview:
        tmp = tempfile.mkdtemp()
        fp = os.path.join(tmp, "f.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(a.ss + a.pt),
                        "-i", a.source, "-frames:v", "1", fp], check=True)
        canvas = paper_bg()
        if a.layout == "A":
            layout_a(canvas, fp, a.pt, c.get("blocks", []), opts)
        else:
            layout_b(canvas, fp, a.pt, c, opts)
        out = a.preview_out or "preview.png"
        canvas.convert("RGB").save(out)
        print("preview ->", out)
        shutil.rmtree(tmp, ignore_errors=True)
        return

    work = tempfile.mkdtemp(prefix="kf_")
    raw = os.path.join(work, "raw")
    seq = os.path.join(work, "seq")
    os.makedirs(raw, exist_ok=True)
    os.makedirs(seq, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(a.ss), "-t", str(a.t),
                    "-i", a.source, "-vf", f"fps={FPS}", "-q:v", "2",
                    os.path.join(raw, "%04d.jpg")], check=True)
    frames = sorted(os.listdir(raw))
    frames = frames[:n]
    bg = paper_bg()
    for i, fn in enumerate(frames):
        canvas = bg.copy()
        t = i / FPS
        fp = os.path.join(raw, fn)
        if a.layout == "A":
            layout_a(canvas, fp, t, c.get("blocks", []), opts)
        else:
            layout_b(canvas, fp, t, c, opts)
        canvas.convert("RGB").save(os.path.join(seq, f"{i:04d}.png"))
    print(f"frames {len(frames)}")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-framerate", str(FPS), "-i", os.path.join(seq, "%04d.png"),
                    "-ss", str(a.ss), "-t", str(a.t), "-i", a.source,
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", a.out], check=True)
    shutil.rmtree(work, ignore_errors=True)
    print("->", a.out)


if __name__ == "__main__":
    main()
