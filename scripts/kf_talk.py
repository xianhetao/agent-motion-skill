#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人在讲 · KF 风格版式
====================
只给「没有定稿关键帧」的抽象段落用（U05 选谁 / U06 分不清真假 / U12 品牌资产）。
视觉语言完全复用 gen_keyframes.py 的 KF 体系：
  纸底 bg_press #efe9dd / 墨 #2b2722 / 深红 #9e2b25 / 白卡 / 整块色条
人窗 = 版面里的一张「卡」（圆角 28），不是另搞一套分栏。
"""
import os
import sys

KEYFRAME_DIR = "/Users/hzz/WorkBuddy/2026-09-10-16-17-19/huashu-测试口播"
sys.path.insert(0, KEYFRAME_DIR)
from gen_keyframes import W, H, font, rr, block, bg_press  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kf_talk")
os.makedirs(OUT, exist_ok=True)

INK = "#2b2722"
RED = "#9e2b25"
CREAM = "#efe9dd"
MUT = "#6f6754"   # 深灰褐（纸底 #efe9dd 上 4.69:1，达 WCAG AA）


def person_card(img, frame_path, box, radius=28):
    """把原片帧当作一张卡贴进版面（竖窗按比例裁切，脸完整）"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    im = Image.open(frame_path).convert("RGB")
    sw, sh = im.size
    s = max(w / sw, h / sh)
    im2 = im.resize((int(sw * s), int(sh * s)), Image.LANCZOS)
    ox = (im2.width - w) // 2
    oy = (im2.height - h) // 2
    im2 = im2.crop((ox, oy, ox + w, oy + h))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    img.paste(im2, (x0, y0), mask)


def u05(frame):
    """U05「而是选谁」27.4–31.8s —— 过渡段：旧问题 → 新问题。
    只用本段台词（对甲方来说 / 麻烦不再是没人可用 / 而是选谁），
    字块按实测高度垂直居中于人窗，不硬塞后文内容。"""
    img, d = bg_press()
    L = 60
    person_card(img, frame, (628, 300, 1020, 1620))   # 右栏竖卡（392 宽，脸完整）
    d = ImageDraw.Draw(img)

    f_lab, f_old, f_new = font("medium", 40), font("black", 132), font("black", 248)
    ink_lab = (43, 39, 34, 175)
    segs = [
        ("以前，麻烦是", f_lab, ink_lab, 26, None),
        ("没人可用", f_old, MUT, 96, "strike"),
        ("现在，麻烦是", f_lab, ink_lab, 36, None),
        ("选谁", f_new, RED, 0, None),
    ]
    # 实测高度（anchor=lt，y 即字形顶部）
    heights = []
    for txt, f, col, gap, extra in segs:
        b = f.getbbox(txt)
        heights.append((b[3] - b[1], gap))
    total = sum(h + g for h, g in heights)
    y = 300 + (1320 - total) // 2

    for (txt, f, col, gap, extra), (h, _) in zip(segs, heights):
        d.text((L, y), txt, font=f, fill=col, anchor="lt")
        if extra == "strike":
            tw = f.getbbox(txt)[2] - f.getbbox(txt)[0]
            sy = y + int(h * 0.56)
            d.rectangle([L, sy, L + tw, sy + 9], fill=(111, 103, 84, 235))
        y += h + gap
    img.save(os.path.join(OUT, "KF-U05-选谁.png"))
    print("U05 ->", os.path.join(OUT, "KF-U05-选谁.png"))


def u06(frame):
    """U06「分不清谁真谁假」32.0–38.2s —— KF 骨架：大标题 + (左卡 / 右人窗) + 底部色条"""
    img, d = bg_press()
    block(d, 60, 130, W - 120, ["满市场都说", "自己能做内容"],
          font("black", 100), INK, lh=116)
    d.text((64, 388), "能带货，能涨粉", font=font("black", 60), fill=RED)

    # 三行卡（左栏，与人窗同上下）
    rows = ["说自己能做", "说自己能带货", "说自己能涨粉"]
    cy0, cy1 = 500, 1500
    chh, gap = 200, 60
    for i, a in enumerate(rows):
        yy = cy0 + i * (chh + gap)
        rr(d, [60, yy, 566, yy + chh], 16, fill=(255, 253, 248, 255))
        d.text((92, yy + 52), a, font=font("medium", 44), fill=(43, 39, 34, 225))
        d.text((92, yy + 118), "凭什么？", font=font("black", 40), fill=(158, 43, 37, 230))

    # 人窗卡（右栏，与卡区同上下）
    person_card(img, frame, (600, cy0, W - 60, cy1))
    d = ImageDraw.Draw(img)

    # 底部深红条（文字居中，不出界）
    rr(d, [0, 1560, W, H], 0, fill=RED)
    d.text((W / 2, 1650), "你分不清", font=font("black", 86), fill=CREAM, anchor="ma")
    d.text((W / 2, 1770), "谁真谁假", font=font("black", 86), fill=CREAM, anchor="ma")
    img.save(os.path.join(OUT, "KF-U06-分不清.png"))
    print("U06 ->", os.path.join(OUT, "KF-U06-分不清.png"))


if __name__ == "__main__":
    u05("/tmp/u05.png")
    u06("/tmp/u06.png")
