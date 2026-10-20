# shot_list.json 分镜格式规范

本格式是 koubo-video 的核心数据契约：AI 规划分镜后产出，脚本 `scripts/build_jianying.py` 读取后生成剪映草稿。

## 顶层结构

```json
{
  "meta": { ... },
  "segments": [ ... ]
}
```

## meta 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | string | 否 | 工程标题，用于草稿文件夹名 |
| resolution | [w, h] | 否 | 画幅；竖屏 `[1080,1920]` / 横屏 `[1920,1080]`。缺省由模板预设决定 |
| fps | int | 否 | 帧率，默认 30 |
| video_path | string | 否 | 口播视频/音频路径；缺省则仅生成文字/图片轨 |
| template | string | 否 | 风格模板 id：`modern` / `tech` / `magazine`，缺省 `modern` |
| layout | string | 否 | `"portrait"` / `"landscape"`，强制覆盖画幅 |

## segments 字段

每条 segment 是一段时间内的视觉元素。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| start | float | 是 | 起始秒 |
| end | float | 是 | 结束秒 |
| anim_type | string | 是 | 见下方取值 |
| text | string | 否 | 文字内容（title / body / subtitle） |
| image | string | 否 | 图片路径（anim_type = image 时必填） |
| visual | object | 否 | 样式覆盖：`font_size` / `color` / `bold` / `pos_x` / `pos_y` / `align` / `bg` |
| keyword | string | 否 | 在 text 中高亮的关键词，使用模板 `keyword.color` |
| transition | string | 否 | 段间转场：`fade` / `slide` / `none`（MVP 预留，剪映精修） |

## anim_type 取值

- `title` — 标题大字，套用模板 `title` 样式
- `body` — 正文段落，套用模板 `body` 样式
- `subtitle` — 底部字幕条，套用模板 `subtitle` 样式（带背景）
- `image` — 图片元素，按模板 `image_pos` 定位（需 `image` 字段，且环境支持 ImageMaterial）
- `none` — 空段（占位 / 停顿，不生成任何元素）

## 时间约束

- segment 按 `start`/`end` 排序，可无缝衔接，也可留白（无段区间显示背景）。
- 总时长建议与口播视频时长一致；无口播视频时由 segments 决定。
- 同一条文字轨上的文字段不应时间重叠；图片段可与其他段并行。
- `end - start` 至少 0.1 秒，过短会被脚本拉到最小值。

## 坐标约定

- `pos_y` / `pos_x` 为归一化比例（0=顶/左，1=底/右，0.5=居中）。
- 脚本内部换算为剪映 `transform_y = (pos_y - 0.5) * 2.0` 等。
- 文字默认居中（`align` 省略）；`align: "left"` 时配合 `pos_x` 做左对齐起点。
