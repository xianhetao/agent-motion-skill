# 导演式包装 · 端到端工作流（路线 C）

依赖 [`huashu-motion`](../SKILL.md) 技能的 `om` CLI 与 talking-head 模板。本文件是实战跑通后沉淀的完整流程 + 坑位。

## 前提

- 已安装 `huashu-motion` 技能（提供 `~/.workbuddy/skills/huashu-motion/bin/om` 与 talking-head 模板）。
- 本机有 Chrome（om 驱动它截帧/渲染）、FFmpeg（导出/抽帧）、Node 22+。
- 口播视频 + 对应 SRT 字幕（字幕用于生成 om-cues 词时间轴；没有 SRT 时可用 `om voice` 提词，或手填 `length`）。

## 端到端流程

```bash
OM="$HOME/.workbuddy/skills/huashu-motion/bin/om"
SRC="/abs/path/口播.mp4"
SRT="/abs/path/字幕.srt"

# 1) 新建工程（模板来自 huashu-motion）
"$OM" new my_film --template talking-head

# 2) 竖屏源（抖音/视频号/小红书）转 9:16；横屏源跳过
"$OM" fork my_film my_film_v --size 1080x1920

# 3) 配置：注入 om-cues + 卡片变量（自动删 footage muted）
python3 scripts/configure.py --dir my_film_v --srt "$SRT" --config config.json
#    只注入词时间轴（不配卡片）: 省略 --config
#    只覆盖口播路径: --talk "$SRC"

# 4) 冒烟：抽帧看落点 + 人脸避让（务必先做！再整片渲染）
"$OM" look --at 3 my_film_v      # 名牌 + 人脸完整度
"$OM" look --at 45 my_film_v     # 金句花字
"$OM" look --at 92 my_film_v     # 数字卡

# 5) 渲染（--frames jpg 必填）
"$OM" render my_film_v --frames jpg --silent
#    输出 my_film_v/out/*.mp4，自带音轨（sound direct）
```

## config.json 字段（与模板 composition variables 对应）

| 字段 | 类型 | 说明 |
|---|---|---|
| `talk` | string | 口播视频绝对路径，覆盖模板默认（留空=占位提示） |
| `name` / `role` / `nameTag` | string | 名牌：姓名 / 身份 / 小标 |
| `nameCue` / `nameAt` / `nameHold` | string/float | 名牌锚定词 / 兜底时刻 / 停留 |
| `corner` / `cornerPos` / `cornerAt` | string | 角标：文案 / 位置(tl/tr/auto) / 出现时刻 |
| `stats` | JSON 数组 | 数字 count-up 卡：`{value, prefix?, suffix?, label, cue?, at?, hold?}` |
| `statTint` | color | 数字卡底色 |
| `keywords` | JSON 数组 | 金句花字：`{text, cue?, at?, hold?}` |
| `highlight` | color | 花字底色 |
| `chapter` / `chapterNo` / `chapterCue` / `chapterAt` / `chapterHold` | string/num | 章节卡 |
| `videoFit` | enum | `cover`(铺满裁切)/`contain`(完整留边) |
| `focusX` / `focusY` | number | cover 裁切焦点（%） |
| `subjectX/W/Top/Bottom` | number | 人物避让区（0–1 画面比例） |
| `cardBottom` | number | 卡片底边 Y（0=自动，竖屏 0.74 下方留给字幕） |
| `accent` / `ink` / `card` | color | 配色 |

> 多章节：模板单 `chapter` 变量只承载一段章节卡。需要多幕章节时，扩展 `keywords`/额外 DOM，或后续版本升级模板。

## cue 机制（为什么卡片能卡在说到的词上）

- `configure.py` 把 SRT 解析成 om-cues 的 `words:[{word, start, end}]`（**字段名是 `word`，不是 `text`**）。
- 模板运行时 `OM.cue("把关")` 在所有 words 里搜包含「把关」的句子，返回其 `start` 作为卡片浮现时刻。
- **cue 命中 → 以真实说话时刻为准**（覆盖手配 `at`）；cue 搜不到 → 落到兜底 `at`。
- ASR 写法可能与 cue 不一致（如说「子号」ASR 写成「拿这个子号去做试验」）——只要句子里含 cue 子串就能命中，不必完全一致。洁丽雅案例里「子号」实测卡在 134.4s 说出瞬间，比手配 131.3s 更准。

## 实战坑位（已踩，必看）

1. **沙箱放行**：WorkBuddy 里 `om render`/`om look` 必须 `dangerouslyDisableSandbox`（Chrome 被签名克隆层拦截会报 `Chrome exited (null)`）。且**后台任务不生效**——用前台运行不加 timeout，超时自动转后台、放行属性跟随进程。
2. **音频无声**：talking-head 模板 `<video id="talk">` 默认 `muted`，不处理则成片无声。`configure.py` 已自动删除 muted；删掉后 `om render` 自动把原片音轨 `direct` mux 进成片（log 显示 `sound direct`）。
3. **`--frames` 必填 `jpg`**：不传默认 png，逐帧抽帧缓存会膨胀到几十 GB（一支 2 分钟片可占 10GB+）。
4. **横竖屏**：竖屏源（如 1440×2560）别直接在横屏画布渲染——`cover` 裁切会把脸切掉。务必 `om fork --size 1080x1920` 转竖屏重渲。横屏源可直接渲。
5. **原片硬字幕**：可保留（口播标准形态，模板 `cardBottom` 自动给字幕留位）。只有笔误等局部问题用**限时 delogo** 擦那一小段，其余原样保留：
   ```bash
   ffmpeg -i "$SRC" -vf "delogo=x=280:y=1890:w=880:h=150:enable='between(t,89.4,93.6)'" \
     -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -c:a copy my_film_v/assets/talk_clean.mp4
   # 然后 configure.py --talk assets/talk_clean.mp4（路径相对工程目录或绝对）
   ```
6. **验证用输出侧 `-ss`**：`ffmpeg -i 成片.mp4 -ss 91 -frames:v 1 f.png`；输入侧 `-ss` 在 HEVC 上有 seek 假象，会误判字幕错位。

## 交付前验证清单

- [ ] `om look --at 3` 名牌 + 人脸完整（竖屏未被裁切）
- [ ] 每张金句花字在说出该词时浮现（cue 锚定）
- [ ] 数字卡 count-up 在说到数字时出现
- [ ] 章节卡位置/文字正确
- [ ] 角标出现
- [ ] `ffprobe` 确认成片有音轨（sound direct）
- [ ] 无笔误/双字幕（必要时 delogo 已处理）
