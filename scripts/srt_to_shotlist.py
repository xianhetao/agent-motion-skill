#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 SRT 字幕转成 koubo-video 的 shot_list.json。

- 每条字幕 → subtitle 段（保持原始时间码，剪映里就是同步字幕条）
- 开头追加一张封面标题卡（title 段），可在剪映删除
用法:
  python3 srt_to_shotlist.py 测试.srt --video 测试.mp4 --out shot_list.json
"""
import argparse
import json
import os
import re

TC = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def tc2s(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(text):
    blocks = re.split(r"\n\s*\n", text.strip())
    segs = []
    for blk in blocks:
        lines = [l for l in blk.splitlines() if l.strip()]
        if not lines:
            continue
        # 跳过序号行，找时间轴行
        tc_line = None
        start = None
        for i, l in enumerate(lines):
            m = TC.search(l)
            if m:
                tc_line = i
                start = tc2s(*m.group(1, 2, 3, 4))
                end = tc2s(*m.group(5, 6, 7, 8))
                break
        if tc_line is None:
            continue
        content = " ".join(lines[tc_line + 1:]).strip()
        if not content:
            continue
        segs.append({"start": round(start, 3), "end": round(end, 3), "text": content})
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srt")
    ap.add_argument("--video", default=None)
    ap.add_argument("--out", default="shot_list.json")
    ap.add_argument("--title", default="传播门槛归零，企业拼什么？")
    ap.add_argument("--cover-dur", type=float, default=3.0)
    ap.add_argument("--template", default="modern")
    args = ap.parse_args()

    with open(os.path.expanduser(args.srt), encoding="utf-8") as f:
        raw = f.read()
    cues = parse_srt(raw)

    segments = []
    # 封面标题卡
    segments.append({
        "start": 0.0,
        "end": args.cover_dur,
        "anim_type": "title",
        "text": args.title,
    })
    # 字幕
    for c in cues:
        segments.append({
            "start": c["start"],
            "end": c["end"],
            "anim_type": "subtitle",
            "text": c["text"],
        })

    sl = {
        "meta": {
            "title": "测试口播",
            "resolution": [1080, 1920],
            "fps": 30,
            "layout": "portrait",
            "template": args.template,
            "video_path": os.path.expanduser(args.video) if args.video else None,
        },
        "segments": segments,
    }
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sl, f, ensure_ascii=False, indent=2)
    print("shot_list.json 已生成:", out)
    print("封面标题卡 1 条 + 字幕段 %d 条" % len(cues))


if __name__ == "__main__":
    main()
