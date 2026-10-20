#!/usr/bin/env python3
"""分段校验：concat 之前必跑。

口播包装走「分段渲染 + ffmpeg concat」时，最常见的灾难是**帧目录残留**导致某一段
多编进去几帧（甚至几百帧），后果是后面所有段落的音画整体漂移。这个脚本把人工核对
变成一条命令：

- 从文件名 `sample-<t0>-<t1>.mp4` 解析期望时长 / 期望帧数
- 用 ffprobe 精确计数视频帧（nb_read_frames，不信任容器里的 nb_frames）
- 对比音轨时长，检出「无音轨 / 音画不等长」这类静默杀手
- 对不匹配的段直接给出**修复命令**（显式 -frames:v 重编码）
- 可选生成 concat list

用法：
    python3 verify_segments.py --dir film                      # 校验目录下所有 sample-*.mp4
    python3 verify_segments.py --dir film --fps 30             # 指定帧率（默认 30）
    python3 verify_segments.py --dir film --concat list-v9.txt # 顺带生成 concat list
    python3 verify_segments.py --dir film --source ../source.mp4  # 修复命令里带上源片路径

退出码：0 全通过；1 存在 BAD。
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

NAME_RE = re.compile(r"sample-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\.mp4$")


def find_ffprobe():
    p = os.path.expanduser("~/.local/bin/ffprobe")
    if os.path.exists(p):
        return p
    return shutil.which("ffprobe") or "ffprobe"


def probe(ffprobe, f, stream, expr, count_frames=False):
    cmd = [ffprobe, "-v", "error", "-select_streams", stream]
    if count_frames:
        cmd.append("-count_frames")   # 帧数必须精确计数：容器里的 nb_frames 不可信
    cmd += ["-show_entries", expr, "-of", "csv=p=0", f]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None
    if out.returncode != 0:
        return None
    val = out.stdout.strip().strip(",")
    return val or None


def fmt(v):
    return "-" if v is None else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".", help="分段所在目录（含 sample-*.mp4）")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--tolerance", type=float, default=0.08,
                    help="音画时长容差（秒），默认 0.08")
    ap.add_argument("--source", default="../source.mp4", help="修复命令里的源片路径")
    ap.add_argument("--frames-dir", default="frames-sample", help="帧目录名（修复命令用）")
    ap.add_argument("--concat", default=None, help="生成 concat list 到该路径")
    ap.add_argument("--from", dest="from_list", default=None,
                    help="只校验该 concat list 里列出的段（推荐，避免扫到历史测试段）")
    args = ap.parse_args()

    ffprobe = find_ffprobe()
    if args.from_list:
        base_dir = os.path.dirname(os.path.abspath(args.from_list))
        files = []
        with open(args.from_list) as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("file"):
                    continue
                p = line.split("'", 1)[1].rsplit("'", 1)[0]
                files.append(os.path.join(base_dir, p))
    else:
        files = sorted(glob.glob(os.path.join(args.dir, "sample-*.mp4")))
    dedup, files_u = [], []
    for f in files:
        if f not in files_u:
            files_u.append(f)
    files = files_u
    if not files:
        print(f"[!] 没有可校验的分段（--from {args.from_list} / {args.dir}）")
        return 1

    rows, bad = [], []
    for f in files:
        base = os.path.basename(f)
        m = NAME_RE.search(base)
        # 外插片段（白板段/参考段等，非 sample- 命名）：重点只查「有没有音轨」
        if not m:
            adur = probe(ffprobe, f, "a:0", "stream=duration")
            adur = float(adur) if adur else None
            problems = [] if adur else ["外插片段无音轨（必查！concat 后会整体漂移）"]
            rows.append((base, 0.0, None, None, adur, problems))
            if problems:
                bad.append((base, 0.0, 0.0, None, problems))
            continue
        t0, t1 = float(m.group(1)), float(m.group(2))
        want_dur = t1 - t0
        want_frames = int(round(want_dur * args.fps))

        vframes = probe(ffprobe, f, "v:0", "stream=nb_read_frames", count_frames=True)
        vframes = int(vframes) if (vframes or "").isdigit() else None
        vdur = probe(ffprobe, f, "v:0", "stream=duration")
        vdur = float(vdur) if vdur else None
        adur = probe(ffprobe, f, "a:0", "stream=duration")
        adur = float(adur) if adur else None

        problems = []
        if vframes is None or vframes != want_frames:
            problems.append(f"帧数 {fmt(vframes)} != {want_frames}")
        if adur is None:
            problems.append("无音轨（concat 后会整体漂移！）")
        else:
            if abs(adur - want_dur) > args.tolerance:
                problems.append(f"音轨 {adur:.3f}s != {want_dur:.3f}s")
            if vdur is not None and abs(vdur - adur) > args.tolerance:
                problems.append(f"音画不等长 v={vdur:.3f} a={adur:.3f}")

        rows.append((base, want_dur, vframes, want_frames, adur, problems))
        if problems:
            bad.append((base, t0, want_dur, want_frames, problems))

    print(f"{'分段':<28}{'期望时长':>9}{'视频帧':>9}{'期望帧':>8}  {'音轨':>8}  状态")
    for base, want_dur, vframes, want_frames, adur, problems in rows:
        st = "OK" if not problems else "BAD " + "; ".join(problems)
        if not problems and want_frames is None:
            st = "OK · 外插片段（已确认有音轨）"
        wd = "-" if want_frames is None else f"{want_dur:.2f}"
        wf = "-" if want_frames is None else str(want_frames)
        print(f"{base:<28}{wd:>9}{str(vframes):>9}{wf:>8}  "
              f"{(f'{adur:.2f}' if adur is not None else '-'):>8}  {st}")

    if not bad:
        print("\n[OK] 全部分段通过，可以 concat。")
    else:
        print(f"\n[!] {len(bad)} 段需要修复。建议命令（显式帧数重编码，绕开帧残留）：\n")
        for base, t0, want_dur, want_frames, problems in bad:
            if want_frames is None:
                print(f"# {base}: {'; '.join(problems)}（外插片段，需手动补音轨）\n")
                continue
            f0 = int(round(t0 * args.fps))
            print(f"# {base}: {'; '.join(problems)}")
            print(f"ffmpeg -hide_banner -loglevel error -y \\")
            print(f"  -framerate {args.fps:g} -start_number {f0} -i {args.frames_dir}/f-%06d.jpg \\")
            print(f"  -ss {t0:g} -t {want_dur:g} -i {args.source} \\")
            print(f"  -map 0:v -map 1:a -frames:v {want_frames} \\")
            print(f"  -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 160k "
                  f"-movflags +faststart {os.path.join(args.dir, base)}\n")

    if args.concat:
        with open(args.concat, "w") as fh:
            for f in files:
                fh.write(f"file '{os.path.basename(f)}'\n")
        print(f"[+] concat list 已写入 {args.concat}"
              f"（注意：外插片段需手动加在最前/中间）")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
