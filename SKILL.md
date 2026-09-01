---
name: 个人信息台构建器
description: 从素材库一键生成「个人信息台」——可离线双击打开、能筛选浏览与状态跟踪的单文件 HTML 工作台。内置素材库模板与深度访谈脚本，别人装上就能从零复刻。触发场景：用户说「有素材库之后就建成这个信息台」「把这些数据做成一个台子/看板/跟踪表」「建个信息台」「双击打开就能看的本地主页」「数据存自己手上不上传」。覆盖深度访谈、字段建模、素材库归一化、单文件 HTML 生成、数据内嵌（解决 file:// 归零）、状态跟踪与导出回环、冒烟验证。
agent_created: true
---

# 个人信息台构建器（访谈 → 素材库 → 单文件 HTML 工作台）

把一个想法或一份素材库变成「双击就能用、离线能看、数据在自己手上」的个人信息台。

**技能自给自足**：模板、生成器、访谈脚本、说明文档全在包里。
别人装完，按本流程走一遍就能得到同样的成品，不需要参考任何外部页面。

## 何时用

- 用户有一批东西想管起来：岗位、客户、论文、书影音、项目、订阅、素材库……
- 想要筛选浏览 / 状态跟踪 / 到期提醒 / 纯展示
- 关键词：「素材库」「信息台」「工作台」「看板」「跟踪表」「双击打开」「本地主页」

## 五步流程

### 0. 深度访谈（没有素材库时必做；已有素材库可跳到 2）

按 `references/interview-guide.md` 分三轮问，每轮 3–4 题：

1. **定位**：手上有什么？现在哪里难受？做出来最常做的事是什么？
   → 决定 `status.enabled`（翻找/看全 = false；推进/盯 deadline = true）
2. **结构**：一行代表什么？**哪几个字段合起来唯一确定一行？**要哪些列？
   → 决定 `idFields` 与 `columns`
3. **行为**：左上角想看哪几个数字？风格？要不要手机看？
   → 决定 `kpis` 与 `theme`

**规则**：能推断的别问；拿不准的给选项不要开放式；用户说「你看着办」
就直接套 `interview-guide.md` 里的兜底默认，别追问。

访谈答案落进 `assets/素材库模板/00-访谈记录.md`，按文末对照表转成配置。

### 1. 建素材库

```bash
python scripts/build_desk.py --init ./我的素材库
```

生成四件套（都是 ASCII/中文混排的纯文本，Excel 可直接编辑）：

```
00-访谈记录.md      需求存档，不参与生成
01-字段定义.csv     列定义：key,label,type,width,filter,sort,search
02-数据.csv         数据行（表头 = 字段 key）
03-视图配置.json    标题/主题/主键/状态流转/KPI
填表说明.md         给用户看的填表手册
```

- `01` 存在时覆盖配置里的 `columns`；想纯 JSON 管一切就删掉 `01`
- `type` 可选：`text` `date`（3 天内到期标红 / 过期变灰）`link` `tags` `number`
- **事实类字段（截止日期/金额/链接）一律留空，禁止编造**

### 2. 填素材库

- 用户有数据 → 转成 `02-数据.csv`，表头对齐 `01` 的 `key`
- 用户没数据 → 留空表头，页面里可以点「更新数据」临时导入
- 数据源只走**用户自己有权使用**的渠道：本地文件、表格、数据库导出、
  手工录入，或对方明确开放的数据导出/接口。
  不做登录态绕过、不做签名复刻、不做频率规避。
  对方只提供网页时，优先让用户自己导出 CSV 再喂进来。

`03-视图配置.json` 三个关键项：

| 项 | 说明 |
|---|---|
| `idFields` | **最重要**。哪几列合起来唯一确定一行。只取一列极易重复，状态会串台 |
| `status` | `{enabled, options[], default}`。关掉就是纯浏览模式 |
| `kpis` | `count` / `countWhere` / `dueWithin` / `sum` / `distinct`<br>统计状态时 `key` 写 `__status` |

### 3. 一键生成

```bash
python scripts/build_desk.py --lib ./我的素材库 --out 我的信息台.html
python scripts/build_desk.py --lib ./我的素材库 --check     # 只校验不生成
```

生成器会检查并**警告主键重复**（重复行的状态会互相覆盖）。

产物自带：侧栏 KPI + 筛选 · 搜索 · 点表头排序 · 状态流转 · 备注 ·
localStorage 覆盖层 · 导出 JSON/CSV 回环 · 响应式（表格转卡片）·
**数据内嵌**（file:// 双击即见，不依赖 fetch、不弹文件框）。

### 4. 验证（不靠肉眼）

以**纯 `file://`** 打开并断言，逐项对上才算交付：

```python
pg.goto("file:///绝对路径/我的信息台.html", wait_until="domcontentloaded")
pg.wait_for_timeout(1200)
rows = pg.evaluate("() => document.querySelectorAll('#tbody tr').length")
assert rows == len(rows_data), f"渲染 {rows} 行 != 数据 {len(rows_data)} 条"
```

必测六项：① 行数 == 数据条数 ② KPI 数值正确 ③ 搜索能过滤
④ 筛选器生成 ⑤ 改状态 → 刷新后仍在 ⑥ 无 JS 运行时错误。

注意：`evaluate` 必须传**箭头函数**（`() => ...`），写 `var e=...; return e...`
会报 `Illegal return statement`。`file://` 下有 CORS 报错日志属预期无害。

### 5. 交付

`present_files` 打开 HTML，说清三件事：双击即可看 · 离线可用 · 数据在本机不上传。
数据会更新就附一条刷新命令（重跑第 3 步即可）。

---

## 内置了什么

```
SKILL.md                            本文件（五步流程）
README.md                           GitHub 仓库首页
build_my_desk.sh                   一键：build 我的素材库 → 我的信息台.html
我的素材库/                         已填好的可 build 素材库（别人直接 build 这个）
assets/素材库模板/                   空白素材库，--init 就是复制它
references/interview-guide.md       深度访谈执行手册（给 Agent）
references/html-checklist.md        页面骨架 / 视觉铁律 / 交付前自检
scripts/build_desk.py               主生成器：素材库 → 单文件 HTML
scripts/embed_data.py               只更新已有 HTML 的内嵌数据
examples/lib-qiuzhao-sample/        填好的示例素材库（输入，和「我的素材库」同款）
examples/example-qiuzhao-desk.html  它生成出来的页面（输出）
```

**零修改先跑通**：别人装上就 `bash build_my_desk.sh`，build 顶层 `我的素材库/` →
`我的信息台.html`，立刻得到同款秋招台子，不必先懂字段。要做自己的台子再走五步流程。

**三种角色分清楚**：
- `我的素材库/` + `build_my_desk.sh` = 拿来就 build，立刻得到同款
- `assets/素材库模板/` = 空白模板（`--init` 复制给自己填）
- `examples/` = 纯参考（输入样例 / 输出页面），不一定要动

想看成品长什么样，直接开 `examples/example-qiuzhao-desk.html`；想知道怎么填，
看 `examples/lib-qiuzhao-sample/` 那四份文件。

## 数据从哪来（仅授权渠道）

本 skill 只负责**呈现**数据，不负责**获取**数据。真实岗位 / 素材要用你有权使用的渠道取得：

- **站点自带导出 / 订阅**：国聘网、学校就业网、应届生网等多数提供 RSS、邮件订阅、表格导出 → 直接导出 CSV 喂进 `02-数据.csv`
- **手动整理**：把网页上的条目复制成表格，填进 `我的素材库/` 或 `--init` 出的空白模板
- **官方开放接口**：仅限站点明文提供、且使用条款允许使用的 API

> 边界：不做登录态绕过、不做签名复刻、不做频率规避。对方只给网页时，优先自己导出 CSV/Excel 再喂进来。
> 你私人的取数脚本（如国央企秋招采集器）留在本地项目，**不要**打进这个公开 skill。

拿到数据后：对齐 `01-字段定义.csv` 的 `key` → 填 `02-数据.csv` → 跑 build 即出台子。

## 常见坑

- **换数据后状态全丢** → 稳定 id 用了随机数，或 `idFields` 变了。改用业务主键拼接
- **状态串台** → 主键重复，生成器会警告，加一列让它唯一
- **双击打开 0 条** → 数据没内嵌（本生成器默认内嵌；手写页面才需要 `embed_data.py`）
- **列全是英文 / 顺序不对** → `01-字段定义.csv` 的 `key` 和 `02-数据.csv` 表头不一致
- **KPI 显示「—」** → `op` 拼写错，或 `key` 不是真实列名（状态要写 `__status`）
- **导出一次丢字段** → 导出把 `overlay` 一起带出（生成器已处理）
- **移动端输入框自动放大** → 字号 <16px，生成器里已全部 ≥16px
- **改了样式没生效** → 预览系统注入的 `data-page-node-id` 会让正则失配，直接用 Edit 改具体节点

## 风格配方

| theme.name | 观感 | 适用 |
|---|---|---|
| `mckinsey` | 深藏青侧栏 `#051C2C` + 蓝强调 `#034EA2`，圆角 6px | 求职、客户、项目、汇报 |
| `warm` | 米白 `#FBF8F3` + 淡紫侧栏 `#EDE8F7` + 珊瑚 `#FF7F6B`，圆角 22px | 书影音、灵感、生活 |
| `ink` | 黑白 + 一抹蓝，圆角 10px | 作品集、档案、极简 |

覆盖单个变量：`"theme": {"name":"mckinsey","vars":{"accent":"#C0392B"}}`
可覆盖：`sideBg` `sideFg` `sideSub` `accent` `bg` `fg` `line` `chip` `radius`
