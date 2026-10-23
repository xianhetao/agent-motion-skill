#!/usr/bin/env python3
"""生成「参考片关键帧板」HTML —— 给 agent / 用户看得见的同媒介参考。

huashu-design 3.0 的 ref_board.py 把参考作品截成参考板，agent 亲眼看过再动手。
口播版：给定若干参考短视频（本地文件），用 ffmpeg 抽关键帧，拼成带时间戳/标注的板，
先看板、再定视觉方向（不要凭空想象）。

用法：
    python3 ref_board.py ref1.mp4 ref2.mp4 --out board.html --frames 6
    python3 ref_board.py ref1.mp4 --at 3,12,40 --out board.html          # 指定秒数抽帧
    python3 ref_board.py ref1.mp4 ref2.mp4 --label "竖屏知识解说:品牌口播" --out board.html

--frames N  每片均匀抽 N 帧（默认 6）
--at t1,t2  改为按指定秒数抽帧（每片相同时刻，逗号分隔）
--label "a:b:..."  每片标签（与文件顺序对应；缺省用文件名主干）
--cols N    板每行几列（默认 3）

依赖 ffmpeg / ffprobe（~/.local/bin 或 PATH）。生成后建议走本地 server 截图看
（图片用 file:// 能加载，但若板里混了 webfont 样张需注意 CORS；稳妥：起 http.server）。
"""
import argparse
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


def find_bin(name):
    for cand in (os.path.expanduser("~/.local/bin/" + name),
                "/opt/homebrew/bin/" + name,
                "/usr/local/bin/" + name):
        if os.path.exists(cand):
            return cand
    found = shutil.which(name)
    return found or name  # 找不到就留原名，让报错清晰


FFMPEG = find_bin("ffmpeg")
FFPROBE = find_bin("ffprobe")


def probe_duration(path):
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "xml", path],
            capture_output=True, text=True, timeout=30)
        root = ET.fromstring(out.stdout)
        # duration 是 <format> 的属性，不是子元素文本
        fmt = root.find(".//format")
        d = fmt.get("duration") if fmt is not None else None
        return float(d) if d else None
    except Exception as e:
        print(f"[!] 取时长失败 {path}: {e}", file=sys.stderr)
        return None


def extract_frame(video, t, out_path):
    r = subprocess.run(
        [FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
         "-q:v", "3", out_path],
        capture_output=True, text=True, timeout=60)
    return r.returncode == 0 and os.path.exists(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+", help="参考短视频（本地文件，同形态口播/短视频）")
    ap.add_argument("--out", default="ref-board.html")
    ap.add_argument("--frames", type=int, default=6, help="每片均匀抽 N 帧")
    ap.add_argument("--at", default="", help="改为按指定秒数抽帧：3,12,40")
    ap.add_argument("--label", default="", help="每片标签，冒号分隔：a:b:c")
    ap.add_argument("--cols", type=int, default=3)
    args = ap.parse_args()

    labels = args.label.split(":") if args.label else []
    ats = []
    if args.at:
        try:
            ats = [float(x) for x in args.at.split(",") if x.strip() != ""]
        except ValueError:
            print("[!] --at 需为逗号分隔的数字", file=sys.stderr)
            sys.exit(2)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    base = os.path.splitext(os.path.basename(args.out))[0]
    frame_dir = os.path.join(out_dir, base + "_frames")
    os.makedirs(frame_dir, exist_ok=True)

    cells = []  # (label, [(rel_path, t), ...])
    for i, v in enumerate(args.videos):
        if not os.path.exists(v):
            print(f"[!] 找不到 {v}，跳过", file=sys.stderr)
            continue
        dur = probe_duration(v)
        lab = labels[i] if i < len(labels) and labels[i] else os.path.splitext(os.path.basename(v))[0]
        if ats:
            ts = ats
        elif dur and dur > 0:
            ts = [dur * (k + 0.5) / args.frames for k in range(args.frames)]
        else:
            ts = [0.0]
        frames = []
        for j, t in enumerate(ts):
            fp = os.path.join(frame_dir, f"v{i}-{j}.jpg")
            if extract_frame(v, t, fp):
                frames.append((os.path.relpath(fp, out_dir), t))
        if frames:
            cells.append((lab, dur, frames))
        else:
            print(f"[!] {v} 没抽到帧，跳过", file=sys.stderr)

    if not cells:
        print("[!] 没有任何帧，退出", file=sys.stderr)
        sys.exit(1)

    def cell_html(lab, dur, frames):
        imgs = "\n".join(
            f'        <figure><img loading="lazy" src="{p}">'
            f'<figcaption>{t:.1f}s</figcaption></figure>' for p, t in frames)
        dur_s = f"{dur:.1f}s" if dur else "?"
        return (f'    <section>\n'
                f'      <h3>{lab} <span class="dur">· {dur_s}</span></h3>\n'
                f'      <div class="strip">\n{imgs}\n      </div>\n'
                f'    </section>')

    body = "\n".join(cell_html(*c) for c in cells)
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>参考片关键帧板</title>
<style>
  html,body{{margin:0;background:#1c1d22;color:#e8e8ea;font-family:-apple-system,"PingFang SC","Noto Sans SC",sans-serif;}}
  .wrap{{max-width:1100px;margin:0 auto;padding:32px 28px 64px;}}
  h1{{font-size:22px;margin:0 0 4px;}}
  .tip{{font-size:13px;color:#9a9aa2;margin:0 0 24px;}}
  section{{margin:0 0 28px;background:#26272e;border-radius:14px;padding:16px 18px;}}
  h3{{font-size:16px;margin:0 0 12px;}}
  h3 .dur{{color:#8a8a92;font-weight:400;font-size:13px;}}
  .strip{{display:grid;grid-template-columns:repeat({args.cols},1fr);gap:10px;}}
  figure{{margin:0;}}
  figure img{{width:100%;border-radius:8px;display:block;background:#000;}}
  figcaption{{font-size:11px;color:#8a8a92;text-align:center;margin-top:4px;}}
</style></head>
<body><div class="wrap">
  <h1>参考片关键帧板</h1>
  <p class="tip">同形态口播/短视频的关键帧 —— 先看板，再定视觉方向（加选项，不加禁令）。</p>
{body}
</div></body></html>"""

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    n = sum(len(f) for _, _, f in cells)
    print(f"[+] 参考板已生成 {args.out}（{len(cells)} 部片 / {n} 帧，存于 {frame_dir}）")
    print("[i] 看板建议走本地 server：cd 到输出目录，`python3 -m http.server` 后浏览器打开，"
          "或用项目自带 server + Chromium fullPage 截图")


if __name__ == "__main__":
    main()
