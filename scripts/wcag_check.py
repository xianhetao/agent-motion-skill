#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WCAG 文字/背景对比度核算工具（口播包装专用）
用途：给定一组 (前景文字色, 背景色) 配对，核算对比度并判断是否达到 WCAG AA：
  - 普通文本  >= 4.5:1
  - 大字号    >= 3.0:1 （>=24px，或 >=18.66px 且加粗）
参考资料：WCAG 2.1 对比度（增强）SC 1.4.3 / 1.4.6

用法：
  # 单对
  python3 wcag_check.py "#8f5f12" "#ffffff"
  # 多对（用 :: 分隔，可加注释用 #）
  python3 wcag_check.py \\
    "#8f5f12::#ffffff::数据数字 on 白" \\
    "#EB6C36::#ffffff::[反面]亮橙 on 白"
  # 从文件批量（-f，每行  fg::bg::备注）
  python3 wcag_check.py -f palette.txt
"""
import sys, re

def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def lum(rgb):
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def parse(color):
    color = color.strip().lstrip('#')
    if len(color) == 3:
        color = ''.join(ch * 2 for ch in color)
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))

def ratio(fg, bg):
    lf, lb = lum(fg), lum(bg)
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)

def check(fg_hex, bg_hex, note="", size=16, bold=False):
    fg, bg = parse(fg_hex), parse(bg_hex)
    r = ratio(fg, bg)
    big = size >= 24 or (size >= 18.66 and bold)
    need = 3.0 if big else 4.5
    ok = r >= need
    tag = "AA✓" if ok else ("AA✗" if r >= 3.0 else "FAIL")
    flag = "达标" if ok else ("大字号可达标" if big and r >= 3.0 else "不达标")
    print(f"  {fg_hex:>9} on {bg_hex:<9} = {r:5.2f}:1  [{tag}/{flag}]  阈值{need}  "
          + (note if note else ""))
    return ok

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    print("WCAG 2.1 对比度核算（AA）\n" + "-" * 60)
    if args[0] == "-f":
        path = args[1]
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('::')
                if len(parts) < 2:
                    continue
                fg, bg = parts[0], parts[1]
                note = parts[2] if len(parts) > 2 else ""
                check(fg, bg, note)
        return
    # 单对 or 多对（:: 分隔）
    for a in args:
        if '::' in a:
            parts = a.split('::')
            check(parts[0], parts[1], parts[2] if len(parts) > 2 else "")
        else:
            # 两两配对
            pass
    # 若只给了一个参数（视为 fg bg 相邻），兜底：无

if __name__ == "__main__":
    main()
