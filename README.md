# Agent Motion · 口播导演包装

> *「把口播视频做成真正理解文案的导演式短视频。」*

Agent Motion 是一个 WorkBuddy 技能：把「口播视频 + 字幕/讲稿」做成**理解文案**的短视频包装——数据 count-up 卡、金句花字、章节卡、名牌、角标，全部**卡在说到的词上**，而不是机械铺字幕。

核心路线（路线 C）站在 [`huashu-motion`](../../huashu-motion/SKILL.md) 的肩膀上，用它的 `om` CLI 和 talking-head 模板做导演式合成；另外保留剪映草稿（路线 A）和 FFmpeg 直烧（路线 B）两条兜底路线。

---

## 四条路线

| 路线 | 何时用 | 引擎 | 交付 |
|---|---|---|---|
| **C · 导演式（默认）** | 要「理解文案」的包装、数据/金句可视化、口播成片 | huashu-motion `om` + talking-head | 自带音轨的 MP4（可透明叠层） |
| **D · 原生工程** | 模板不够：逐元素按口播调度、自绘卡片/图表系统、完全控制每帧构图 | 自建 Three.js + 逐帧截图 + ffmpeg | 自带音轨的 MP4 |
| **B · FFmpeg 直烧** | 不要二次编辑、只要成片；剪映打不开草稿时 | `srt_to_ass.py` + ffmpeg | 烧录字幕/卡片的 MP4 |
| **A · 剪映草稿** | 需要在剪映里精修/加特效 | `build_jianying.py` | 剪映工程文件夹 |

### 路线 D 快速开始（逐元素控制）

```bash
node check-frames.mjs 52.0 79.8 91.0      # 静帧验证：秒级出图，改完立刻目检
node render.mjs 38.9 80.0                 # 分段渲染（后台跑，~10min/段）
python3 scripts/verify_segments.py --from concat-list.txt --source ../source.mp4
```

参考实现 `work/test-01/film/`（142.5s 竖屏，v4→v18 迭代 14 版）。
其 `SPEC.md` 是风格真值，通用化版本在 `references/design_principles.md`。

---

## 快速开始（路线 C）

```bash
OM="$HOME/.workbuddy/skills/huashu-motion/bin/om"

# 1) 新建 talking-head 工程
"$OM" new my_film --template talking-head

# 2) 竖屏源转 9:16（横屏源跳过）
"$OM" fork my_film my_film_v --size 1080x1920

# 3) 配置：注入口播词时间轴 + 卡片（自动删 footage muted）
python3 scripts/configure.py --dir my_film_v --srt 字幕.srt --config config.json

# 4) 冒烟抽帧（先看落点，再整片渲染）
"$OM" look --at 45 my_film_v

# 5) 渲染（--frames jpg 必填，否则缓存几十 GB）
"$OM" render my_film_v --frames jpg --silent
```

### config.json 示例

```jsonc
{
  "name": "主讲", "role": "企业内容营销 · 筛选与把关", "corner": "企业内容观察",
  "stats": [
    {"value": 1.2, "suffix": "亿", "label": "全网播放", "cue": "播放量", "at": 89.9},
    {"value": 22.8, "suffix": "万", "label": "30天涨粉", "cue": "涨粉", "at": 93.7}
  ],
  "keywords": [
    {"text": "不是创意，是筛选和把关", "cue": "把关", "at": 41.9, "hold": 5.0},
    {"text": "主号保调性，子号做试验", "cue": "子号", "at": 131.3, "hold": 4.0}
  ],
  "chapter": "真正缺的能力", "chapterNo": "PART 03", "chapterAt": 38.0, "chapterHold": 2.4
}
```

`cue` 命中词表时以**真实说话时刻**为准覆盖 `at`；搜不到才落兜底 `at`。完整字段见 `references/workflow_director.md`。

---

## 理解文案优先

开工第一件事是看片 + 读字幕，写出分镜细案（钩子 / 核心论点 / 数据块 / 章节 / 警告），决定每张卡片卡在哪句话。方法见 `references/planning_guide.md`。这是「理解文案」和「机械铺字幕」的分水岭——后者已被明确否决过。

---

## 依赖与安装

- 必须安装 [`huashu-motion`](../../huashu-motion/SKILL.md) 技能（提供 `om` CLI 与 talking-head 模板）。
- 本机需要：Chrome（om 驱动截帧/渲染）、FFmpeg（导出）、Node 22+。
- WorkBuddy 里运行 `om render`/`om look` 时需在 Agent 模式放开沙箱（见下方坑位）。

---

## 坑位速查（路线 C）

1. **沙箱**：`om render`/`look` 必须放开沙箱（dangerouslyDisableSandbox）；后台任务不生效，前台跑自动转后台。
2. **音频**：talking-head 模板 footage 默认 `muted` → `configure.py` 已自动删；不删则成片无声。
3. **`--frames jpg`**：不传默认 png，抽帧缓存膨胀到几十 GB。
4. **横竖屏**：竖屏源先 `om fork --size 1080x1920`，别直接渲横屏（cover 会切脸）。
5. **笔误/双字幕**：原片硬字幕可保留；局部问题用限时 `delogo`（`enable='between(t,...)'`）只擦那一小段。

详细流程与 cue 机制见 `references/workflow_director.md`。

### 坑位速查（路线 D）

1. **帧目录残留 → 音画漂移（踩 4 次）**：render 后必跑 `verify_segments.py`，不对就显式 `-frames:v` 重编码。
2. **外插片段没音轨**：视频加了时长、音频没加，后面整体提前；补音轨后再 concat。
3. **新 mesh 忘关 `visible`**：默认可见且在原点，画面中央出现灰团；`visible` 有多处赋值要全 grep。
4. **抽帧 QC 假象**：必须输出侧 seek（`-i in.mp4 -ss <t>`），输入侧会落在旧关键帧。
5. **macOS awk 删帧失效**：`-F'[-.]'` 切错字段，批量删帧用 Python。

详见 `references/native_engine.md`。

---

## 目录结构

```
agent-motion/
├── SKILL.md                    # 技能入口（agent 读）
├── README.md                   # 本文件
├── scripts/
│   ├── configure.py            # 路线C核心：SRT→om-cues + 卡片变量注入（自动去 muted）
│   ├── verify_segments.py      # 路线D：concat 前校验各段帧数/音轨 + 给修复命令
│   ├── srt_to_ass.py           # 路线B：SRT→tech 风格 ASS
│   ├── build_jianying.py       # 路线A：剪映工程生成
│   └── srt_to_shotlist.py      # 路线A：SRT→shot_list.json
├── references/
│   ├── design_principles.md    # ★动效与排版硬规则（用户拍板，开工前必读）
│   ├── native_engine.md        # 路线D：工程结构、渲染管线、7 个必踩坑位
│   ├── review_loop.md          # 验收迭代：口语反馈翻译表 + 定位技巧
│   ├── workflow_director.md    # 路线C 端到端流程 + cue + 坑位
│   ├── planning_guide.md       # 理解文案·分镜规划方法
│   └── shot_list_spec.md       # 路线A 的 shot_list 格式规范
└── assets/
    └── template-{modern,tech,magazine}.json   # 路线A 风格模板
```

---

## 与 huashu-motion 的关系

导演式路线（C）完全建立在花叔的 [huashu-motion](../../huashu-motion/SKILL.md) 之上——`om` CLI、talking-head 模板、渲染引擎均来自它。Agent Motion 做的是**口播场景的固化**：把"看片理解 → 分镜 → 卡片配置 → 渲染出片"的工作流、踩过的坑、cue 机制沉淀成可复用技能，让口播包装不再从零摸索。感谢花叔的导演方法学。
