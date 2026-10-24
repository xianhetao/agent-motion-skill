#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文字动画渲染器（满屏风格 + 按口播时序元素入场/退场）。

动效参数严格遵守 agent-motion/references/design_principles.md §3（对齐 huashu-motion 动画系统）：
  - 曲线只用 expoOut(默认) / overshoot / expoIn / linear
  - 入场位移 20px 上浮 + expoOut；tier 分级时长 small300/mid500/hero800ms
  - 出场 250ms 快于入场；淡出先于运动清零（70% 处 alpha=0）
  - 段尾常驻元素硬切、不淡出；同镜元素交接由 scene 编排保证 0.10s 硬间隙
  - 可 mux 原片对应段音轨
"""
import argparse, json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

FONTS = {
    "black": "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Black.otf",
    "bold":  "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Bold.otf",
    "medium":"/System/Library/Fonts/Supplemental/NotoSansCJKsc-Medium.otf",
}
W, H = 1080, 1920
FPS = 30

# ---------- 运动曲线库（design_principles.md §3.0，只用这 4 条）----------
def expoOut(t):
    t = max(0.0, min(1.0, t))
    return 0.0 if t == 0 else 1 - 2 ** (-10 * t)

def expoIn(t):
    t = max(0.0, min(1.0, t))
    return 0.0 if t == 1 else 2 ** (10 * (t - 1))

def linear(t):
    return max(0.0, min(1.0, t))

def backOut(t):  # 近似 overshoot cubic-bezier(0.34,1.56,0.64,1)
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

EASES = {"expoOut": expoOut, "expoIn": expoIn, "linear": linear, "overshoot": backOut}
TIER_DUR = {"small": 0.30, "mid": 0.50, "hero": 0.80}  # §3.1 入场时长字典
RISE = 20          # §3.2 入场位移 20px
DOUT = 0.25        # §3.3 出场 250ms（快于入场）

def alpha_of(e, t, dur):
    t0, t1 = e["t0"], e["t1"]
    din = TIER_DUR.get(e.get("tier", "mid"), 0.50)
    if t < t0 or t > t1:
        return 0.0
    tail = (t1 >= dur - 0.02)  # 段尾常驻 → 硬切，不淡出（§3.4/§3.7）
    if t < t0 + din:
        return expoOut((t - t0) / din)
    if (not tail) and t > t1 - DOUT:
        return 1 - expoIn((t - (t1 - DOUT)) / DOUT)  # 淡出先于运动清零
    return 1.0

def yoff_of(e, t, dur):
    t0 = e["t0"]
    din = TIER_DUR.get(e.get("tier", "mid"), 0.50)
    anim = e.get("anim", "fade")
    ease = backOut if anim in ("pop", "impact") else expoOut
    if t < t0:
        return RISE
    if t < t0 + din:
        return RISE * (1 - ease((t - t0) / din))
    t1 = e["t1"]
    tail = (t1 >= dur - 0.02)
    if (not tail) and t > t1 - DOUT:
        # 带位移出场：继续上移消失，alpha 已在 70% 处归零
        return -RISE * expoOut((t - (t1 - DOUT)) / DOUT)
    return 0

def font(weight, sz):
    return ImageFont.truetype(FONTS[weight], sz)

def hexa(hexc, a):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, int(a))

def draw_multiline(d, cx, top, lines, f, fg, alpha, lh, align="center"):
    y = top
    for ln in lines:
        tw = d.textlength(ln, font=f)
        x = cx - tw / 2 if align == "center" else cx
        d.text((x, y), ln, font=f, fill=hexa(fg, alpha))
        y += lh

def render(scene, out_mp4, audio=None, ss=None, t=None):
    dur = scene["dur"]
    bgc = BGS.get(scene.get("bg", "paper"), "#f2efe6")
    elems = scene["elems"]
    n = int(dur * FPS) + 2
    tmp = tempfile.mkdtemp(prefix="anim_")
    for i in range(n):
        tcur = i / FPS
        img = Image.new("RGB", (W, H), bgc)
        d = ImageDraw.Draw(img)
        for dec in scene.get("decos", []):
            draw_deco(d, dec, tcur, dur)
        for e in elems:
            draw_elem(d, e, tcur, dur)
        img.save(os.path.join(tmp, f"f{i:04d}.png"))
    vtmp = os.path.join(tmp, "v.mp4")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i",
                    os.path.join(tmp, "f%04d.png"), "-c:v", "libx264",
                    "-crf", "20", "-pix_fmt", "yuv420p", vtmp], check=True)
    if audio and ss is not None and t is not None:
        atmp = os.path.join(tmp, "a.m4a")
        subprocess.run(["ffmpeg", "-y", "-ss", str(ss), "-i", audio, "-t", str(t),
                        "-vn", "-c:a", "aac", "-b:a", "192k", atmp], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", vtmp, "-i", atmp,
                        "-c:v", "copy", "-c:a", "copy", "-shortest", out_mp4], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", vtmp, "-c:v", "copy", out_mp4], check=True)
    print("OK ->", out_mp4)

def draw_deco(d, dec, t, dur):
    a = alpha_of(dec, t, dur)
    if a <= 0:
        return
    typ = dec.get("type")
    if typ == "block":
        x, y, w, h = dec["box"]
        d.rounded_rectangle([x, y, x + w, y + h], radius=dec.get("r", 18), fill=hexa(dec["fill"], a))
    elif typ == "divider":
        y = dec["y"]
        d.rectangle([60, y, W - 60, y + dec.get("h", 6)], fill=hexa(dec["fill"], a))

def draw_elem(d, e, t, dur):
    a = alpha_of(e, t, dur)
    if a <= 0:
        return
    yo = int(yoff_of(e, t, dur))
    typ = e["type"]
    fg = e.get("fg", "#2b2722")
    if typ == "line":
        f = font(e.get("weight", "bold"), e.get("size", 60))
        cx = e.get("x", W / 2)
        top = e.get("y", 600) + yo
        draw_multiline(d, cx, top, e["text"] if isinstance(e["text"], list) else [e["text"]],
                       f, fg, int(255 * a), int(f.size * 1.25), e.get("align", "center"))
    elif typ == "title":
        f = font(e.get("weight", "black"), e.get("size", 140))
        cx = e.get("x", W / 2)
        top = e.get("y", 360) + yo
        draw_multiline(d, cx, top, e["lines"], f, fg, int(255 * a),
                       int(e.get("lh", f.size * 1.05)), e.get("align", "center"))
    elif typ == "kwblock":
        f = font(e.get("weight", "black"), e.get("size", 64))
        text = e["text"]
        tw = d.textlength(text, font=f)
        pad = 40
        bw = tw + pad * 2
        bh = e.get("size", 64) + pad
        bx = (W - bw) / 2
        by = e.get("y", 1300) + yo
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=22, fill=hexa(e.get("bg", "#9e2b25"), a))
        d.text((bx + pad, by + (bh - e["size"]) / 2), text, font=f, fill=hexa(e.get("fg", "#ffffff"), a))
    elif typ == "number":
        f = font(e.get("weight", "black"), e.get("size", 120))
        text = e["text"]
        tw = d.textlength(text, font=f)
        x = (W - tw) / 2
        y = e.get("y", 700) + yo
        d.text((x, y), text, font=f, fill=hexa(fg, int(255 * a)))

BGS = {
    "paper": "#f2efe6",
    "mag":   "#f5f3ef",
    "book":  "#f3ecdc",
    "dark":  "#16181d",
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--ss", type=float, default=None)
    ap.add_argument("--t", type=float, default=None)
    args = ap.parse_args()
    scene = json.load(open(args.scene, encoding="utf-8"))
    render(scene, args.out, args.audio, args.ss, args.t)

if __name__ == "__main__":
    main()
