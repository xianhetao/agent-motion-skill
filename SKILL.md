---
name: agent-motion
description: 把口播视频/讲稿做成「理解文案」的导演式短视频。当用户要做口播短视频、知识讲解、企业宣传口播，或提到「口播包装」「talking-head」「花字」「数字卡」「章节卡」「名牌」「导演式包装」「口播成片」「按口播出元素」「元素动画」时使用。三条路线：C 用 huashu-motion talking-head 模板（默认）；D 用原生 Three.js 逐帧工程（需要逐元素按口播调度、完全自定义视觉时用）；另有剪映草稿与 FFmpeg 直烧兜底。不论走哪条，都必须遵守 references/design_principles.md 的动效与排版规范。
---

# Agent Motion · 口播导演包装

## Overview

把「口播视频 + 字幕/讲稿」做成**真正理解文案**的短视频包装：数据 count-up 卡、金句花字、章节卡、名牌、角标，全部**卡在说到的词上**，而不是机械铺字幕。

核心路线（路线 C）依赖 [`huashu-motion`](../../huashu-motion/SKILL.md) 技能的 `om` CLI 与 talking-head 模板做导演式合成；另外保留两条兜底路线——剪映草稿（需二次精修）和 FFmpeg 直烧字幕（只要成片、不要编辑）。

**先理解、再包装**：开工第一件事是看片 + 读字幕，写出分镜细案（强化段 / 金句 / 数据块 / 章节），再决定每张卡片卡在哪句话上。否则容易回到「机械铺字幕」——这是用户明确否决过的方向。

## 三条路线选型

| 路线 | 何时用 | 引擎 | 交付 |
|---|---|---|---|
| **C · 导演式（默认）** | 要「理解文案」的包装、数据/金句可视化、口播成片 | huashu-motion `om` + talking-head 模板 | 自带音轨的 MP4 |
| **D · 原生工程** | 模板不够：要逐元素按口播调度、自绘图表/白板/卡片系统、完全控制每帧构图 | 自建 Three.js 工程 + 逐帧截图 + ffmpeg | 自带音轨的 MP4 |
| **B · FFmpeg 直烧** | 不要二次编辑、只要成片；剪映打不开草稿时 | `srt_to_ass.py` + ffmpeg | 烧录字幕/卡片的 MP4 |
| **A · 剪映草稿** | 需要在剪映里精修/加特效 | `build_jianying.py` | 剪映工程文件夹 |

> 路线 A/B 在新版剪映专业版上有兼容性问题（旧 `draft_content.json` 格式不被识别、FFmpeg 路线只适合轻量字幕）。
> **默认走路线 C**；当用户要求「每个元素跟着口播一个一个出」「这一段要重做视觉」「按我说的改动画」这类
> **逐元素控制**时，切到路线 D（参考实现 `work/test-01/film/`，v4→v18 迭代 14 版）。

## 通用前置（两条路线都要）

开工第一件事是看片 + 读字幕，写出分镜细案（强化段 / 金句 / 数据块 / 章节），再决定每张卡片卡在哪句话上。
否则容易回到「机械铺字幕」——这是用户明确否决过的方向。

动效与排版**不是自由发挥**：`references/design_principles.md` 是用户反复验收后拍板的硬规则
（生命周期、入画落视觉中心、组间距、脉冲缩放必须归位、硬切原则、图片规范等），开工前必读。

## 路线 C：导演式包装（核心）

### 流程

```bash
OM="$HOME/.workbuddy/skills/huashu-motion/bin/om"

# 1) 新建 talking-head 工程（模板来自 huashu-motion）
"$OM" new <dir> --template talking-head

# 2) 竖屏源（抖音/视频号/小红书）先转 9:16，避免 cover 裁切切到脸
"$OM" fork <dir> <dir-v> --size 1080x1920
#    横屏源（B站/官网）可跳过此步

# 3) 配置：注入 om-cues（口播词时间轴）+ 卡片变量（名牌/数字卡/花字/章节/角标）
#    config.json 见 references/workflow_director.md；脚本会自动去掉 footage 的 muted
python3 scripts/configure.py --dir <dir-v> --srt 字幕.srt --config config.json

# 4) 冒烟：抽几帧看卡片落点和人脸避让（务必先做，再整片渲染）
"$OM" look --at 3 . --dir <dir-v>     # 名牌
"$OM" look --at 45 .                  # 金句花字

# 5) 渲染（--frames jpg 必填，否则抽帧缓存膨胀到几十 GB）
"$OM" render . --frames jpg --silent
```

### config.json 字段

```jsonc
{
  "talk": "/abs/path/口播.mp4",        // 覆盖模板默认（留空=占位提示）
  "name": "主讲",                       // 名牌·姓名
  "role": "企业内容营销 · 筛选与把关",   // 名牌·身份
  "nameTag": "主讲",                    // 名牌·小标
  "corner": "企业内容观察",             // 右上角标
  "stats": [                            // 数字 count-up 卡，cue 锚定说到的词
    {"value": 1.2, "suffix": "亿", "label": "全网播放", "cue": "播放量", "at": 89.9},
    {"value": 22.8, "suffix": "万", "label": "30天涨粉", "cue": "涨粉", "at": 93.7}
  ],
  "keywords": [                         // 金句花字，cue 命中的真实说话时刻优先于 at
    {"text": "不是创意，是筛选和把关", "cue": "把关", "at": 41.9, "hold": 5.0},
    {"text": "主号保调性，子号做试验", "cue": "子号", "at": 131.3, "hold": 4.0}
  ],
  "chapter": "真正缺的能力",            // 章节卡标题（留空不出）
  "chapterNo": "PART 03",
  "chapterAt": 38.0,
  "chapterHold": 2.4
  // 配色可选：accent / ink / card / statTint / highlight
}
```

字段与 talking-head 模板的 composition variables 一一对应（`name`/`role`/`stats`/`keywords`/`chapter*`/`corner`/`talk` 等）。`cue` 命中词表时以**真实说话时刻**为准覆盖 `at`；cue 搜不到就落到兜底 `at`。

### 实战坑位（已踩，必看）

- **Chrome 启动崩溃**：`Chrome exited (null)` 的真凶通常是 macOS 上 Chrome 自身 GPU 子进程沙箱崩溃（stderr 有 `GPU process isn't usable`）。已给 huashu-motion 的 `cli/lib/cdp.js` 打本地补丁：darwin 也加 `--no-sandbox`（npx 重装后需重打）。命令仍要前台 + `dangerouslyDisableSandbox`（后台任务放行不生效）。
- **`om new` 残缺模板**：WorkBuddy 沙箱下 `om new` 可能 CODEBUDDY_BROKER_DENY，产出**缺 `<body>` 的残缺 index.html**（渲染报 `composition has no timeline`）。对策：从已知可用工程复制完整 `index.html` + `vendor/om.js` + `assets/fonts/` 后再跑 configure.py。
- **音频**：talking-head 模板的 `<video id="talk">` 默认 `muted`，不处理则成片无声。`configure.py` 已自动删除 muted；若手动改模板记得删。删掉后 `om render` 自动把原片音轨 `direct` mux 进成片。
- **`--frames` 必填 `jpg`**：不传默认 png，逐帧抽帧缓存会膨胀到几十 GB。
- **横竖屏**：竖屏源（如 1440×2560）别直接在横屏画布渲染——`cover` 裁切会把脸切掉。`om fork --size 1080x1920` 转竖屏重渲。
- **原片硬字幕**：可保留（口播标准形态，模板 cardBottom 自动给字幕留位）；只有笔误等局部问题用**限时 delogo**擦那一小段，其余原样保留：
  `ffmpeg -i 口播.mp4 -vf "delogo=x=280:y=1890:w=880:h=150:enable='between(t,89.4,93.6)'" -c:v libx264 -crf 18 -c:a copy assets/talk_clean.mp4`
- **cue 词表**：来自 ASR，措辞可能与 cue 不一致（如说「子号」ASR 写成全句）——cue 搜不到就落兜底 `at`，不影响出片。om-cues 的 words 字段名是 `word`（不是 `text`）。

## 路线 B：FFmpeg 直烧字幕（兜底）

SRT → ASS（tech 风格：亮青底字幕 + 青色强调卡片）→ ffmpeg `subtitles` 滤镜烧录。

```bash
python3 scripts/srt_to_ass.py 字幕.srt --out tech.ass
# 强调卡/笔误修正改脚本顶部的 CARDS / FIXES，或用 --cards / --fixes 传入 JSON
ffmpeg -y -i 口播.mp4 -vf "subtitles=/abs/path/tech.ass" \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 160k 成片.mp4
```

注意：ASS 必须用**绝对路径**（subtitles 滤镜不认 `~` 也不认后台任务的相对 cwd）；颜色是 `&HAABBGGRR`（BGR 顺序）；输入侧 `-ss` 在 HEVC 上有 seek 假象，验证用**输出侧** `-ss`。

## 路线 A：剪映草稿（兜底，需精修时）

```bash
python3 scripts/srt_to_shotlist.py 字幕.srt --video 口播.mp4 --out shot_list.json
python3 scripts/build_jianying.py --list shot_list.json --template assets/template-modern.json
# 默认直接写入本机剪映草稿目录（~/Movies/JianyingPro/.../com.lveditor.draft），重启剪映可见
```

> 新版剪映专业版草稿主文件是私有格式，旧 `pyJianYingDraft` 生成的 `draft_content.json` 可能显示 0KB/00:00。此路线仅作兜底，优先路线 C。

## 路线 D：原生 Three.js 工程（逐元素控制）

模板解决不了时用：需要每个元素按口播逐个出场、自绘卡片/图表系统、完全控制构图。
代价是开发量大、每次改动都要重渲（全片 142s 约 15 分钟）。

**核心约定**：状态采样（`seq2.js`，纯函数 `t → 状态`）与渲染应用（`stage2.js`）分离；
改时间只动 seq2，改视觉只动 stage2。

```bash
node check-frames.mjs 52.0 79.8 91.0          # 静帧验证：秒级出图，改完立刻目检
node render.mjs 38.9 80.0                     # 分段渲染（后台跑）
python3 scripts/verify_segments.py --from concat-list-v10.txt --source ../source.mp4   # concat 前必跑
```

完整流程、目录结构、7 个必踩坑位（**帧目录残留导致音画漂移、外插片段无音轨、
新 mesh 忘关 visible、抽帧落在旧关键帧**等）见 `references/native_engine.md`。

## 字体选型（别靠猜，出样张）

汉字字重/字体的观感（尤其横画粗细）在代码里看不出来，必须拉到实际字号比对：

```bash
python3 scripts/font_compare.py --text "门槛几乎 降到零" \
  --row "A 现状 得意黑:Smiley Sans:400:150" \
  --row "B Noto 700:Noto Sans SC:700:150" \
  --row "C Noto 900:Noto Sans SC:900:150" \
  --font-dir /path/to/fonts --out font-compare.html
# 再截图给用户目测（走本地 server，file:// 会因 CORS 加载不到字体）
```

规范见 `references/design_principles.md` §5：**中文只用 Noto Sans SC 两档（正文 500、强调 900）**，
不要用 600/700 当强调，也不要用横细竖粗的展示字体（得意黑已被否决）。

## 风格参考与样张（加选项，不加禁令）

来源：huashu-design 3.0（路线 C 引擎 huashu-motion 的设计方法论，2026-10-23）。核心三条，开工前必读 `references/style_reference.md`：

- **加选项，不加禁令**：风格多样性不要用「别用 X」表达（会逼 agent 躲到最安全最无聊的长相）；改成给 2–3 个候选方向 + 样张。硬规则（design_principles）是对错线，必须守，不在此列。
- **先出候选方向，再定稿**：开工前摆 2–3 个视觉方向（配色 + 版式 + 参考片），够好 / 彼此差异明显 / 不撞近期项目三选，确认再渲。
- **参考板（ref_board）：同媒介、先截图**：参考片必须是同形态口播/短视频，抽关键帧拼板先看再定（`scripts/ref_board.py`）；字体样张用 `scripts/font_compare.py`。
- **外观账本 + 成片体检**：交付记一笔外观、下个片主动错开；成片只查事实（裂帧/字太小/对比度/撞外观/换皮），见 review_loop.md。

## 交付后清理

定稿后清理中间产物（各版成片、逐帧目录、历史测试段、QC 抽帧），只留真值 + 成品段构件 + 成片。
分类方法、执行规则（先报告→用户选档→白名单→`trash` 分批→每批验证）见 `references/delivery_cleanup.md`。
参考量级：142s 竖屏工程一轮回收 **3.6 GB**。

## 理解文案：分镜规划

开工前先写分镜细案，方法见 `references/planning_guide.md`：读片 → 标强化段（钩子/核心论点/警告）→ 标金句（卡花字）→ 标数据块（卡 count-up）→ 标章节。这一步决定了卡片卡在哪、什么时候出，是「理解文案」和「机械铺字幕」的分水岭。

## 验收迭代（用户截图 → 下一版）

口播包装不是一次做对的活。用户会给截图 + 口语反馈，闭环是：
翻译成可执行的视觉问题 → 按时间点定位代码 → 改 → **静帧验证（不能省）** → 只重渲受影响分段 → 成片抽帧 QC → 交付并逐条说明。

口语反馈的翻译对照表、定位技巧、交付说明写法见 `references/review_loop.md`。

## Resources

- `scripts/configure.py` — 路线 C 核心：SRT→om-cues 注入 + 卡片变量配置（自动去 muted）
- `scripts/verify_segments.py` — 路线 D：concat 前校验各段帧数/音轨，并给出修复命令
- `scripts/font_compare.py` — 字体对比样张生成（选字体前先出图目测）
- `scripts/ref_board.py` — 参考片关键帧板（同媒介参考，先截图再看；对标 huashu-design 3.0 的 ref_board）
- `scripts/wcag_check.py` — 文字/背景对比度核算（WCAG 2.1 AA；改配色前先核每一处配对，避免亮橙压白底这类不达标）
- `scripts/srt_to_ass.py` — 路线 B：SRT→tech 风格 ASS
- `scripts/build_jianying.py` — 路线 A：剪映完整工程生成
- `scripts/srt_to_shotlist.py` — 路线 A：SRT→shot_list.json
- `references/design_principles.md` — **动效与排版硬规则（用户拍板，开工前必读）**
- `references/native_engine.md` — 路线 D：原生工程结构、渲染管线、7 个必踩坑位
- `references/review_loop.md` — 验收迭代：口语反馈翻译表、定位技巧、交付说明写法
- `references/delivery_cleanup.md` — 交付后清理：分类、白名单、`trash` 分批执行规则
- `references/style_reference.md` — **风格参考与样张方法论（huashu-design 3.0 沉淀：加选项不加禁令 / 参考板 / 外观账本）**
- `references/workflow_director.md` — 路线 C 端到端流程 + cue/坑位详解
- `references/planning_guide.md` — 理解文案·分镜规划方法
- `references/shot_list_spec.md` — 路线 A 的 shot_list 格式规范
- `assets/template-*.json` — 路线 A 风格模板（modern/tech/magazine）
