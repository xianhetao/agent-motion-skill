---
name: agent-motion
description: 把口播视频/讲稿做成「理解文案」的导演式短视频。当用户要做口播短视频、知识讲解、企业宣传口播，或提到「口播包装」「talking-head」「花字」「数字卡」「章节卡」「名牌」「导演式包装」「口播成片」「按口播出元素」「元素动画」时使用。主路线 H 用 Python PIL+ffmpeg 混排直渲（满屏文字动画/人全屏+关键字/人+动效混合，默认）；C 用 huashu-motion talking-head 模板（标准化卡片备选）；D 用原生 Three.js 逐帧工程（极致逐元素/3D）；另有 FFmpeg 直烧兜底，剪映草稿已退役。不论走哪条，都必须遵守 references/design_principles.md 的动效与排版规范。
---

# Agent Motion · 口播导演包装

## Overview

把「口播视频 + 字幕/讲稿」做成**真正理解文案**的短视频包装：数据 count-up 卡、金句花字、章节卡、名牌、角标，全部**卡在说到的词上**，而不是机械铺字幕。

**主路线是 H（PIL+ffmpeg 混排直渲）**：用 Python PIL 逐帧画满屏文字动画 / 人全屏+关键字 / 人+动效混合，再 ffmpeg 合成编码，稳、无浏览器依赖。huashu-motion（路线 C）作为标准化卡片模板备选；Three.js（路线 D）留作极致逐元素/3D；剪映草稿（路线 A）已退役。

**先理解、再包装**：开工第一件事是看片 + 读字幕，写出分镜细案（强化段 / 金句 / 数据块 / 章节），再决定每张卡片卡在哪句话上。否则容易回到「机械铺字幕」——这是用户明确否决过的方向。

## 全流程方案（先设计对齐，再渲染）

开工**不要直接进渲染**。完整决策流见 `references/pipeline.md`：

```
P0 输入理解 → P1 关键帧设计 → P2 段落决策(抽象→人讲/具象→动效)
 → P3 节奏规划(按片长定呼吸) → P4 技术决策(画中画/抠像+混排布局)
 → P5 渲染前对齐(用户+agent 锁定方案,含2样本预演) → P6 渲染+QC
```

**铁律**：P0–P5 只做设计与对齐、不写渲染代码；P5 用户拍板后才进 P6。
关键决策：① 特别抽象的段落**让人讲、不出画面演绎**；② 纯口播连续 ≤30s、纯动效 ≤25s 必切换（疲劳阈值）；
③ 人+动效同框：**先判背景可抠性**——背景干净（纯色/绿幕/自带Alpha）走抠像，否则默认**画中画**（圆形或方形小窗，背景不可抠时）；关键帧未满屏时人窗放空白处；④ 全局规范（`design_principles.md`/`style_reference.md`）定调，
段落级微调写独立 scene 文件、不污染通用规则。样例节奏表（洁丽雅 142s）见 pipeline.md §9。

## 路线选型

| 路线 | 何时用 | 引擎 | 交付 |
|---|---|---|---|
| **H · 混排直渲（主路线）** | 满屏演绎 + 人全屏 + 混排：文字动画段、人在讲+关键字、人+动效混合 | Python PIL 逐帧 + ffmpeg 合成/编码（`scripts/render_anim.py` / `render_talk.py`） | 自带音轨 MP4 |
| **C · 导演式（备选）** | 需要 huashu-motion 标准化模板/卡片（名牌/数字卡/花字/章节）时 | huashu-motion `om` + talking-head 模板（web/JS 引擎） | 自带音轨 MP4 |
| **D · Three.js 原生（保留）** | 极致逐元素 / 3D 控制，模板与 PIL 都做不出时 | 自建 Three.js 工程 + 逐帧 + ffmpeg | 自带音轨 MP4 |
| **B · FFmpeg 直烧（兜底）** | 只要轻量字幕烧录、不要二次编辑 | `srt_to_ass.py` + ffmpeg | 烧录字幕 MP4 |
| **A · 剪映草稿（退役）** | 新版剪映专业版私有格式不兼容，已停用 | — | — |

> **默认走路线 H**（稳、无浏览器依赖、已验证洁丽雅口播样本）；C 是标准化卡片模板备选（需 mac Chrome sandbox 补丁）；
> D 是重武器，仅在需要逐元素/3D 时使用（参考实现 `work/test-01/film/`，v4→v18 迭代 14 版）；B 仅轻量字幕；A 退役。

## 通用前置（所有路线都要）

开工第一件事是看片 + 读字幕，写出分镜细案（强化段 / 金句 / 数据块 / 章节），再决定每张卡片卡在哪句话上。
否则容易回到「机械铺字幕」——这是用户明确否决过的方向。

动效与排版**不是自由发挥**：`references/design_principles.md` 是用户反复验收后拍板的硬规则
（生命周期、入画落视觉中心、组间距、脉冲缩放必须归位、硬切原则、图片规范等），开工前必读。

## 主路线 H：混排直渲（PIL + ffmpeg，默认）

稳定、无浏览器依赖、已验证（洁丽雅口播样本 `work/test-01/hybrid/`）。按 P2/P3 定的模式选脚本：

- **人在讲（A 模式）/ 混合 L1·L3**：`scripts/render_talk.py` —— 原片（可全屏、也可缩放进九宫格某格 + 背景补位）+ PIL 灵活关键字层（按口播时序、按人在九宫格的位置定落位：人中对下 / 人下对上 / 人左对右，20px expoOut 上浮 + 硬间隙）+ ffmpeg overlay。解决 ffmpeg drawtext 读 Noto OTC 缺字（筛/给 变方框）问题。**大特写占满全帧的素材必须走画中画（`--pip`），窗口比例须小于源比例否则纵向切脸**；另一栏用「编号+论点」列表（`--list`）撑满并与窗等高对齐。详见 `design_principles.md` §2.1.1/§2.1.2。
- **纯动效（B 模式）**：`scripts/render_anim.py` —— PIL 逐帧画满屏关键帧（标题/数据/树图），动效严格遵守 `design_principles.md` §3（expoOut/overshoot/expoIn/linear、tier 分级、20px 位移、段尾硬切），可 mux 原片音轨。
- **关键帧设计（P1）**：`scripts/gen_keyframes.py` —— PIL 直绘静态关键帧 PNG（4 章风格 + 大标题/数据卡/树图），先出图定方案再渲染。

```bash
# 人在讲段：关键字按口播时序，t0/t1 单位秒，相邻留 0.10s 硬间隙
python3 scripts/render_talk.py --source 口播.mp4 --ss 9.8 --t 9.7 --out u03.mp4 \
  --kws '[{"text":"有人替你筛过一遍","t0":0,"t1":4.4},{"text":"供给端天然稀缺","t0":4.5,"t1":6.9},{"text":"所以它可信","t0":7.0,"t1":9.7}]'

# 大特写素材：画中画 + 论点列表（先 --preview 出静态图给用户确认构图，再渲染）
python3 scripts/render_talk.py --source 口播.mp4 --ss 9.8 --t 9.7 --out u03.mp4 \
  --pip square --pip-cell right --pip-ratio 0.34 --bg "#f2f1ec" \
  --list '["有人替你\n筛过一遍","供给端\n天然稀缺","所以它\n可信"]' \
  --kws '[{"idx":0,"t0":0,"t1":4.4},{"idx":1,"t0":4.5,"t1":6.9},{"idx":2,"t0":7.0,"t1":9.7}]'
#   --preview --pt 2 --preview-out prev.png   ← 只出静态确认图，带九宫格 P/K 标注

# 纯动效段：scene JSON 描述元素入场/出场（元素类型 line/title/kwblock/number/block/divider）
python3 scripts/render_anim.py --scene scene_u04.json --out u04.mp4 --audio 口播.mp4 --ss 19.7 --t 7.366
```

- 字体：mac 系统 `NotoSansCJKsc-{Black,Bold,Medium}.otf`（Noto 900/700/500）；换平台需改脚本顶部字体路径。
- 逐段渲染后按 P5 锁定方案 concat 拼接（用 `verify_segments.py` 校验帧数/音轨）。
- 元素类型可按需扩展（如 KF6 树状图需 node/tree 类型，在 `render_anim.py` 的 `draw_elem` 增加分支即可）。

## 路线 C：导演式包装（备选）

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

## 路线 A：剪映草稿（已退役）

> 新版剪映专业版草稿主文件是私有格式，旧 `pyJianYingDraft` 生成的 `draft_content.json` 不兼容（显示 0KB/00:00）。**此路线已退役，不要再走**；需要剪映精修改用路线 C 或 H。`scripts/srt_to_shotlist.py`、`scripts/build_jianying.py` 保留但标记废弃。

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
- `scripts/render_talk.py` — **路线 H**：人在讲段渲染器（九宫格灵活构图 / 大特写走画中画 / 编号论点列表 / `--preview` 渲染前构图确认）
- `scripts/render_anim.py` — **路线 H**：纯动效段渲染器（PIL 逐帧满屏关键帧 + ffmpeg 编码 + mux 音轨）
- `scripts/gen_keyframes.py` — **路线 H / P1**：静态关键帧 PNG 生成（4 章风格 + 大标题/数据卡/树图）
- `scripts/srt_to_ass.py` — 路线 B：SRT→tech 风格 ASS
- `scripts/build_jianying.py` — 路线 A：剪映完整工程生成
- `scripts/srt_to_shotlist.py` — 路线 A：SRT→shot_list.json
- `references/design_principles.md` — **动效与排版硬规则（用户拍板，开工前必读）**
- `references/native_engine.md` — 路线 D：原生工程结构、渲染管线、7 个必踩坑位
- `references/review_loop.md` — 验收迭代：口语反馈翻译表、定位技巧、交付说明写法
- `references/delivery_cleanup.md` — 交付后清理：分类、白名单、`trash` 分批执行规则
- `references/style_reference.md` — **风格参考与样张方法论（huashu-design 3.0 沉淀：加选项不加禁令 / 参考板 / 外观账本）**
- `references/pipeline.md` — **全流程方案：P0–P6 决策流、段落决策、节奏规划、画中画/抠像、渲染前对齐清单、样例节奏表**
- `references/workflow_director.md` — 路线 C 端到端流程 + cue/坑位详解
- `references/planning_guide.md` — 理解文案·分镜规划方法
- `references/shot_list_spec.md` — 路线 A 的 shot_list 格式规范
- `assets/template-*.json` — 路线 A 风格模板（modern/tech/magazine）
