#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent-motion · 导演式包装配置器（路线 C 核心脚本）

把 talking-head 工程配置好：
  1) 解析 SRT -> om-cues words（字段名 word，talking-head 靠词时间驱动卡片落点）
  2) 用 config.json 覆盖模板的 composition variables（name/role/stats/keywords/chapter/corner/talk…）
  3) 注入/替换 <script id="om-cues"> 到 index.html
  4) 自动删除 <video id="talk"> 的 muted（否则成片无声；--keep-muted 可保留）

用法:
  python3 configure.py --dir <工程目录> --srt 字幕.srt --config config.json
  python3 configure.py --dir <工程目录> --srt 字幕.srt --talk /abs/口播.mp4
  python3 configure.py --dir <工程目录> --srt 字幕.srt   # 只注入 om-cues + 删 muted

依赖: huashu-motion 的 talking-head 模板（om new <dir> --template talking-head 生成）
"""
import argparse
import json
import os
import re
import shutil
import sys

# om-cues 的 words 字段名是 word（不是 text）；talking-head 的 OM.cue 搜的是 word 文本
TC = re.compile(r"(\d+):(\d+):(\d+)[.,](\d{1,3})\s*-->\s*(\d+):(\d+):(\d+)[.,](\d{1,3})")

# 这些 id 在 composition variables 里是 JSON 字符串类型，config 给 list/dict 时要序列化
JSON_STRING_IDS = {"stats", "keywords"}


def tc2s(h, m, s, ms):
    ms = int(ms)
    if len(str(ms)) == 2:  # "05" -> 0.05s
        ms *= 10
    return int(h) * 3600 + int(m) * 60 + int(s) + ms / 1000.0


def parse_srt(text):
    blocks = re.split(r"\n\s*\n", text.strip())
    words = []
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
                    words.append({"word": content, "start": round(start, 3), "end": round(end, 3)})
                break
    return words


def strip_muted(html):
    """删除 <video id="talk" ... muted ...> 里的 muted（保留前面的空白，避免属性粘连）。"""
    return re.sub(r'\s+muted(?=\s|>)', '', html)


def main():
    ap = argparse.ArgumentParser(description="配置 talking-head 工程：注入 om-cues + 卡片变量")
    ap.add_argument("--dir", required=True, help="talking-head 工程目录（含 index.html）")
    ap.add_argument("--srt", required=True, help="口播字幕 SRT（生成 om-cues 词时间轴）")
    ap.add_argument("--config", default=None, help="卡片配置 JSON（name/role/stats/keywords/chapter/corner/talk…）")
    ap.add_argument("--talk", default=None, help="口播视频绝对路径，快捷覆盖 talk 变量")
    ap.add_argument("--out", default=None, help="输出 index.html（默认覆盖 --dir 下的，先备份 .bak）")
    ap.add_argument("--keep-muted", action="store_true", help="保留 footage 的 muted（默认删除，否则成片无声）")
    args = ap.parse_args()

    html_path = os.path.join(os.path.expanduser(args.dir), "index.html")
    if not os.path.exists(html_path):
        print("错误: 找不到", html_path, "（先 om new <dir> --template talking-head）")
        sys.exit(1)

    html = open(html_path, encoding="utf-8").read()

    # 0) 备份
    shutil.copy(html_path, html_path + ".bak")

    # 1) 解析 SRT -> words
    with open(os.path.expanduser(args.srt), encoding="utf-8") as f:
        words = parse_srt(f.read())
    if not words:
        print("错误: SRT 未解析出任何字幕句")
        sys.exit(1)
    cues = {
        "version": 1,
        "duration": round(words[-1]["end"], 3),
        "offset": 0,
        "words": words,
    }
    print("om-cues: %d 句，时长 %.2fs" % (len(words), cues["duration"]))

    # 2) 读 config
    cfg = {}
    if args.config:
        with open(os.path.expanduser(args.config), encoding="utf-8") as f:
            cfg = json.load(f)
    if args.talk:
        cfg["talk"] = args.talk

    # 3) 覆盖 composition variables 默认值
    m = re.search(r"data-composition-variables='(.*?)'", html, re.S)
    if not m:
        print("错误: index.html 里找不到 data-composition-variables")
        sys.exit(1)
    arr = json.loads(m.group(1))

    applied, skipped = [], []
    for item in arr:
        vid = item.get("id")
        if vid in cfg:
            val = cfg[vid]
            if vid in JSON_STRING_IDS and not isinstance(val, str):
                val = json.dumps(val, ensure_ascii=False)
            item["default"] = val
            applied.append(vid)
        # length 用 om-cues 时长兜底（无显式配置时）
        elif vid == "length" and "length" not in cfg:
            item["default"] = cues["duration"]
    new_attr = "data-composition-variables='" + json.dumps(arr, ensure_ascii=False) + "'"
    html = html[:m.start()] + new_attr + html[m.end():]

    # 4) 删 muted（默认）
    if not args.keep_muted:
        before = html
        html = strip_muted(html)
        if html != before:
            print("已删除 <video id=talk> 的 muted（成片会自动 mux 原片音轨）")

    # 5) 注入 / 替换 om-cues
    #    注意：talking-head 模板的注释里含有字面文本 <script id="om-cues">（文档示例）。
    #    必须用带 type="application/json" 的真实脚本模式匹配，否则用 re.S 会从注释里的
    #    假标签一路跨行吞掉整个 <body>（含 GSAP 时间轴注册脚本），导致「no timeline」。
    cue_json = json.dumps(cues, ensure_ascii=False)
    REAL_CUE = re.compile(r'<script id="om-cues"[^>]*type="application/json"[^>]*>.*?</script>', re.S)
    existing = REAL_CUE.search(html)
    cue_script = '<script id="om-cues" type="application/json">' + cue_json + '</script>'
    if existing:
        html = html[:existing.start()] + cue_script + html[existing.end():]
        print("已替换已有 om-cues")
    else:
        if "</body>" in html:
            html = html.replace("</body>", cue_script + "\n</body>", 1)
        else:
            html += "\n" + cue_script + "\n"
        print("已注入 om-cues")

    out_path = os.path.expanduser(args.out) if args.out else html_path
    open(out_path, "w", encoding="utf-8").write(html)
    print("已写入:", out_path)
    print("应用变量:", ", ".join(applied) or "(无，仅 om-cues)")
    if skipped:
        print("跳过(不存在于模板):", ", ".join(skipped))


if __name__ == "__main__":
    main()
