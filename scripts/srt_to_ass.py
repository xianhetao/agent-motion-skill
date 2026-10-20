#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把口播 SRT 转成 tech 风格 ASS 字幕（供 ffmpeg 烧录）。

- 每条字幕 -> Sub 样式（底部、亮青底、居中）
- 强调卡片 -> Card 样式（中上部、青色大字、半透明深色底）
- 可选笔误修正 FIXES

用法:
  python3 srt_to_ass.py 字幕.srt --out tech.ass
  # 自定义卡片/修正（JSON 文件）:
  python3 srt_to_ass.py 字幕.srt --cards cards.json --fixes fixes.json --playres 1080x1920

cards.json 格式: [[start, end, text, fontsize, y], ...]   # y 为 ASS 像素坐标
fixes.json 格式: {"原文": "修正后"}
"""
import argparse
import json
import os
import re

TC = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")

# ASS 颜色 = &HAABBGGRR
CYAN_TEXT = "&H00FFE37F"   # #7FE3FF 青
DARK = "&H00140E0B"        # #0B0E14 深底字
SUB_BG = "&H00D0FF39"      # #39FFD0 亮青字幕底
CARD_BG = "&H80140E0B"     # 深色 50% 透明卡片底

# 默认示例（洁丽雅案例）；用 --cards / --fixes 覆盖
DEFAULT_CARDS = [
    [0.0,   3.0,   "传播门槛归零，企业拼什么？", 96, 780],
    [39.0,  46.0,  "不是创意，是筛选和把关",       90, 820],
    [89.5,  98.0,  "1.2亿播放 · 22.8万涨粉 · 500万+带货", 58, 900],
    [120.5, 126.0, "流量来得快，压进去的是品牌资产", 74, 860],
    [134.0, 141.5, "主号保调性，子号做试验",       90, 860],
]
DEFAULT_FIXES = {"全网播放量超一1.2亿次": "全网播放量超 1.2 亿次"}


def tc2s(h, m, s, ms):
    ms = int(ms)
    if len(str(ms)) == 2:
        ms *= 10
    return int(h) * 3600 + int(m) * 60 + int(s) + ms / 1000.0


def ass_time(sec):
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs == 100:
        cs = 0
        s += 1
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)


def parse_srt(text):
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for blk in blocks:
        lines = [l for l in blk.splitlines() if l.strip()]
        if not lines:
            continue
        for i, l in enumerate(lines):
            m = TC.search(l)
            if m:
                start = tc2s(*m.group(1, 2, 3, 4))
                end = tc2s(*m.group(5, 6, 7, 8))
                content = " ".join(lines[i + 1:]).strip()
                if content:
                    segs.append((start, end, content))
                break
    return segs


def esc(t):
    return t.replace("{", "\\{").replace("}", "\\}")


def load_json_arg(path, default):
    if not path:
        return default
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srt")
    ap.add_argument("--out", default="tech.ass")
    ap.add_argument("--font", default="PingFang SC")
    ap.add_argument("--cards", default=None, help="卡片 JSON（覆盖默认示例）")
    ap.add_argument("--fixes", default=None, help="笔误修正 JSON（覆盖默认示例）")
    ap.add_argument("--playres", default="1080x1920", help="ASS 画布分辨率 WxH，默认 1080x1920")
    args = ap.parse_args()

    rx, ry = (int(x) for x in args.playres.lower().split("x"))
    cards = load_json_arg(args.cards, DEFAULT_CARDS)
    fixes = load_json_arg(args.fixes, DEFAULT_FIXES)

    with open(os.path.expanduser(args.srt), encoding="utf-8") as f:
        cues = parse_srt(f.read())

    # 字幕落点：竖屏底部约 85% 高度处（y = ry*0.85），成为唯一字幕
    sub_y = int(ry * 0.85)
    header = f"""[Script Info]
Title: 口播 tech 字幕
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {rx}
PlayResY: {ry}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{args.font},110,&H00FFFFFF,&H000000FF,{DARK},{SUB_BG},-1,0,0,0,100,100,0,0,1,5,1,2,60,60,{sub_y},1
Style: Card,{args.font},90,{CYAN_TEXT},&H000000FF,{DARK},{CARD_BG},-1,0,0,0,100,100,0,0,3,16,0,5,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    fixed = 0
    for (st, en, tx) in cues:
        tx2 = fixes.get(tx, tx)
        if tx2 != tx:
            fixed += 1
        lines.append("Dialogue: 0,%s,%s,Sub,,0,0,0,,%s" % (ass_time(st), ass_time(en), esc(tx2)))

    for (st, en, tx, fs, y) in cards:
        tag = r"{{\pos({rx0},{y})\fs{fs}}}".format(rx0=rx // 2, y=y, fs=fs)
        lines.append("Dialogue: 1,%s,%s,Card,,0,0,0,,%s%s" % (ass_time(st), ass_time(en), tag, esc(tx)))

    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("ASS 已生成:", out)
    print("字幕 %d 条（修正笔误 %d）+ 卡片 %d 张" % (len(cues), fixed, len(cards)))


if __name__ == "__main__":
    main()
