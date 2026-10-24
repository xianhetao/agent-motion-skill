#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试口播 · 新方向关键帧生成器
方向：无人物 / 段落核心句出大标题(强冲击、占满、不缩角) / 论证里抓关键词做动画提示 /
      满屏内容演绎 / 格式塔分组、画面无大空白。
分章套用 4 种参考风格：报刊题签 / 暗场展柜 / 杂志grid / 书籍朱砂印。
输出 6 张 1080x1920 关键帧 PNG。
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keyframes")
os.makedirs(OUT, exist_ok=True)
FD = "/System/Library/Fonts/Supplemental"
F = {
    "black":   ImageFont.truetype(os.path.join(FD, "NotoSansCJKsc-Black.otf"), 10),
    "bold":    ImageFont.truetype(os.path.join(FD, "NotoSansCJKsc-Bold.otf"), 10),
    "medium":  ImageFont.truetype(os.path.join(FD, "NotoSansCJKsc-Medium.otf"), 10),
    "regular": ImageFont.truetype(os.path.join(FD, "NotoSansCJKsc-Regular.otf"), 10),
}
def font(w, s):
    return ImageFont.truetype(os.path.join(FD, {
        "black": "NotoSansCJKsc-Black.otf", "bold": "NotoSansCJKsc-Bold.otf",
        "medium": "NotoSansCJKsc-Medium.otf", "regular": "NotoSansCJKsc-Regular.otf"}[w]), s)

def rr(d, box, r, fill=None, outline=None, wdt=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=wdt)

def tline(d, p1, p2, col=(138, 124, 94, 255), w=3):
    """树状图连线（结构必需，表达从属层级，非装饰细线）"""
    d.line([p1[0], p1[1], p2[0], p2[1]], fill=col, width=w)

def node(d, c, w, h, fill, main, msz, sub, ssz, mfill, sfill):
    """居中绘制一个节点块（无描边，靠色块分组）；sub 为可选副标签"""
    x, y = c
    rr(d, [x - w / 2, y - h / 2, x + w / 2, y + h / 2], 14, fill=fill)
    if sub:
        d.text((x, y - 20), main, font=font("black", msz), fill=mfill, anchor="mm")
        d.text((x, y + 32), sub, font=font("bold", ssz), fill=sfill, anchor="mm")
    else:
        d.text((x, y), main, font=font("black", msz), fill=mfill, anchor="mm")

def text_w(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]

def wrap_cjk(d, s, f, maxw):
    """按字符断行（CJK 友好），返回行列表"""
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        t = cur + ch
        if text_w(d, t, f) > maxw and cur:
            lines.append(cur); cur = ch
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines

def draw_text(d, x, y, s, f, fill, align="left", lh=None, anchor="la"):
    lh = lh or f.size * 1.18
    for i, ln in enumerate(s.split("\n") if "\n" in s else [s]):
        ly = y + i * lh
        if align == "center":
            d.text((x, ly), ln, font=f, fill=fill, anchor="ma")
        elif align == "right":
            d.text((x, ly), ln, font=f, fill=fill, anchor="ra")
        else:
            d.text((x, ly), ln, font=f, fill=fill, anchor=anchor)

def block(d, x, y, w, lines, f, fill, align="left", lh=None):
    lh = lh or f.size * 1.2
    for i, ln in enumerate(lines):
        ly = y + i * lh
        if align == "center":
            d.text((x + w / 2, ly), ln, font=f, fill=fill, anchor="ma")
        else:
            d.text((x, ly), ln, font=f, fill=fill, anchor="la")
    return y + len(lines) * lh

# ---------------- 背景 ----------------
def bg_press():
    img = Image.new("RGB", (W, H), "#efe9dd"); d = ImageDraw.Draw(img)
    return img, d

def bg_dark():
    img = Image.new("RGB", (W, H), "#14110e"); d = ImageDraw.Draw(img)
    # 径向暖光
    cx, cy, R = W / 2, H * 0.40, W * 0.95
    try:
        import numpy as np
        ys, xs = np.mgrid[0:H, 0:W]
        dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / R
        a = (np.clip(1 - dist, 0, 1) ** 1.6 * 150).astype("uint8")
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for yy in range(0, H, 2):
            for xx in range(0, W, 2):
                av = int(a[yy, xx])
                if av > 4:
                    gd.point((xx, yy), fill=(216, 162, 74, av))
        img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
        d = ImageDraw.Draw(img)
    except Exception:
        for r in range(int(R), 0, -12):
            a = int(150 * (1 - r / R) ** 1.6)
            d.ellipse([cx - r, cy - r * 1.1, cx + r, cy + r * 1.1], outline=(216, 162, 74, a))
    return img, d

def bg_mag():
    img = Image.new("RGB", (W, H), "#ffffff"); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 10, H], fill="#8f5f12")
    return img, d

def bg_book():
    img = Image.new("RGB", (W, H), "#f3ede1"); d = ImageDraw.Draw(img)
    return img, d

# ---------------- 关键帧 ----------------
def kf1():
    img, d = bg_press()
    # 大标题（占满、强冲击）
    block(d, 90, 160, W - 180, ["门槛", "几乎降到零"],
          font("black", 168), "#2b2722", lh=176)
    # 副行
    d.text((92, 640), "旧的传播秩序，有一道硬门槛", font=font("medium", 40), fill=(43, 39, 34, 200))
    # 关键词芯片组（格式塔紧邻）
    d.text((92, 720), "能上，本身就说明有人替你 —", font=font("medium", 38), fill=(43, 39, 34, 200))
    chips = ["刊号", "牌照", "审查"]
    cw, gap, y = 250, 28, 800
    for i, c in enumerate(chips):
        x = 92 + i * (cw + gap)
        rr(d, [x, y, x + cw, y + 130], 14, fill=(158, 43, 37, 255))
        d.text((x + cw / 2, y + 65), c, font=font("black", 56), fill="#efe9dd", anchor="mm")
    # 论证关键词句（动画提示：强调“极度膨胀/鱼龙混杂”）
    d.text((92, 990), "供给端", font=font("black", 60), fill="#2b2722")
    d.text((300, 990), "极度膨胀", font=font("black", 60), fill="#9e2b25")
    d.text((92, 1070), "鱼龙混杂", font=font("black", 60), fill="#9e2b25")
    # 底部满屏陈述条（文字竖向居中，消除条内空白）
    rr(d, [0, 1240, W, H], 0, fill="#2b2722")
    block(d, 92, 1502, W - 184,
          ["供给端天然稀缺", "→ 公众天然信它"],
          font("black", 64), "#efe9dd", lh=78, align="center")
    img.save(os.path.join(OUT, "KF1-门槛.png"))
    print("KF1 done")

def kf2():
    img, d = bg_press()
    # 论证核心句：关键词"筛过一遍"高亮
    d.text((90, 170), "有人替你", font=font("black", 120), fill="#2b2722")
    d.text((90, 310), "筛过一遍", font=font("black", 120), fill="#9e2b25")
    # 三组旧媒体门槛 紧邻堆叠（格式塔一组）
    items = [("报纸杂志", "刊号"), ("频道", "牌照"), ("广电", "审查")]
    y = 560
    for i, (a, b) in enumerate(items):
        yy = y + i * 150
        rr(d, [92, yy, W - 92, yy + 120], 16, fill=(255, 253, 248, 255))
        d.text((120, yy + 60), a, font=font("medium", 44), fill=(43, 39, 34, 220), anchor="lm")
        d.text((W - 120, yy + 60), b, font=font("black", 60), fill="#9e2b25", anchor="rm")
    # 底部配对陈述（文字竖向居中，消除条内空白）
    rr(d, [0, 1140, W, H], 0, fill="#9e2b25")
    block(d, 92, 1454, W - 184, ["供给天然稀缺", "→ 所以它可信"],
          font("black", 62), "#efe9dd", lh=76, align="center")
    img.save(os.path.join(OUT, "KF2-筛过一遍.png"))
    print("KF2 done")

def kf3():
    img, d = bg_dark()
    block(d, 90, 165, W - 180, ["公信力", "不稳了"],
          font("black", 160), "#f3ead6", lh=168)
    # 两列对比（紧邻分组，无空白）
    colw = (W - 180 - 40) / 2
    # 左：机构给的（稳定）—— 白卡 + 深琥珀字（WCAG 4.85:1）
    lx, rx = 90, 90 + colw + 40
    rr(d, [lx, 760, lx + colw, 1380], 18, fill=(245, 240, 230))
    block(d, lx, 985, colw, ["机构给的", "长期积累", "相对稳定"],
          font("black", 58), "#8f5f12", lh=74, align="center")
    # 右：算法给的（暴涨/反噬）—— 深琥珀卡 + 白字（WCAG 4.47:1）
    rr(d, [rx, 760, rx + colw, 1380], 18, fill=(143, 95, 18))
    block(d, rx, 985, colw, ["算法给的", "一夜暴涨", "一夜反噬"],
          font("black", 58), "#ffffff", lh=74, align="center")
    d.text((W / 2, 1560), "一家报社不会今天有信誉，明天归零", font=font("medium", 38),
           fill=(233, 226, 212, 220), anchor="mm")
    img.save(os.path.join(OUT, "KF3-公信力.png"))
    print("KF3 done")

def kf4():
    img, d = bg_mag()
    block(d, 60, 130, W - 120, ["毛巾帝国", "一夜暴涨"],
          font("black", 132), "#222222", lh=140)
    # 数据三联（大数字紧邻分组）
    data = [("1.2亿", "全网播放"), ("22.8万", "30天涨粉"), ("500万", "带货")]
    cw = (W - 160 - 40) / 3
    y = 580
    for i, (num, lab) in enumerate(data):
        x = 80 + i * (cw + 20)
        rr(d, [x, y, x + cw, y + 300], 16, fill="#eae8e4")
        d.text((x + cw / 2, y + 150), num, font=font("black", 76), fill="#8f5f12", anchor="mm")
        d.text((x + cw / 2, y + 235), lab, font=font("bold", 34), fill="#333333", anchor="mm")
    # 论证关键词句（动画提示：强调“品牌资产”）
    d.text((80, 960), "流量给足了 —— 但压进去的", font=font("medium", 42), fill="#444444")
    d.text((80, 1020), "可能是品牌资产本身", font=font("black", 52), fill="#8f5f12")
    # 底部满屏强调条（文字竖向居中，消除条内空白）
    rr(d, [0, 1240, W, H], 0, fill="#8f5f12")
    d.text((W / 2, 1520), "播放超 1.2 亿次", font=font("black", 70), fill="#ffffff", anchor="mm")
    d.text((W / 2, 1630), "30天涨粉 22.8万 · 带货超 500万", font=font("bold", 40), fill="#ffffff", anchor="mm")
    img.save(os.path.join(OUT, "KF4-毛巾帝国.png"))
    print("KF4 done")

def kf5():
    img, d = bg_mag()
    # 三词标题
    d.text((80, 130), "报案", font=font("black", 92), fill="#222222")
    d.text((360, 130), "晒证", font=font("black", 92), fill="#8f5f12")
    d.text((620, 130), "自证", font=font("black", 92), fill="#222222")
    # 三张紧邻大卡
    cards = [("01", "报案", "谣言四起，公司报案"),
             ("02", "晒结婚证", "公开婚姻证明"),
             ("03", "DNA鉴定", "自证家族关系")]
    y = 420
    for i, (no, t, sub) in enumerate(cards):
        cy = y + i * 360
        rr(d, [80, cy, W - 80, cy + 320], 18, fill="#eae8e4")
        d.text((120, cy + 60), no, font=font("black", 70), fill="#8f5f12")
        d.text((210, cy + 70), t, font=font("black", 72), fill="#222222")
        d.text((120, cy + 220), sub, font=font("medium", 40), fill="#555555")
    # 底部结论条
    rr(d, [0, 1560, W, H], 0, fill="#222222")
    block(d, 80, 1610, W - 160, ["用娱乐化方式做品牌", "流量来得快，压进去的是品牌资产"],
          font("black", 58), "#ffffff", lh=74, align="center")
    img.save(os.path.join(OUT, "KF5-报案三连.png"))
    print("KF5 done")

def kf6():
    img, d = bg_book()
    # 大标题（段落核心句，居中、强冲击）
    block(d, 0, 100, W, ["主号", "要保调性"],
          font("black", 100), "#2d2a24", lh=108, align="center")
    # ---- 树状组织结构图（层级：主号 → 子号×3 → 新号×9）----
    COL = (138, 124, 94, 255)
    # L1 主号
    node(d, (540, 500), 360, 150, "#2d2a24", "主号", 66, "保调性", 32, "#f3ede1", "#d9c9a2")
    bus1 = 620
    tline(d, (540, 575), (540, bus1), COL, 3)
    tline(d, (240, bus1), (840, bus1), COL, 3)
    # L2 子号 ×3
    l2y, l2w, l2h = 750, 250, 140
    l2x = [240, 540, 840]
    for x in l2x:
        tline(d, (x, bus1), (x, l2y - l2h / 2), COL, 3)
        node(d, (x, l2y), l2w, l2h, "#ffffff", "子号", 50, "做试验", 26, "#2d2a24", "#2d2a24")
    # L3 新号 ×9（每子号 3 个）
    bus2, l3y, l3w, l3h = 880, 1130, 84, 150
    l3groups = [[140, 240, 340], [440, 540, 640], [740, 840, 940]]
    for i, x in enumerate(l2x):
        tline(d, (x, l2y + l2h / 2), (x, bus2), COL, 3)
        grp = l3groups[i]
        tline(d, (grp[0], bus2), (grp[2], bus2), COL, 3)
        for gx in grp:
            tline(d, (gx, bus2), (gx, l3y - l3h / 2), COL, 3)
            node(d, (gx, l3y), l3w, l3h, "#ffffff", "新号", 40, "", 0, "#2d2a24", "#2d2a24")
    # 层级说明（填满中下部，消除空白）
    d.text((W / 2, 1330), "一个主号 → 3 个子号 → 每子号再开 3 个新号（共 9）",
           font=font("medium", 34), fill=(45, 42, 36, 220), anchor="mm")
    d.text((W / 2, 1392), "新东西，另开号去试", font=font("black", 46), fill="#2d2a24", anchor="mm")
    # 底部收尾满屏条
    rr(d, [0, 1520, W, H], 0, fill="#b8433f")
    d.text((W / 2, 1700), "千万别拿主号去赌", font=font("black", 66), fill="#f3ede1", anchor="mm")
    img.save(os.path.join(OUT, "KF6-主号保调性.png"))
    print("KF6 done")

if __name__ == "__main__":
    kf1(); kf2(); kf3(); kf4(); kf5(); kf6()
    print("ALL KEYFRAMES ->", OUT)
