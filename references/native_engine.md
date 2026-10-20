# 路线 D · 原生 Three.js 工程（完全自定义视觉）

模板（路线 C）解决不了时用这条路线：需要**逐元素按口播调度**、自绘图表/白板/卡片系统、
或对每一帧的构图有完全控制。代价是开发量大、每次改动都要重渲。

> 参考实现：`work/test-01/film/`（142.5s 竖屏口播，v4→v18 共 14 版迭代）。
> 它的规范文档 `work/test-01/SPEC.md` 是风格真值来源。

## 1. 目录结构

```
film/
  index.html            # 入口：挂 window.film = { ready, renderAt(t), debugVis(t) }
  render.mjs            # 分段渲染：逐帧 renderAt(t) → screenshot → h264（挂原声）
  check-frames.mjs      # 静帧验证：只渲染几个时间点，秒级出图
  src/
    timeline.js         # 开场样段状态机（stage-1）+ LAYOUT 常量 + px() 坐标换算
    seq2.js             # 主段状态采样（纯函数：t → 各元素状态），含 TITLES 时间轴真值
    stage2.js           # 元素构造 + applyStage2(t)：把状态应用到 mesh
    text.js             # 排版引擎：makeTextTexture / textPlane（卡片、花字、荧光笔）
    main.js             # 场景根、人物卡、apply 主循环、debugVis
  assets/               # 图片素材（AI 生成的必须去水印、验方向）
  frames-sample/        # 逐帧输出（JPEG q92 默认）
  concat-list-vN.txt    # 分段拼接方案
```

**核心约定**：`seq2.js` 是纯函数（`t → 状态`），可任意顺序/重复寻址同一画面；
`stage2.js` 只负责把状态贴到 mesh 上。改视觉只动 stage2，改时间只动 seq2。

## 2. 端到端流程（每轮改动都按这个走）

```bash
cd work/test-01/film

# ① 改代码 → 语法检查（运行时错误查不出，但语法能挡一批）
node --check src/seq2.js && node --check src/stage2.js && node --check src/main.js

# ② 静帧验证：只渲染几个关键时间点，秒级出图，逐张目检
node check-frames.mjs 52.0 79.8 91.0 77.3

# ③ 分段渲染（每段 5-10 分钟，串起来后台跑）
node render.mjs 0.0 23.9 && node render.mjs 38.9 80.0 && node render.mjs 80.0 127.0

# ④ concat 之前必跑：校验每段帧数与音轨（见「坑位 1」）
python3 ~/.workbuddy/skills/agent-motion/scripts/verify_segments.py \
  --from concat-list-v10.txt --source ../source.mp4

# ⑤ 拼接
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i concat-list-v10.txt \
  -c copy film-final-vN-nosfx.mp4

# ⑥ 混音效（aevalsrc 合成 thump + adelay 定位；normalize=0 否则旁白被压半）
ffmpeg -y -i film-final-vN-nosfx.mp4 \
  -f lavfi -i "aevalsrc=0.9*sin(2*PI*58*t*(1-0.3*t))*exp(-9*t)+0.36*sin(2*PI*87*t)*exp(-12*t):s=44100:d=0.55:c=stereo" \
  -filter_complex "[1:a]adelay=22400|22400[fx];[0:a][fx]amix=inputs=2:duration=first:normalize=0[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k -movflags +faststart film-final-vN.mp4

# ⑦ 成片抽帧 QC（务必 -i 在前、输出侧 seek，见「坑位 4」）
ffmpeg -y -i film-final-vN.mp4 -ss 73.8 -frames:v 1 -q:v 3 qc.jpg
```

**渲染速度**：720×1280×DPR2、JPEG q92 约 0.19s/帧，全片 4275 帧 ≈ 15 分钟（分段后并行不了，只能串）。

## 3. 分段策略

- 按「改动影响的时间范围」决定重渲哪些段，不要每次全片重渲。
- 段边界放在**没有连续动画**的时刻（如标题交接的硬间隙），防止接缝跳帧。
- 外插片段（如引用其它素材的 15s 白板段）单独编码后写进 concat list。
- 分段方案单独存 `concat-list-vN.txt`，版本化，便于回溯。

## 4. 坑位清单（全部踩过，代价惨重）

### 坑位 1 · 帧目录残留 → 段内多帧 → 全片音画漂移（踩了 4 次）
`render.mjs` 想清空 `frames-sample/` 但受管 Node 的安全护栏删不掉，只能覆盖同名文件。
帧按**全局序号**命名，ffmpeg 编码时没有 `-frames:v` 限制、靠「遇到缺号才停」
→ 缺号处恰好是段边界时干净，但只要盘上有后续旧帧就会被一路吃进去。

表现：视频 88.1s 但音轨 41.1s；或只多 3 帧（后段整体漂移 0.1s）。

对策（**流程固化，不要指望一次改对**）：
1. render 后一律 `verify_segments.py` 核对 nb_frames；
2. 不对就显式帧数重编码：
   `ffmpeg -framerate 30 -start_number <f0> -i frames-sample/f-%06d.jpg -ss <t0> -t <dur> -i 源.mp4 -map 0:v -map 1:a -frames:v <N> ...`
3. 删残留帧用 Python（`int(n[2:8])`），**不要用 macOS awk**——`-F'[-.]'` 对 `./f-002403.jpg` 切出的是 `/f`，过滤会静默失效。

### 坑位 2 · 外插片段没有音轨
引用外部 15s 片段时它常常**没有音轨**，视频加了 15s、音频没加 → 从该处起解说整体提前 15s。
对策：concat 前 `verify_segments.py` 会标出；补音轨用
`ffmpeg -i 片段.mp4 -ss <t0> -t 15 -i 源.mp4 -map 0:v -map 1:a -shortest 补音.mp4`。

### 坑位 3 · 新 mesh 忘记 `visible = false`
`new THREE.Mesh(...)` 默认可见且位于原点。stage2 接管前（前 10.5s）它就会以默认状态
悬在屏幕正中央——表现为「画面中央一团灰色模糊影」，用户一眼就能看到，且很难反查。
**铁律**：构造后立刻 `m.visible = false`。影子（makeShadow）同样适用，且要注意
`visible` 可能有**多处赋值**（构造/主循环/收尾），改一处不够，必须 grep 全部赋值点。

### 坑位 4 · 抽帧 QC 落在旧关键帧上（假象）
`-ss <t> -i in.mp4`（输入侧 seek）会跳到最近的关键帧，可能抽到几秒前的画面，
导致「121s 抽出来和 74s 一样」的假象。**QC 必须用输出侧 seek**：`-i in.mp4 -ss <t>`。

### 坑位 5 · 影子/位置不同步
调度函数改了元素位置，但影子按旧调度放置 → 大灰影钉在画面一角；
或影子没按元素缩放同比缩放 → 小窗挂大灰团。修法：apply 之后用元素**终位**重放影子。

### 坑位 6 · `window.film.ready` 超时
不是渲染慢，是页面初始化抛错。`node --check` 查不出运行时错误，
要靠 `page.on('pageerror')`（render.mjs 已接）或浏览器控制台定位。

### 坑位 7 · 长渲染要后台，后台沙箱放行不生效
渲染 >10 分钟的命令用 `run_in_background`；需要 `dangerouslyDisableSandbox` 的操作
（如 ffmpeg lavfi）**只在前台生效**，后台任务里会失败。

## 5. 调试利器

- `window.film.debugVis(t)`：遍历场景图列出**实际可见**的 mesh（屏幕位置/尺寸/透明度/z），
  查「画面上这个不明物体是什么」第一件事就是跑它。
- `node check-frames.mjs <t1> <t2> ...`：秒级出静帧，改完立刻看，别等整段渲染。
- 音画对齐验证：`ffprobe` 比对各段 v/a 时长 + 30ms 包络互相关（错位 15s 时对齐度 0.80 vs 0.008）。
