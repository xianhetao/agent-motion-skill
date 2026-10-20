#!/usr/bin/env python3
"""生成「字体对比样张」HTML —— 选字体别靠猜，出图让用户目测。

口播包装里字重/字体的观感差异（尤其汉字横画粗细）在代码里看不出来，
必须拉到实际字号上比对。这个脚本把「列几种方案 → 生成样张 → 截图给用户看」标准化。

用法：
    python3 font_compare.py \
      --text "门槛几乎 降到零" \
      --row "A 现状 得意黑:Smiley Sans:400:150" \
      --row "B Noto 700:Noto Sans SC:700:150" \
      --row "C Noto 900:Noto Sans SC:900:150" \
      --font-dir /path/to/fonts --out font-compare.html [--bg '#f2f1ec' --ink '#26282e']

--row 格式：<标签>:<font-family>:<weight>:<size>
--font-dir：扫描该目录下 *.ttf/*.woff/*.woff2 自动生成 @font-face（family 取文件名主干，
            可用 --face "Family=/abs/file.ttf" 覆盖）
生成后截图（避开 file:// 的字体 CORS，走本地 server 或项目自带 server）再给用户看。
"""
import argparse
import glob
import os
import sys

CSS = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>字体对比样张</title>
<style>
{faces}
  html, body {{ margin: 0; background: {bg}; color: {ink}; font-family: sans-serif; }}
  .wrap {{ width: 720px; padding: 40px 36px 60px; }}
  .hd {{ font-size: 26px; font-weight: 700; color: #b8433f; margin: 40px 0 6px; }}
  .sub {{ font-size: 15px; color: #6b6659; margin-bottom: 18px; }}
  .row {{ margin: 0 0 18px; }}
  .sample {{ display: block; line-height: 1.18; }}
  .tag {{ font-size: 15px; color: #8a8579; margin-top: 6px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hd">字体对比 · {text}</div>
  <div class="sub">同一文案、同一字号，逐方案目测（重点看横画粗细与整体重量）</div>
{rows}
</div>
</body>
</html>
"""


def scan_faces(font_dir, overrides):
    """扫描字体目录生成 @font-face；返回 (css, {归一化名: 实际 family})"""
    faces, aliases = [], {}
    seen = set()
    for p in sorted(glob.glob(os.path.join(font_dir, "**/*.*"), recursive=True)):
        if os.path.splitext(p)[1].lower() not in (".ttf", ".otf", ".woff", ".woff2"):
            continue
        fam = os.path.splitext(os.path.basename(p))[0]
        base = fam.split("[")[0].replace("%5Bwght%5D", "").strip()
        key = base.lower()
        if key in seen:
            continue
        seen.add(key)
        fmt = {".ttf": "truetype", ".otf": "opentype",
               ".woff": "woff", ".woff2": "woff2"}[os.path.splitext(p)[1].lower()]
        # 可变字体给全字重区间，静态字体给默认字重
        rng = "font-weight: 100 900;" if ("[wght]" in fam or "Variable" in fam) else ""
        faces.append(f'@font-face {{ font-family: "{base}"; src: url("{p}") format("{fmt}"); {rng} }}')
        aliases[norm(base)] = base
        # 把文件名里的空格形态也注册（NotoSansSC ↔ Noto Sans SC 之类靠 norm 兜住）
        aliases[norm(fam)] = base
    for ov in overrides:
        if "=" not in ov:
            continue
        fam, path = ov.split("=", 1)
        fmt = {".ttf": "truetype", ".otf": "opentype",
               ".woff": "woff", ".woff2": "woff2"}.get(os.path.splitext(path)[1].lower(), "truetype")
        faces.append(f'@font-face {{ font-family: "{fam}"; src: url("{path}") format("{fmt}"); font-weight: 100 900; }}')
        aliases[norm(fam)] = fam
    return "\n".join(faces), aliases


def lookup(fam, aliases):
    """精确匹配 → 前缀兜底（如 Smiley Sans ↔ SmileySans-Oblique）"""
    k = norm(fam)
    if k in aliases:
        return aliases[k]
    for ak, real in aliases.items():
        if ak.startswith(k) or k.startswith(ak):
            return real
    return fam


def norm(s):
    """归一化字体名：小写 + 去掉空格/连字符/下划线，用于 Noto Sans SC ↔ NotoSansSC 互认"""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="样例文案（用真实标题，别用 abc）")
    ap.add_argument("--row", action="append", required=True,
                    help="标签:font-family:weight:size，可重复")
    ap.add_argument("--font-dir", default="", help="字体目录，自动扫描生成 @font-face")
    ap.add_argument("--face", action="append", default=[], help='Family=/abs/file.ttf 覆盖')
    ap.add_argument("--out", default="font-compare.html")
    ap.add_argument("--bg", default="#f2f1ec")
    ap.add_argument("--ink", default="#26282e")
    args = ap.parse_args()

    aliases = {}
    faces = ""
    if args.font_dir:
        faces, aliases = scan_faces(args.font_dir, args.face)

    rows, miss = [], []
    for r in args.row:
        parts = r.split(":")
        if len(parts) != 4:
            print(f"[!] --row 格式应为 标签:字体:字重:字号，跳过: {r}", file=sys.stderr)
            continue
        label, fam, weight, size = [p.strip() for p in parts]
        real = lookup(fam, aliases)
        if aliases and norm(real) not in aliases:
            miss.append(fam)
        rows.append(
            f'  <div class="row">\n'
            f'    <span class="sample" style=\'font-family:"{real}"; font-weight:{weight}; '
            f'font-size:{size}px;\'>{args.text}</span>\n'
            f'    <div class="tag">{label} · {real} {weight} / {size}px</div>\n'
            f'  </div>')

    html = CSS.format(faces=faces, bg=args.bg, ink=args.ink,
                      text=args.text, rows="\n".join(rows))
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[+] 样张已生成 {args.out}（{len(rows)} 个方案）")
    if aliases:
        print(f"[i] 扫描到 {len(set(aliases.values()))} 个字体：{', '.join(sorted(set(aliases.values())))}")
    if miss:
        print(f"[!] 这些字体没在 --font-dir 里找到，会回退到系统字体：{sorted(set(miss))}",
              file=sys.stderr)
    print("[i] 截图走本地 server（file:// 会因 CORS 加载不到字体）："
          "python3 -m http.server 后 Chromium 打开，或用项目自带 server + fullPage 截图")


if __name__ == "__main__":
    main()
