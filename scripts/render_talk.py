#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人在讲段渲染器（九宫格灵活构图 + 画中画版）
=========================================
⚠️ 视觉基准：**已有定稿关键帧（KF1–KF6）的段落不得用本脚本另造版式**，直接用那张 KF。
   本脚本只服务「没有 KF 覆盖的抽象段落」，且版式须沿用 KF 语言（纸底/墨/深红/白卡/色条），
   见 references/design_principles.md §2.1 铁律与 §2.1.1/§2.1.2。
   `--list`（编号论点列表）为早期实验版式，**默认不要用**，仅当用户明确要求时启用。

设计规则（design_principles.md §2.1「人在讲构图」）：
  原片在视频里等价于图文排版里的「图片」，占哪个九宫格格由构图决定。
  - 先看人物在素材里的九宫格位置（person-pos）与「是否有空间放字」：
      * 人物占满全帧（近景大特写、无空白）→ 只能做【画中画】：把口播裁成
        圆形或方形小窗放进某一格，纸面/底色补位，关键字补到对侧空格（保持平衡）。
      * 人物偏在一侧、同帧有空白 → 可【叠加】：原片做底，关键字补空白侧。
  - 关键字落位 = 人物格的对侧/对角（center->bottom / left->right / top->bottom ...）。
  - 关键字样式统一走编辑风（见 style_reference 调色板）：墨色重黑体 + 深红短饰条，
    不出现黑底白字胶囊；背景为纸面/底色，与 KF 系列视觉一致。
  - 渲染前先出 --preview 静态确认图（带九宫格叠层，标注人物格 P 与字幕格 K）。

PIL 逐帧合成（原片帧 + 画中画窗/关键字层）+ ffmpeg 编码 + 原声 mux。

用法:
  # 画中画（全帧特写素材）：口播裁成圆形窗放右侧，纸面补位，关键字自动补左侧
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 --out OUT.mp4 \
    --pip circle --pip-cell right --bg "#f2f1ec" \
    --kws '[{"text":"有人替你筛过一遍","t0":0,"t1":4.4},...]'

  # 叠加（人物偏一侧、有空白）：原片全帧做底，关键字补对侧空白
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 --out OUT.mp4 \
    --person-pos left --kws '[{"text":"..."}]'

  # 预览（静态确认图，带九宫格叠层）
  python3 render_talk.py --source SRC --ss 9.8 --t 9.7 --pip circle --pip-cell right \
    --bg "#f2f1ec" --kws '[{"text":"有人替你筛过一遍"}]' \
    --preview --pt 2 --preview-out preview.png
"""
import argparse, json, math, os, subprocess, sys, tempfile, glob
from PIL import Image, ImageDraw, ImageFont

FONT_BLACK = "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Black.otf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Bold.otf"
FPS = 30
W, H = 1080, 1920

# ---- 编辑风调色板（源自 style_reference.md 已验证调色板）----
PAPER = (242, 241, 236)      # #f2f1ec 纸面
PAPER2 = (245, 240, 230)     # #f5f0e6 浅米
INK = (43, 39, 34)           # #2b2722 墨
DEEP_RED = (158, 43, 37)     # #9e2b25 报刊深红
AMBER = (143, 95, 18)        # #8f5f12 深琥珀

# ---- 运动曲线库（对齐 design_principles.md §3.0）----
def expoOut(t):
    t = max(0.0, min(1.0, t))
    return 0.0 if t == 0 else 1 - 2 ** (-10 * t)

def expoIn(t):
    t = max(0.0, min(1.0, t))
    return 0.0 if t == 1 else 2 ** (10 * (t - 1))

DIN = 0.30    # 入场 300ms
DOUT = 0.25   # 出场 250ms
RISE = 20     # 20px 上浮

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

# ---- 九宫格逻辑 ----
PERSON_OPP = {
    "center": "bottom", "left": "right", "right": "left",
    "top": "bottom", "bottom": "top",
    "tl": "br", "tr": "bl", "bl": "tr", "br": "tl",
}
CELL_NAMES = ["tl", "top", "tr", "left", "center", "right", "bl", "bottom", "br"]

def cell_rect(name, m=56):
    if name == "bottom":  return (m, H * 0.60, W - m, H - m)
    if name == "top":     return (m, m, W - m, H * 0.40)
    # 左右半栏：中间留 56px 栏间距，便于「一图一文」分栏排布
    if name == "left":    return (m, m, W * 0.5 - 28, H - m)
    if name == "right":   return (W * 0.5 + 28, m, W - m, H - m)
    if name == "center":  return (m, H * 0.38, W - m, H * 0.62)
    cw, ch = W * 0.5, H * 0.5
    corners = {
        "tl": (m, m, m + cw, m + ch),
        "tr": (W - cw - m, m, W - m, m + ch),
        "bl": (m, H - ch - m, m + cw, H - m),
        "br": (W - cw - m, H - ch - m, W - m, H - m),
    }
    return corners[name]

# ---- 参数解析 ----
def parse_bg_rgb(s):
    s = s.strip()
    if s.startswith("#"): s = s[1:]
    elif "," in s:
        r, g, b = map(int, s.split(",")); return (r, g, b)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))

# ---- 关键字块（编辑风：多行大字 + 栏目标记竖条）----
def split_lines(text, colw, fs_max=118):
    """按列宽把关键字折成 2-3 行大字，让文字块有体量、撑满所在栏。
    显式 `\\n` 优先（人工断行最稳，不从词中间切）。"""
    if "\n" in text:
        lines = [l for l in text.split("\n") if l]
        longest = max(len(l) for l in lines)
        fs = int(min(fs_max, colw / longest))
        return fs, lines
    n = len(text)
    for k in (2, 3):
        per = math.ceil(n / k)
        fs = int(min(fs_max, colw / per))
        if fs >= 66:
            return fs, [text[i:i + per] for i in range(0, n, per)]
    return int(min(fs_max, colw / max(1, n))), [text]

def draw_keyword_block(canvas, kws, kw_cell, t, shadow):
    rx0, ry0, rx1, ry1 = cell_rect(kw_cell)
    d = ImageDraw.Draw(canvas)
    for kw in kws:
        a = kw_alpha(kw, t)
        if a <= 0:
            continue
        alpha = int(255 * a)
        yoff = int(kw_yoff(kw, t))
        col = kw.get("color", INK)
        acc = kw.get("accent", DEEP_RED)
        avail = (rx1 - rx0) - 96          # 左侧留出竖条位置
        fs, lines = split_lines(kw["text"], avail, kw.get("size", 118))
        f = font(FONT_BLACK, fs)
        lh = int(fs * 1.14)
        block_h = lh * len(lines)
        cx = (rx0 + rx1) / 2 + 14          # 视觉重心略右移，给竖条让位
        mid_y = (ry0 + ry1) / 2 + yoff
        top = mid_y - block_h / 2
        # 深红竖条贯穿整块（栏目标记，编辑风锚点）
        sbx = rx0 + 8
        d.rectangle([sbx, top + 6, sbx + 12, top + block_h - 6],
                    fill=(acc[0], acc[1], acc[2], alpha))
        for i, ln in enumerate(lines):
            tw = d.textlength(ln, font=f)
            tx = cx - tw / 2
            ty = top + i * lh + (lh - fs) / 2
            if shadow:
                d.text((tx + 4, ty + 4), ln, font=f, fill=(0, 0, 0, int(0.5 * alpha)))
            d.text((tx, ty), ln, font=f, fill=(col[0], col[1], col[2], alpha))

# ---- 整段关键词堆叠（论点列表：当前词高亮，其余压灰；撑着左栏不空）----
MUTED = (122, 114, 100)   # #7a7264 未激活词（纸面上约 4.6:1）

def draw_keyword_list(canvas, kws, kw_cell, t, groups, span=None):
    """groups: 整段 2-4 个论点，每项可含 \\n；kws 用 idx+t0/t1 指定当前激活项。
    span=(y0,y1)：可选，把列表上下均分到该区间（用于与人物窗等高对齐，
    避免一侧撑满、另一侧堆在中间导致画面失衡）。
    版面 = 编辑风「编号 + 论点」列表：序号定锚、当前项墨色实显 + 深红序号，
    其余压灰但保持可读。常驻结构列表（三点列表属结构性上下文，规范允许），
    激活项随口播推进切换 = 天然动画，无需硬间隙。"""
    rx0, ry0, rx1, ry1 = cell_rect(kw_cell)
    d = ImageDraw.Draw(canvas)
    avail = (rx1 - rx0) - 84
    all_lines = [l for g in groups for l in g.split("\n") if l]
    longest = max(len(l) for l in all_lines)
    fs = int(min(124, avail / longest))
    f = font(FONT_BLACK, fs)
    fnum = font(FONT_BOLD, max(28, int(fs * 0.32)))
    lh = int(fs * 1.10)
    numh = int(fs * 0.52)          # 序号行高
    hs = [numh + len(g.split("\n")) * lh for g in groups]
    n = len(groups)
    if span:
        y0, y1 = span
        body = y1 - y0
        # 间距设上限：宁可整块居中留边，也不能把三段拉散（相邻成组原则）
        gap = min(int(lh * 1.7), max(int(lh * 0.9), int((body - sum(hs)) / max(1, n - 1))))
        total = sum(hs) + gap * (n - 1)
        top = y0 + (body - total) / 2
    else:
        gap = int(lh * 0.95)
        total = sum(hs) + gap * (n - 1)
        top = (ry0 + ry1) / 2 - total / 2
    maxw = max(d.textlength(l, font=f) for l in all_lines)
    cx = (rx0 + rx1) / 2 + 8
    block_left = cx - maxw / 2
    num_x = max(rx0 + 6, block_left - 66)

    active = None
    for kw in kws:
        if kw.get("idx") is not None and kw["t0"] <= t <= kw["t1"]:
            active = kw["idx"]
    yoff = 0
    if active is not None:
        cur = next((k for k in kws if k.get("idx") == active), None)
        if cur and t < cur["t0"] + DIN:
            yoff = int(RISE * (1 - expoOut((t - cur["t0"]) / DIN)))

    y = top + yoff
    for i, g in enumerate(groups):
        lines = g.split("\n")
        on = (i == active)
        col, al = (INK, 255) if on else (MUTED, 205 if (active is None or i > active) else 225)
        ncol = (DEEP_RED, 255) if on else (MUTED, 170)
        d.text((num_x, y), "%02d" % (i + 1), font=fnum, fill=ncol[0] + (ncol[1],))
        for j, ln in enumerate(lines):
            tw = d.textlength(ln, font=f)
            tx = cx - tw / 2
            ty = y + numh + j * lh + (lh - fs) / 2
            d.text((tx, ty), ln, font=f, fill=col + (al,))
        y += hs[i] + gap

# ---- 画中画窗 ----
def cover_crop(src_img, win_w, win_h, vbias=0.12):
    """把原片按 cover 裁进窗口矩形；vbias>0 向上偏（保留头部、避开底部字幕）"""
    sw, sh = src_img.size
    scale = max(win_w / sw, win_h / sh)
    sim = src_img.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
    ox = max(0, min((sim.width - win_w) // 2, sim.width - win_w))
    oy_raw = (sim.height - win_h) // 2
    oy = int(oy_raw - vbias * (sim.height - win_h))
    oy = max(0, min(oy, sim.height - win_h))
    return sim.crop((ox, oy, ox + win_w, oy + win_h))

def draw_pip(canvas, src_img, pip_cell, pip_shape, border_col, ratio=0.42):
    """画中画窗。
    窗口宽高比 ratio(w/h) 必须 < 源宽高比，否则 cover 裁切会在纵向切掉大半张脸
    （竖屏 9:16 大特写素材的典型坑）。默认 0.42：只裁两侧约 13%，脸完整。
    """
    rx0, ry0, rx1, ry1 = cell_rect(pip_cell)
    pad = 0
    rx0, ry0, rx1, ry1 = rx0 + pad, ry0 + pad, rx1 - pad, ry1 - pad
    colw, colh = rx1 - rx0, ry1 - ry0
    cx, cy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
    d = ImageDraw.Draw(canvas)
    if pip_shape == "circle":
        size = int(min(colw, colh * 0.86))
        sim = cover_crop(src_img, size, size, vbias=0.05)
        sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([6, 12, size + 6, size + 12], fill=(0, 0, 0, 80))
        canvas.paste(sh, (int(cx - size / 2) + 6, int(cy - size / 2) + 12), sh)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        d.ellipse([cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2],
                  outline=border_col + (255,), width=9)
        canvas.paste(sim.convert("RGBA"), (int(cx - size / 2), int(cy - size / 2)), mask)
    else:  # 竖版圆角矩形窗：宽度贴合列宽，高度按 ratio 推，竖直居中
        win_w = int(colw)
        win_h = int(min(colh, win_w / ratio))
        x0, y0 = int(cx - win_w / 2), int(cy - win_h / 2)
        sim = cover_crop(src_img, win_w, win_h, vbias=0.0)
        rad = 44
        sh = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([6, 14, win_w + 6, win_h + 14],
                                             radius=rad, fill=(0, 0, 0, 76))
        canvas.paste(sh, (x0 + 6, y0 + 14), sh)
        mask = Image.new("L", (win_w, win_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, win_w, win_h], radius=rad, fill=255)
        canvas.paste(sim.convert("RGBA"), (x0, y0), mask)
        d.rounded_rectangle([x0, y0, x0 + win_w, y0 + win_h], radius=rad,
                            outline=border_col + (235,), width=8)
        return (x0, y0, win_w, win_h)

# ---- 合成单帧 ----
def compose(src_path, t, mode, bg_rgb, pip_cell, pip_shape, person_pos, kws, pip_ratio=0.42, groups=None):
    canvas = Image.new("RGBA", (W, H), bg_rgb + (255,))
    if mode == "pip":
        im = Image.open(src_path).convert("RGB")
        box = draw_pip(canvas, im, pip_cell, pip_shape, INK, ratio=pip_ratio)
        kw_cell = PERSON_OPP[pip_cell]
        if groups:
            # 列表与人物窗等高对齐：左右两栏同起同收，画面不偏
            span = (box[1] + 10, box[1] + box[3] - 10) if box else None
            draw_keyword_list(canvas, kws, kw_cell, t, groups, span=span)
        else:
            draw_keyword_block(canvas, kws, kw_cell, t, shadow=False)
    else:  # overlay：原片全帧做底，关键字补对侧空白
        im = Image.open(src_path).convert("RGB")
        r = min(W / im.width, H / im.height)
        sim = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
        canvas.alpha_composite(sim.convert("RGBA"),
                               ((W - sim.width) // 2, (H - sim.height) // 2))
        pcell = person_pos or "center"
        kw_cell = PERSON_OPP[pcell]
        if groups:
            draw_keyword_list(canvas, kws, kw_cell, t, groups)
        else:
            draw_keyword_block(canvas, kws, kw_cell, t, shadow=True)
    return canvas.convert("RGB")

# ---- 抽帧 / 编码 ----
def extract_frames(source, ss, t, outdir, tw=W, th=H):
    os.makedirs(outdir, exist_ok=True)
    run(["ffmpeg", "-y", "-ss", str(ss), "-i", source, "-t", str(t),
         "-vf", f"scale={tw}:{th}", "-q:v", "3",
         os.path.join(outdir, "f%05d.jpg")])
    return sorted(glob.glob(os.path.join(outdir, "f*.jpg")))

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:]); sys.exit(1)

# ---- 九宫格叠层（预览）----
def draw_grid(d, person_cell, kw_cell):
    for gx in (W / 3, 2 * W / 3):
        d.line([(gx, 0), (gx, H)], fill=(255, 255, 255, 90), width=2)
    for gy in (H / 3, 2 * H / 3):
        d.line([(0, gy), (W, gy)], fill=(255, 255, 255, 90), width=2)
    def tag(cell, label, col):
        rx0, ry0, rx1, ry1 = cell_rect(cell)
        d.rectangle([rx0, ry0, rx1, ry1], outline=col, width=5)
        d.text(((rx0 + rx1) / 2 - 18, ry0 + 12), label,
               font=font(FONT_BOLD, 44), fill=col)
    tag(person_cell, "P", (220, 60, 60, 235))
    tag(kw_cell, "K", (40, 170, 180, 235))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--ss", type=float, required=True)
    ap.add_argument("--t", type=float, required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--kws", required=True)
    ap.add_argument("--pip", default=None, choices=["circle", "square"],
                    help="画中画形状；给定即走画中画模式（全帧特写素材用）")
    ap.add_argument("--pip-cell", default="right",
                    help="画中画人物窗占的九宫格（right/left/bottom/top/...）")
    ap.add_argument("--pip-ratio", type=float, default=0.42,
                    help="画中画窗宽高比 w/h；须小于源宽高比，否则会纵向裁掉脸")
    ap.add_argument("--person-pos", default="center",
                    help="叠加模式用：人物在九宫格的格，决定关键字对侧补位")
    ap.add_argument("--bg", default="#f2f1ec", help="背景补位色 #rrggbb")
    ap.add_argument("--list", default=None,
                    help='整段论点堆叠（JSON 数组，每项可含 \\n）；给定时用列表模式，'
                         'kws 用 idx+t0/t1 标记当前高亮项')
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--pt", type=float, default=1.0, help="预览时刻（秒）")
    ap.add_argument("--preview-out", default="preview.png")
    args = ap.parse_args()

    kws = json.loads(args.kws)
    groups = json.loads(args.list) if args.list else None
    bg_rgb = parse_bg_rgb(args.bg)
    mode = "pip" if args.pip else "overlay"
    pip_cell = args.pip_cell if args.pip else None

    if args.preview:
        tmp = tempfile.mkdtemp(prefix="talkprev_")
        frames = extract_frames(args.source, args.ss, args.t, tmp)
        idx = max(0, min(len(frames) - 1, int(args.pt * FPS)))
        src = frames[idx]
        person_cell = pip_cell if mode == "pip" else (args.person_pos or "center")
        kw_cell = PERSON_OPP[person_cell]
        canvas = compose(src, args.pt, mode, bg_rgb, pip_cell,
                         args.pip or "square", args.person_pos, kws, args.pip_ratio, groups)
        d = ImageDraw.Draw(canvas)
        draw_grid(d, person_cell, kw_cell)
        canvas.save(args.preview_out)
        print("PREVIEW ->", args.preview_out, "(P=%s K=%s)" % (person_cell, kw_cell))
        return

    if not args.out:
        sys.exit("--out 必填（非预览模式）")
    tmp = tempfile.mkdtemp(prefix="talk_")
    frames = extract_frames(args.source, args.ss, args.t, tmp)
    seqdir = os.path.join(tmp, "seq")
    os.makedirs(seqdir, exist_ok=True)
    n = int(args.t * FPS) + 2
    for i in range(n):
        fi = min(i, len(frames) - 1)
        compose(frames[fi], i / FPS, mode, bg_rgb, pip_cell,
                args.pip or "square", args.person_pos, kws, args.pip_ratio, groups).save(
            os.path.join(seqdir, f"o{i:04d}.png"))
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(seqdir, "o%04d.png"),
         "-ss", str(args.ss), "-i", args.source, "-t", str(args.t),
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", args.out])
    print("OK ->", args.out)

if __name__ == "__main__":
    main()
