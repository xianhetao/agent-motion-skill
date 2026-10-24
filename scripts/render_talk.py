#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人在讲段渲染器（灵活构图版）：原片可全屏、也可缩放进九宫格某格 + 背景补位；
关键字落位按人在九宫格的位置灵活决定（pos: top/bottom/left/right/center）。
PIL 渲染透明关键字层（20px expoOut 上浮 + 0.10s 硬间隙）+ ffmpeg 合成原片 + 原声。

用法:
  # 视频模式（默认）：原片全屏、关键字默认钉顶部
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 --out OUT.mp4 \
    --kws '[{"text":"有人替你筛过一遍","t0":0,"t1":4.4,"pos":"bottom"},...]'

  # 九宫格构图：原片放下半屏、纸面背景补位、关键字放上半
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 --out OUT.mp4 \
    --box 0,980,1080,940 --bg "#f2f1ec" \
    --kws '[{"text":"有人替你筛过一遍","t0":0,"t1":4.4,"pos":"top"},...]'

  # 预览模式：只出一张静态合成图（原片落位+关键字位置），给用户确认构图，不渲染视频
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 \
    --box 0,980,1080,940 --bg "#f2f1ec" \
    --kws '[{"text":"有人替你筛过一遍","t0":0,"t1":4.4,"pos":"top"}]' \
    --preview --pt 0.5 --preview-out preview.png
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

# ---- 参数解析 ----
def parse_box(s):
    x, y, w, h = map(int, s.split(","))
    return x, y, w, h

def parse_bg_hex(s):
    """#rrggbb 或 r,g,b -> ffmpeg 用的 0xrrggbb"""
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    elif "," in s:
        r, g, b = map(int, s.split(","))
        s = "%02x%02x%02x" % (r, g, b)
    return "0x" + s.lower()

def parse_bg_rgb(s):
    """#rrggbb 或 r,g,b -> (r,g,b)"""
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    elif "," in s:
        r, g, b = map(int, s.split(","))
        return (r, g, b)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))

def kw_layout(kw, fs, tw, bh):
    """按 pos 决定关键字块位置（相对整幅 1080x1920）"""
    pos = kw.get("pos", "top")
    bw = tw + 88
    if pos in ("left", "right"):
        by = (H - bh) / 2
        bx = 120 if pos == "left" else (W - bw - 120)
    else:
        bx = (W - bw) / 2
        if pos == "top":
            by = 140
        elif pos == "bottom":
            by = H - bh - 140
        else:  # center
            by = (H - bh) / 2
    return bx, by

# ---- 关键字层（单帧）----
def render_layer_frame(t, kws):
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
        bx, by = kw_layout(kw, fs, tw, bh)
        by += yoff
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=26,
                            fill=(0, 0, 0, int(0.42 * alpha)))
        tx = bx + pad_x
        ty = by + (bh - fs) / 2
        d.text((tx, ty), text, font=f, fill=(255, 255, 255, alpha),
               stroke_width=4, stroke_fill=(0, 0, 0, alpha))
    return img

def render_layer_seq(dur, kws, outdir):
    n = int(dur * FPS) + 2
    os.makedirs(outdir, exist_ok=True)
    for i in range(n):
        render_layer_frame(i / FPS, kws).save(os.path.join(outdir, f"f{i:04d}.png"))

# ---- 原片构图（视频模式 base）----
def build_base(source, ss, t, box, bg_hex, crop_path, base_path):
    x, y, bw, bh = box
    if bw == W and bh == H and x == 0 and y == 0:
        run(["ffmpeg", "-y", "-ss", str(ss), "-i", source, "-t", str(t),
             "-vf", f"scale={W}:{H}", "-c:v", "libx264", "-crf", "18",
             "-an", base_path])
    else:
        if not bg_hex:
            sys.exit("box 非全屏时必须传 --bg（背景补位色）")
        scale = (f"scale=w='if(lt(iw/ih,{bw}/{bh}),{bw},-2)':"
                 f"h='if(lt(iw/ih,{bw}/{bh}),-2,{bh})'")
        pad = f"pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color={bg_hex}"
        run(["ffmpeg", "-y", "-ss", str(ss), "-i", source, "-t", str(t),
             "-vf", f"{scale},{pad}", "-c:v", "libx264", "-crf", "18", "-an", crop_path])
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={bg_hex}:s={W}x{H}:d={t}",
             "-i", crop_path,
             "-filter_complex", f"[1:v]overlay={x}:{y}[v]",
             "-map", "[v]", "-c:v", "libx264", "-crf", "18", "-an", base_path])

def run(cmd):
    print("+", " ".join(cmd[:6]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        sys.exit(1)

# ---- 预览模式（静态合成图）----
def build_preview(source, ss, pt, box, bg_rgb, kws, out_png):
    x, y, bw, bh = box
    tmp = tempfile.mkdtemp(prefix="talkprev_")
    frame = os.path.join(tmp, "frame.png")
    run(["ffmpeg", "-y", "-ss", f"{ss + pt:.3f}", "-i", source, "-frames:v", "1", frame])
    im = Image.open(frame).convert("RGB")
    iw, ih = im.size
    r = min(bw / iw, bh / ih)
    sw, sh = int(iw * r), int(ih * r)
    resized = im.resize((sw, sh), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), bg_rgb if bg_rgb else (0, 0, 0))
    canvas.paste(resized, ((bw - sw) // 2 + x, (bh - sh) // 2 + y))
    layer = render_layer_frame(pt, kws).convert("RGBA")
    canvas = Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
    canvas.save(out_png)
    print("PREVIEW ->", out_png)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--ss", type=float, required=True)
    ap.add_argument("--t", type=float, required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--kws", required=True, help="json list, 每项可带 pos(top/bottom/left/right/center)")
    ap.add_argument("--box", default="0,0,1080,1920", help="原片在输出画面的区域 x,y,w,h")
    ap.add_argument("--bg", default=None, help="背景补位色 #rrggbb 或 r,g,b（box 非全屏必填）")
    ap.add_argument("--preview", action="store_true", help="只出静态预览图，不渲染视频")
    ap.add_argument("--pt", type=float, default=0.5, help="预览时刻（秒）")
    ap.add_argument("--preview-out", default="preview.png")
    args = ap.parse_args()

    kws = json.loads(args.kws)
    box = parse_box(args.box)
    bg_hex = parse_bg_hex(args.bg) if args.bg else None
    bg_rgb = parse_bg_rgb(args.bg) if args.bg else None

    if args.preview:
        build_preview(args.source, args.ss, args.pt, box, bg_rgb, kws, args.preview_out)
        return

    if not args.out:
        sys.exit("--out 必填（非预览模式）")

    tmp = tempfile.mkdtemp(prefix="talk_")
    crop = os.path.join(tmp, "crop.mp4")
    base = os.path.join(tmp, "base.mp4")
    layerdir = os.path.join(tmp, "layer")
    layer_mov = os.path.join(tmp, "layer.mov")

    # 1) 原片构图 -> base（无声）
    build_base(args.source, args.ss, args.t, box, bg_hex, crop, base)
    # 2) PIL 透明关键字层 -> PNG序列 -> 带alpha的mov
    render_layer_seq(args.t, kws, layerdir)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(layerdir, "f%04d.png"),
         "-c:v", "qtrle", layer_mov])
    # 3) overlay 关键字 + mux 原声
    run(["ffmpeg", "-y", "-i", base, "-i", layer_mov, "-ss", str(args.ss), "-i", args.source,
         "-t", str(args.t),
         "-filter_complex", "[1:v]format=rgba[ol];[0:v][ol]overlay=0:0:format=auto[v]",
         "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", args.out])
    print("OK ->", args.out)

if __name__ == "__main__":
    main()
