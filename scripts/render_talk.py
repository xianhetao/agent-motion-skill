#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人在讲段渲染器：原片全屏 + PIL 渲染的透明关键字层（按口播时序淡入淡出）+ 可选底部烧录字幕弱化遮罩。
解决 ffmpeg drawtext 读 Noto OTC 字体缺字（筛/给 变方框）的问题。

用法:
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 --out OUT.mp4 \
    --kws '[{"text":"有人替你筛过一遍","t0":0,"t1":4.5},...]' \
    [--mask 1]   # 是否弱化底部烧录字幕
"""
import argparse, json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Bold.otf"
FONT_BLACK = "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Black.otf"
FPS = 30
W, H = 1080, 1920

# ---- 运动曲线库（对齐 design_principles.md §3.0，只用 expoOut/expoIn）----
def expoOut(t):
    t = max(0.0, min(1.0, t))
    return 0.0 if t == 0 else 1 - 2 ** (-10 * t)

def expoIn(t):
    t = max(0.0, min(1.0, t))
    return 0.0 if t == 1 else 2 ** (10 * (t - 1))

DIN = 0.30    # 入场 300ms（关键词层 small 档，§3.1）
DOUT = 0.25   # 出场 250ms，快于入场（§3.3）
RISE = 20     # 入场位移 20px 上浮（§3.2）

def kw_alpha(kw, t):
    t0, t1 = kw["t0"], kw["t1"]
    if t < t0 or t > t1:
        return 0.0
    if t < t0 + DIN:
        return expoOut((t - t0) / DIN)
    if t > t1 - DOUT:
        return 1 - expoIn((t - (t1 - DOUT)) / DOUT)
    return 1.0

def kw_yoff(kw, t):
    t0 = kw["t0"]
    if t < t0:
        return RISE
    if t < t0 + DIN:
        return RISE * (1 - expoOut((t - t0) / DIN))
    t1 = kw["t1"]
    if t > t1 - DOUT:
        return -RISE * expoOut((t - (t1 - DOUT)) / DOUT)
    return 0

def font(path, sz):
    return ImageFont.truetype(path, sz)

def render_layer(dur, kws, outdir):
    n = int(dur * FPS) + 2
    os.makedirs(outdir, exist_ok=True)
    for i in range(n):
        t = i / FPS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for kw in kws:
            a = kw_alpha(kw, t)
            if a <= 0:
                continue
            alpha = int(255 * a)
            yoff = int(kw_yoff(kw, t))
            text = kw["text"]
            fs = kw.get("size", 72)
            f = font(FONT_BLACK, fs)
            tw = d.textlength(text, font=f)
            pad_x, pad_y = 44, 22
            bw = tw + pad_x * 2
            bh = fs + pad_y * 2
            bx = (W - bw) / 2
            by = kw.get("y", 360) + yoff
            d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=26,
                                fill=(0, 0, 0, int(0.42 * alpha)))
            tx = (W - tw) / 2
            ty = by + (bh - fs) / 2
            d.text((tx, ty), text, font=f, fill=(255, 255, 255, alpha),
                   stroke_width=4, stroke_fill=(0, 0, 0, alpha))
        img.save(os.path.join(outdir, f"f{i:04d}.png"))

def run(cmd):
    print("+", " ".join(cmd[:6]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--ss", type=float, required=True)
    ap.add_argument("--t", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--kws", required=True, help="json list")
    ap.add_argument("--mask", type=int, default=0, help="弱化底部烧录字幕")
    args = ap.parse_args()

    kws = json.loads(args.kws)
    tmp = tempfile.mkdtemp(prefix="talk_")
    base = os.path.join(tmp, "base.mp4")
    layerdir = os.path.join(tmp, "layer")
    layer_mov = os.path.join(tmp, "layer.mov")

    # 1) 切原片片段(全屏, 含原声)
    vf = "scale=1080:1920"
    if args.mask:
        vf += ",drawbox=x=0:y=1520:w=1080:h=300:color=black@0.5:t=fill"
    run(["ffmpeg", "-y", "-ss", str(args.ss), "-i", args.source, "-t", str(args.t),
         "-vf", vf, "-c:v", "libx264", "-crf", "18", "-c:a", "copy", base])

    # 2) PIL 渲染透明关键字层 -> PNG序列 -> 带alpha的mov
    render_layer(args.t, kws, layerdir)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(layerdir, "f%04d.png"),
         "-c:v", "qtrle", layer_mov])

    # 3) overlay 合成
    run(["ffmpeg", "-y", "-i", base, "-i", layer_mov,
         "-filter_complex", "[1:v]format=rgba[ol];[0:v][ol]overlay=0:0:format=auto[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "copy", args.out])
    print("OK ->", args.out)

if __name__ == "__main__":
    main()
