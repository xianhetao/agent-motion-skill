#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人在讲 · 大特写素材的人像块版式
==============================
素材是 1440x2560 竖屏大特写（脸占满帧），不能塞进长条竖窗（纵向会切掉脸）。
按用户口径：先把人像裁成**近似等边块**（形状不写死，方形/圆形由该段整体版式定），
再二选一：
  A 上下结构 —— 人像块满宽占上半屏，文字排在下半屏
  B 画中画放角 —— 人像块放任意一角（常用右上），其余版面排文字
视觉语言严格复用 gen_keyframes.py 的 KF 体系（纸底/墨/深红/白卡/整块色条）。
"""
import os
import sys

KEYFRAME_DIR = "/Users/hzz/WorkBuddy/2026-09-10-16-17-19/huashu-测试口播"
sys.path.insert(0, KEYFRAME_DIR)
from gen_keyframes import W, H, font, rr, block, bg_press, text_w  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kf_square")
os.makedirs(OUT, exist_ok=True)

INK = "#2b2722"
RED = "#9e2b25"
CREAM = "#efe9dd"
WHITE = "#fffdf8"
MUT = "#6f6754"

# 取景默认值（头肩像）——每段可按素材覆盖，不要当成固定参数
CROP = dict(cy=0.67, cx=0.5, zoom=0.92)


def square_crop(frame_path, size, cy=0.67, cx=0.5, zoom=0.92):
    """按人像位置取等边块（方/圆同源）。

    取景原则：**头—颈—肩完整**（头肩像），不是只切一张脸；不要从画面顶边取。
    cy/cx/zoom 只是默认值，**每段按素材目测覆盖**，不要当成固定参数：
      cy   取景中心在画面纵向的相对位置（人的头肩常在画面中下段，故默认 0.67）
      zoom 裁切边占原帧短边的比例（≥1 表示取满短边，<1 表示更特写）
    """
    im = Image.open(frame_path).convert("RGB")
    sw, sh = im.size
    side = max(64, int(min(sw, sh) * zoom))
    x0 = int(sw * cx - side / 2)
    y0 = int(sh * cy - side / 2)
    x0 = max(0, min(x0, sw - side))
    y0 = max(0, min(y0, sh - side))
    im = im.crop((x0, y0, x0 + side, y0 + side))
    return im.resize((size, size), Image.LANCZOS)


def paste_square(img, sq, x0, y0, radius=0, shape="square"):
    """贴人像块。shape: square（直角/圆角方）/ circle（圆形）。
    形状由整体版式定，不写死——脚本两种都能出。"""
    if shape == "circle":
        mask = Image.new("L", sq.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, sq.width, sq.height], fill=255)
        img.paste(sq, (x0, y0), mask)
    elif radius:
        mask = Image.new("L", sq.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, sq.width, sq.height], radius=radius, fill=255)
        img.paste(sq, (x0, y0), mask)
    else:
        img.paste(sq, (x0, y0))


# ---------------- A · 上下结构 ----------------
def a_stack(frame):
    """U05 选谁（27.4–31.8s）：方图满宽占上半屏 + 下半屏居中大字对照"""
    img, d = bg_press()
    sq = square_crop(frame, W, **CROP)
    paste_square(img, sq, 0, 0)
    d = ImageDraw.Draw(img)

    segs = [
        ("以前，麻烦是", font("medium", 44), (43, 39, 34, 180), 34, None),
        ("没人可用", font("black", 120), MUT, 86, "strike"),
        ("现在，麻烦是", font("medium", 44), (43, 39, 34, 180), 34, None),
        ("选谁", font("black", 272), RED, 0, None),
    ]
    hs = [f.getbbox(t)[3] - f.getbbox(t)[1] for t, f, _, _, _ in segs]
    total = sum(hs) + sum(s[3] for s in segs)
    y = 1080 + int((H - 1080 - total) / 2)

    for (txt, f, col, gap, extra), h in zip(segs, hs):
        tw = text_w(d, txt, f)
        tx = (W - tw) / 2
        d.text((tx, y), txt, font=f, fill=col, anchor="lt")
        if extra == "strike":
            sy = y + int(h * 0.56)
            d.rectangle([tx, sy, tx + tw, sy + 11], fill=(111, 103, 84, 235))
        y += h + gap

    out = os.path.join(OUT, "A-上下结构-U05.png")
    img.save(out)
    print("A ->", out)


# ---------------- B · 画中画放角 ----------------
def b_corner(frame, shape="square"):
    """U06 分不清真假（32.0–38.2s）：人像块放右上角，其余版面排标题+三卡+底部条
    shape: square（KF 卡片语言默认）/ circle（软调/访谈）"""
    img, d = bg_press()
    S, M = 440, 60
    x0 = W - M - S                            # 右上角人像块
    sq = square_crop(frame, S, **CROP)
    paste_square(img, sq, x0, M, radius=0 if shape == "circle" else 24, shape=shape)
    d = ImageDraw.Draw(img)

    # 左上：标题（两行，与方窗同起）
    block(d, 60, 104, x0 - 100, ["满市场都说", "自己能做内容"],
          font("black", 76), INK, lh=92)
    d.text((64, 330), "能带货，能涨粉", font=font("black", 46), fill=RED)

    # 三张白卡（整宽）：左标签 + 右问号，两栏撑满
    rows = ["说自己能做", "说自己能带货", "说自己能涨粉"]
    cy, chh, gap = 560, 258, 66
    for i, a in enumerate(rows):
        y = cy + i * (chh + gap)
        rr(d, [60, y, W - 60, y + chh], 18, fill=WHITE)
        d.text((96, y + 74), a, font=font("medium", 50), fill=(43, 39, 34, 230))
        d.text((W - 96, y + 66), "凭什么？", font=font("black", 56),
               fill=RED, anchor="ra")

    # 底部深红条
    rr(d, [0, 1560, W, H], 0, fill=RED)
    block(d, 0, 1640, W, ["你分不清", "谁真谁假"],
          font("black", 92), CREAM, lh=112, align="center")

    tag = "" if shape == "square" else "-" + shape
    out = os.path.join(OUT, f"B-画中画放角{tag}-U06.png")
    img.save(out)
    print("B ->", out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="大特写素材的人像块版式（形状可选，不写死）")
    ap.add_argument("--shape", default="square", choices=["square", "circle"],
                    help="人像块形状；由整体版式定（KF 卡片语言→square，软调→circle）")
    ap.add_argument("--u05", default="/tmp/u05.png")
    ap.add_argument("--u06", default="/tmp/u06.png")
    ap.add_argument("--cy", type=float, default=CROP["cy"],
                    help="取景中心纵向位置 0–1（头肩像按素材目测调）")
    ap.add_argument("--cx", type=float, default=CROP["cx"], help="取景中心横向位置 0–1")
    ap.add_argument("--zoom", type=float, default=CROP["zoom"],
                    help="裁切边占短边比例，<1 更特写、=1 取满短边")
    a = ap.parse_args()
    CROP.update(cy=a.cy, cx=a.cx, zoom=a.zoom)
    a_stack(a.u05)
    b_corner(a.u06, shape=a.shape)
