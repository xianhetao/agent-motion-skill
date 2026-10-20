#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
口播视频 · 剪映草稿生成器（koubo-video 技能）

读取 shot_list.json + 风格模板，生成剪映草稿 draft_content.json：
- 主轨：口播视频（video_path 缺省则留空，可在剪映补）
- 文字轨：title / body / subtitle 文字段，套用模板样式与位置
          subtitle 自动带背景条并标记为字幕类型
- 图片轨（可选）：image 段，需 pyJianYingDraft 支持 ImageMaterial（当前版本不支持，会自动跳过并警告）

用法：
  python3 build_jianying.py --list shot_list.json \
      --template ../assets/template-modern.json
  # 默认直接写入本机剪映草稿目录（~/Movies/JianyingPro/.../com.lveditor.draft），重启剪映即可见
  # 自定义草稿目录：--draft-dir /path/to/com.lveditor.draft
  # 或直出单文件：--out /path/to/draft_content.json
  # 或强制画幅：--layout portrait|landscape

依赖：pip install pyJianYingDraft
"""
import argparse
import json
import os
import sys

# 本机剪映草稿根目录（剪映专业版 VideoFusion，数据在 ~/Movies 而非 ~/Library）
# 默认直接写入此处，运行后重启剪映即可在草稿栏看到工程；可用 --draft-dir 覆盖。
DEFAULT_DRAFT_DIR = "~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"


def _rgb(hexstr):
    hexstr = (hexstr or "#FFFFFF").lstrip("#")
    if len(hexstr) < 6:
        hexstr = hexstr + "0" * (6 - len(hexstr))
    r = int(hexstr[0:2], 16) / 255.0
    g = int(hexstr[2:4], 16) / 255.0
    b = int(hexstr[4:6], 16) / 255.0
    return (r, g, b)


def load_template(path):
    if not path:
        return None
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        return json.load(f)


def layout_block(tpl, layout):
    if not tpl:
        return None
    return tpl.get(layout) or tpl.get("portrait")


def _align_of(ts):
    a = ts.get("align")
    if a == "left":
        return 0
    if a == "right":
        return 2
    return 1  # 默认居中


def make_background(bg_hex):
    if not bg_hex:
        return None
    try:
        from pyJianYingDraft.text_segment import TextBackground
        return TextBackground(color=bg_hex, style=1, alpha=0.9, height=0.13, round_radius=0.04)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True, help="shot_list.json 路径")
    ap.add_argument("--template", default=None, help="风格模板 JSON")
    ap.add_argument("--draft-dir", default=None, help="剪映草稿根目录（生成完整可打开工程）")
    ap.add_argument("--project", default=None, help="输出完整工程文件夹路径（含 draft_meta_info.json）")
    ap.add_argument("--out", default=None, help="直接输出单个 draft_content.json 路径")
    ap.add_argument("--layout", default=None, choices=["portrait", "landscape"])
    args = ap.parse_args()

    try:
        import pyJianYingDraft as jy
    except Exception as e:
        print("缺少依赖 pyJianYingDraft，请先: pip install pyJianYingDraft")
        print("错误:", e)
        sys.exit(1)

    with open(os.path.expanduser(args.list), encoding="utf-8") as f:
        sl = json.load(f)
    meta = sl.get("meta", {})
    tpl = load_template(args.template)

    res = meta.get("resolution")
    if not res and tpl:
        lb0 = layout_block(tpl, "portrait")
        res = (lb0 or {}).get("resolution")
    w, h = (res or [1080, 1920])[0], (res or [1080, 1920])[1]
    fps = meta.get("fps", 30)
    layout = args.layout or meta.get("layout") or ("portrait" if h >= w else "landscape")
    lb = layout_block(tpl, layout)
    video = meta.get("video_path")

    script = jy.ScriptFile(w, h, fps, True)

    # 主轨：口播视频
    video_track = script.append_track(jy.TrackSpec(track_type=jy.TrackType.video))
    if video and os.path.exists(os.path.expanduser(video)):
        vp = os.path.expanduser(video)
        vm = jy.VideoMaterial(vp)
        # trange_seconds 按秒构造；VideoMaterial.duration 为微秒，需换算
        vdur = vm.duration / 1_000_000.0
        script.add_segment(jy.VideoSegment(vm, jy.trange_seconds(0, duration=vdur)), track=video_track)
    else:
        print("提示: 未提供有效口播视频路径，仅生成文字/图片轨（可在剪映补主轨）。")

    # 图片轨（可选）
    has_img = hasattr(jy, "ImageMaterial") and hasattr(jy, "ImageSegment")
    img_track = script.append_track(jy.TrackSpec(track_type=jy.TrackType.video)) if has_img else None

    # 文字轨（正文/字幕）与 标题轨（封面/章节标题）分轨，避免同轨重叠报错
    text_track = script.append_track(jy.TrackSpec(track_type=jy.TrackType.text))
    title_track = script.append_track(jy.TrackSpec(track_type=jy.TrackType.text, name="title"))

    for seg in sl.get("segments", []):
        at = seg.get("anim_type")
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start + 3))
        dur = max(0.1, end - start)
        vis = seg.get("visual") or {}

        if at == "image":
            if not img_track:
                print("警告: 跳过 image 段（pyJianYingDraft 不支持 ImageMaterial）。")
                continue
            ip = vis.get("image") or seg.get("image")
            if not ip or not os.path.exists(os.path.expanduser(ip)):
                print("警告: 跳过 image 段，图片不存在:", ip)
                continue
            im = jy.ImageMaterial(os.path.expanduser(ip))
            script.add_segment(jy.ImageSegment(im, jy.trange(start, dur)), track=img_track)
            continue

        if at in (None, "none"):
            continue

        # 文字段 title / body / subtitle
        style_key = at if at in ("title", "body", "subtitle") else "body"
        ts = (lb or {}).get(style_key, {})
        content = seg.get("text") or (vis.get("content") if isinstance(vis.get("content"), str) else "")
        if not content:
            continue
        font_size = float(vis.get("font_size", ts.get("font_size", 64)))
        color = _rgb(vis.get("color", ts.get("color", "#FFFFFF")))
        bold = bool(vis.get("bold", ts.get("bold", False)))
        pos_y = float(vis.get("pos_y", ts.get("pos_y", 0.5)))
        pos_x = float(vis.get("pos_x", ts.get("pos_x", 0.5)))
        is_sub = (at == "subtitle")
        align = _align_of(ts)
        style = jy.TextStyle(
            size=font_size / 14.0,
            bold=bold,
            color=color,
            align=align,
            auto_wrapping=is_sub,
        )
        clip = jy.ClipSettings(
            transform_x=(pos_x - 0.5) * 2.0,
            transform_y=(pos_y - 0.5) * 2.0,
        )
        bg = make_background(ts.get("bg")) if is_sub else None
        seg_obj = jy.TextSegment(
            content,
            jy.trange_seconds(start, duration=dur),
            style=style,
            clip_settings=clip,
            background=bg,
        )
        # title 走独立标题轨，其余走文字轨
        track = title_track if at == "title" else text_track
        script.add_segment(seg_obj, track=track)

    # 输出
    def _ensure_meta(project_dir, w, h, fps, name):
        """用 DraftFolder 生成含 draft_meta_info.json 的完整工程文件夹，返回 draft_content.json 路径"""
        from pyJianYingDraft.draft_folder import DraftFolder
        parent = os.path.dirname(project_dir) or "."
        child = os.path.basename(project_dir) or name
        os.makedirs(parent, exist_ok=True)
        df = DraftFolder(parent)
        df.create_draft(child, w, h, fps, allow_replace=True)
        # 补全 meta 占位符（模板留空会导致剪映里工程名空白/版本缺失）
        meta_path = os.path.join(parent, child, "draft_meta_info.json")
        try:
            import json as _json
            with open(meta_path, encoding="utf-8") as _f:
                _m = _json.load(_f)
            _m["draft_name"] = (meta.get("title") or name)[:40]
            _m["draft_type"] = "normal"
            if not _m.get("version"):
                _m["version"] = 44
            with open(meta_path, "w", encoding="utf-8") as _f:
                _json.dump(_m, _f, ensure_ascii=False, indent=2)
        except Exception as _e:
            print("提示: meta 补全失败（不影响草稿内容）:", _e)
        return os.path.join(parent, child, "draft_content.json")

    if args.project:
        out_path = _ensure_meta(os.path.expanduser(args.project), w, h, fps,
                               (meta.get("title") or "koubo").replace(" ", "_"))
    elif args.draft_dir:
        draft_dir = os.path.expanduser(args.draft_dir)
        name = (meta.get("title") or "口播工程").replace(" ", "_")
        out_path = _ensure_meta(os.path.join(draft_dir, "koubo_" + name), w, h, fps, name)
    elif args.out:
        out_path = os.path.expanduser(args.out)
        if not out_path.endswith(".json"):
            out_path = _ensure_meta(out_path, w, h, fps, (meta.get("title") or "koubo").replace(" ", "_"))
        else:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    else:
        # 默认直接写入本机剪映草稿目录（剪映专业版数据在 ~/Movies）
        draft_dir = os.path.expanduser(DEFAULT_DRAFT_DIR)
        name = (meta.get("title") or "口播工程").replace(" ", "_")
        out_path = _ensure_meta(os.path.join(draft_dir, "koubo_" + name), w, h, fps, name)

    script.dump(out_path)
    print("剪映工程已生成:", out_path)
    if os.path.dirname(out_path):
        print("工程文件夹:", os.path.dirname(out_path))
    print("提示: 把工程文件夹放入剪映草稿目录（或直接在剪映中导入），打开即可精修导出。")


if __name__ == "__main__":
    main()
