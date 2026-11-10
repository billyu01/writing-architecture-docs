# 嵌入、构建与可重建性

> 目标：图在 Markdown 源、HTML 可视版、导出的 SVG/PNG 里保持一致，并且**任何时候都能从源重建**。

## 1. 两条嵌入通道

| 通道 | 做法 | 适用 | 注意 |
|---|---|---|---|
| Markdown | `![图号 图名](assets/x.svg)` + 图注 + 交互源链接 | 可 diff 的源文本 | 多数 Markdown 渲染器会过滤内联 `<svg>`；用图片链接，别指望内联 |
| HTML 可视版 | 内联 `<svg>`（不用 iframe） | 读者打开即见全貌 | 必须做 id/class 前缀 + 视口换算 + 构建断言 |

两通道共用同一批图源（`assets/*.svg`），不许各自维护一套。

## 2. 占位符构建

模板（`*.html.template`）里写：

```html
<figure>
  <h3 id="sec3">领域建模</h3>
  <!--INLINE:domain-model-->
  <figcaption>图 3-1 · 领域数据模型（<a href="assets/domain-model.html">交互源</a> · <a href="assets/domain-model.svg">SVG</a>）</figcaption>
</figure>
```

清单（JSON）：

```json
{
  "template": "docs/architecture/arch.html.template",
  "output": "docs/architecture/arch.html",
  "figures": [
    {"slug": "domain-model", "svg": "docs/architecture/assets/domain-model.svg"},
    {"slug": "deployment", "svg": "docs/architecture/assets/deployment.svg"}
  ]
}
```

构建：

```bash
python3 scripts/embed_svg.py --manifest docs/architecture/figures.json
```

脚本做四件事：读模板 → 把每张 SVG 的 **id 和 class** 按 `<slug>--` 加前缀（同步 `url(#…)`、`href="#…"`、`aria-labelledby`、`<style>` 选择器）→ 替换占位符 → 断言（无残留占位符、图数正确）。输出后建议再跑 `check_architecture_diagrams.py` 查整页 id/class 唯一性与几何。

## 3. 为什么 id 和 class 都要前缀

- `<svg>` 内联后，`<style>` 的作用域是**整个页面**，不是单个 SVG。
- 两张图都定义 `.ttl { font-size: 12px }`，后定义的会覆盖先定义的 → 第 N 张图文字样式跑到别的图上，严重时文字叠在一起。
- `id` 同理：`marker#arrow`、`title#title`、`desc#desc` 跨图重名，`url(#arrow)` 会指向错误 marker。
- 正确做法：`fig1--ttl`、`fig1--arrow`、`fig1--title`，所有引用同步改。
- 只给 id 加前缀、漏掉 class，是真实项目里最常见的「叠加」根因。

## 4. 视口换算（容器高度）

```
容器高度 = 容器宽度 × viewBox 高度 ÷ viewBox 宽度
```

- 不要写死 `height: 900px` 装 `viewBox="0 0 1600 920"` 的图；按宽度缩放后实际需要 `900×920/1600 ≈ 518px`，写死会上下留白或裁切。
- 推荐 CSS：`svg { width: 100%; height: auto; display: block; }`，容器不设固定高度。
- 若必须固定容器（打印/幻灯片），按上式算，并留 8–16px 余量。
- 页面级：不要给正文容器设 `min-width`；不要用 `overflow-x: auto` 包图。

## 5. 图索引（必须）

每张图在总览附录与正文各出现一次：

```markdown
| 图号 | 图名 | 内嵌位置 | 交互源 HTML | SVG | 状态 |
|---|---|---|---|---|---|
| 3-1 | 领域模型 | §3 | assets/domain-model.html | assets/domain-model.svg | 新 |
```

规则：图号与图注编号一致；路径可打开；复用图标 delta；改图后同步状态与修订史。

## 6. 构建断言（脚本必须做）

1. 模板中每个 `<!--INLINE:slug-->` 都有对应图源，且图源里有 `<svg>`。
2. 构建后没有残留 `<!--INLINE:...-->`。
3. 整页 `id` 唯一；跨图同名 class 声明一致或已前缀。
4. 图数 = 清单条数。
5. 连跑两次输出字节一致（确定性构建）。

`embed_svg.py` 做 1、2、4；`check_architecture_diagrams.py` 做 3；连跑两次用 `shasum` 比对即可：

```bash
python3 scripts/embed_svg.py --manifest figures.json
shasum docs/architecture/arch.html
python3 scripts/embed_svg.py --manifest figures.json
shasum docs/architecture/arch.html   # 必须相同
```

## 7. 生命周期

- **构建脚本与模板必须与产物同生命周期**：脚本被删 = 「可重建」承诺失效。
- 生成物可以入库，也可以不入库；入库时每次构建后 `git diff` 必须只包含预期变化。
- 文档里声明的重建命令必须能直接复制执行；定期跑一次（评审前/发布前）。
- 图源、导出物、构建脚本、模板四者一起提交，缺一样都可能断链。

## 8. 常见故障对照

| 症状 | 根因 | 修法 |
|---|---|---|
| 图显示不出来 | 只给链接且路径错；或 iframe 被安全策略拦 | 内联 SVG；校验相对路径 |
| 图被裁切 | 固定 iframe/容器高度 < viewBox 换算高度 | 用 `height:auto` 或按公式算 |
| 有横向滚动 | `min-width` / `overflow-x:auto` / 图固定宽 | 去掉；`width:100%;height:auto` |
| 文字叠到上一张图 | class 未加前缀，`<style>` 全局覆盖 | 构建时给 class 加前缀 |
| 箭头不显示 | marker id 被前缀后未同步 `url(#…)` | 构建脚本统一改写 |
| 图片变形 | 导出时丢了 `viewBox` 或写了固定宽高 | 保留 `viewBox`，宽高交给 CSS |
