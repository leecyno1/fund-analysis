# Qoder 项目交接

更新时间：2026-09-30（交接后首个接手迭代已补：调度错过自动补偿，见 8.1 末尾与 HEAD `c7b16d2`）

当前状态：`main` 三端一致（本地 = GitHub `origin` = gitee，HEAD `2cdecd5`），无未提交改动。前端 3000 与后端 8005 由 launchd 从**本仓库**常驻托管并运行最新代码（09-22 重启后未再改前端；后端 09-25 重启加载快照批量同步）。`docs/plans/2026-08-19-final-launch-iteration-design.md` 的 M1–M6 全部完成。**2026-09-20 → 09-26 的完整迭代弧线**（详见 `CHANGELOG.md` 2.2.2）：UAT 遗留五项缺口闭环 → 前端冒烟 121/121 全绿 → 详情页"研究画像"边界确认（删除 357KB 死组件）→ 报告链路去 Docker 化（读写归一 PG）→ MongoDB 依赖彻底移除（运行栈 = PG + 本地缓存，零外部服务）→ 经理任期快照批量补齐（55→350 条）→ 评价覆盖回填提额至每日 1000 只 → IMA skill 升级 1.1.10（调度 11 任务全绿）。**代码功能零已知缺口，后端 152/152、前端 121/121。**

当前唯一已知环境隐患：3000 端口在**本项目前端停服窗口**（尤其重新构建时）可能被 newma-desk dev-stack 的 fund-analysis dev 副本抢占（见 2.2 的处置流程；根治需在 newma-desk 侧移除该前端或改端口，属用户决策）。

历史沿革：2026-08-18 完成四代合并去重大重构（v2.0.0）：删除旧 `frontend/`、Wind 数据链路、一代 screening/sync 页面与对应 API；旧路由保留薄重定向；历史文档归档至 `docs/history/`。2026-08-19 起进入上线迭代（v2.1.0），2026-09-10 收敛至 v2.2.0，2026-09-11 发布 v2.2.1（修复 launchd 调度环境缺陷 + 重建项目上下文记忆），2026-09-20/21 发布 v2.2.2（UAT 遗留缺口闭环 + 冒烟基线全绿恢复 + 详情页研究画像边界确认）。逐条变更见 `CHANGELOG.md`，架构见 `ARCHITECTURE.md`。

> 2026-09-08 Qoder IDE 的 `cli_ws_migration` 迁移只搬工作区产物、未导入会话正文，导致本项目历史 quest 从 IDE 列表消失。正文已从 CLI transcript 完整导出归档至 `../.quest-recovery/restored/`（索引见该目录 `INDEX.md`），恢复过程与根因见本文件第 13 节。

## 1. 项目定位

本项目是面向普通用户的独立基金研究与选择工具，核心流程是：

`基金数据库 -> 基金浏览与比较 -> 基金分类与评价 -> 经理纪要研究 -> 业绩归因 -> AI 现场分析 -> 标签候选`

不开发交易执行、购买金额、销售规则、个人适当性和投资决策。报告系统不是核心。

Newma Desk 只是可选宿主。独立应用和 Desk Adapter 共用业务页面，禁止复制两套业务实现。人工验收前不要加入 `desk-mods`。

定位演进：`docs/adr/0004-research-portfolio-and-trade-list-boundary.md`（2026-08-19）已把项目从「选基工具」演进为**专业基金研究工作台**——设计原则是信息密度、操作效率与研究对象保真度优先，而非营销叙事；因此页面宣传性大标题已于 `5077473` 全部移除，但实体内容标题（基金名、经理名、公司名、报告标题）与紧凑形式的边界语义保留。已知文档债：`CONTEXT.md` 标题仍写「简单基金选择工具」，与 ADR-0004 不一致，修改属产品定位决策，需用户确认后再动。

## 2. 当前运行入口

- 正式前端：Next.js，`http://127.0.0.1:3000`
- 正式后端：FastAPI，`http://127.0.0.1:8005`
- PostgreSQL：仓库内 `.data/postgres/`（服务端 16.13）
- 后端健康检查：`GET http://127.0.0.1:8005/api/health`
- LLM 配置健康检查：`GET http://127.0.0.1:8005/api/reports/ai-health`
- Desk 描述：`desk/suite.json`
- Desk 发现：`GET /.well-known/newma-desk-suite.json`
- 历史阶段文档已归档至 `docs/history/`，不作为现状依据
- `3001` 属于 Orchestra，本项目不得占用

### 2.1 常驻形态（正式运行方式）

自 2026-08-19（M1）起，本机以 launchd 常驻运行，plist 在 `~/Library/LaunchAgents/`，`WorkingDirectory` 均指向本仓库：

| Label | 作用 | 启动命令 |
| --- | --- | --- |
| `com.fund-analysis.backend` | FastAPI 8005 | `/bin/bash backend/scripts/start_backend.sh` |
| `com.fund-analysis.frontend` | Next.js 3000 | `next start --hostname 127.0.0.1 --port 3000`（**生产模式**） |
| `com.fund-analysis.scheduled_update.daily` | 工作日 18:15 日常同步 | `bash scripts/scheduled_update.sh --bucket daily` |
| `com.fund-analysis.scheduled_update.weekly` | 周日 20:00 周全量同步 | `bash scripts/scheduled_update.sh --bucket weekly` |

两个服务均为 `RunAtLoad` + `KeepAlive`（异常退出自愈）。

改动生效方式：

- **后端**：改 Python 源码后需重启进程（`launchctl kickstart -k gui/$(id -u)/com.fund-analysis.backend`）。
- **前端**：`next start` 跑的是构建产物，**不热重载**。改前端源码必须 `npm run build` 后再 `launchctl kickstart -k gui/$(id -u)/com.fund-analysis.frontend`，否则改动不生效。

### 2.2 端口归属排查（已踩过的坑）

8005 曾被 **newma-desk 的 bundled 副本**抢占：`scripts/dev-stack.mjs` 把 fund-analysis 当作 optional external mod runtime，用 `newma-desk/bundled-runtimes/fund-analysis` 的代码副本监听 8005，导致本仓库的 launchd 服务长期启动失败（`launchctl list` 显示 `PID=-`、last exit 1），出现「源仓库改了不生效」。2026-09-09 已理顺：kill 占用端口的 uvicorn 后，launchd KeepAlive 立即用**源仓库**代码接管（optional 服务被 kill 不会触发 dev-stack 的 `onCoreFailure` 整栈关闭）。

**3000 于 2026-09-22 发生同款抢占**：前端停服构建（bootout → `next build`）的窗口期，newma-desk 的 dev-stack（自有 LaunchAgent `com.newma.desk.dev`）起了一个 fund-analysis **dev 模式**捆绑副本抢占 3000，本项目前端 bootstrap 后因 EADDRINUSE 崩溃循环。已按同款解法夺回：只 kill 占用端口的 next dev 进程树（dev-stack 本体还管着 8011/8788/3001 等其他项目端口，不能动它），随即 `launchctl kickstart` 本项目前端。⚠️ **隐患仍在**：本项目前端任何停服窗口（尤其重新构建时）都可能再被抢占——dev-stack 的 fund-analysis 前端要么在 newma-desk 侧移除，要么改端口，属另一个项目的改动，需用户决策。

另外注意前端重启的正确顺序：`launchctl bootout` → `npm run build` → `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fund-analysis.frontend.plist`。**bootstrap 必须从 `~/Library/LaunchAgents/` 路径加载**——从仓库内相对/绝对路径 bootstrap 会报 `error 5: Input/output error`（09-22 实测）。

怀疑改动不生效时，先确认端口实际由谁管理、跑哪份代码：

```bash
lsof -nP -iTCP:8005 -sTCP:LISTEN -t          # 取 PID（3000 同理）
lsof -a -p <PID> -d cwd                      # 看工作目录是源仓库还是 bundled 副本
ps -o pid,ppid,command -p <PID>              # PPID=1 为 launchd；追到 node dev-stack.mjs 则为 newma-desk 托管
launchctl list | grep fund-analysis          # PID 为 - 且 exit 非 0 说明 launchd 服务没起来
```

### 2.3 launchd 极简 PATH（2026-09-11 已修复）

launchd 启动进程时 PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin`，**不含 `/opt/homebrew/bin`**，而 `npm`/`node`/`psql`/`pg_dump` 全在该目录。这曾导致 `scheduled_update.sh` 里所有 `npm run ...` 任务报 `bash: npm: command not found`（exit 127），`backup_postgres.sh` 因 `command -v pg_dump` 失败叠加 `set -euo pipefail` 而**静默 exit 1（无任何输出）**。手工在终端执行同一脚本一切正常，因此该缺陷在 M1/M6 验收时被完全掩盖，连续失败 20 个调度日才被发现。

已修复（三处）：

- `scripts/scheduled_update.sh` 与 `scripts/backup_postgres.sh` 顶部补全 Homebrew PATH（`/opt/homebrew/bin`、`/usr/local/bin`）；
- `backup_postgres.sh` 的 `pg_dump`/`pg_restore` 回退赋值改为 `command -v ... || true` + 缺失时打印含 PATH 的明确错误，杜绝再次静默退出；
- `package.json` 中 13 个脚本由裸 `python` 改为 `.venv/bin/python`——macOS 与 launchd 环境都没有 `python` 命令，这是 PATH 修好后暴露出的第二层 127。

后续新增任何 launchd 定时任务都要注意这一点；验收定时任务必须用 `launchctl kickstart` 在**调度环境**下跑一次，终端手工成功不算通过。

PATH 修复后曾暴露的第二个问题（`research:sync-ima` 返回 `skill auth failed`）已于 2026-09-12 关闭，且**不是本地凭证失效**——是 IMA 服务端授权状态，用户在 IMA 侧重新授权后即恢复。排查方法与判读规则见 8.1。（注意：09-15 起 sync-ima 又因 IMA 要求 skill 升级 1.1.10 而每日失败，属新的独立问题，同样见 8.1 末尾。）

### 2.4 兜底：手工启动（launchd 不可用时）

```bash
./scripts/start-local-postgres.sh
./backend/scripts/start_backend.sh
npm install
npm run dev
```

## 3. 当前核心功能

1. 基金数据库：真实基金档案、净值、滚动指标、经理、公开持仓、资产配置、持有人结构、债券重仓。
2. 基金浏览器：搜索、分类筛选、净值曲线、基金详情、同类比较。
3. 基金评价：先分类，再按分类专属方法评价；展示同类分位、排名、风险和证据缺口。
4. 纪要库：扫描本地 `ima知识库/`，按基金经理归类，保留原文、来源、确认状态和标签证据。
5. 经理研究：经理浏览、详情、任职产品、任期指标、纪要观点时间线和经理比较。
6. 业绩归因：Barra 类公开持仓风格描述、Brinson 配置/选择效应、净值行为补充解释。
7. AI 分析：用户选中单只基金后现场运行，读取评价、归因和纪要，保存完整历史与版本。LLM 为 MiniMax-M3（openai-compatible，思考型模型，代码已剥离 `<think>` 段），配置见 `.env.local` 的 `LLM_*` 四件套。
8. 标签候选：按标准类别和风格返回不超过 10 只候选基金。
9. Newma Desk Adapter：独立 Suite 描述、工作区映射、上下文和数据能力健康检查。
10. 组合研究（M4/M5，`/portfolio`）：研究型组合构建（准入就绪校验、等权/自定义权重且单只 ≤40%、重仓股重叠/风格暴露加权/净值相关性三合一穿透）、解释性回测（以当前权重回看历史 + 分类映射基准对比 + 样本不足拒答）、组合监控（同类组目标偏离阈值 5% + 成分风格漂移 + 再平衡提示）、目标配置 UI。
11. 交易清单（M5）：目标权重 vs 当前持仓差异 → 申赎建议，属**研究输出**，不落库不执行（边界见 ADR-0004）。
12. 报告库（`/reports`）：经理研究报告与基金评价分析报告，Markdown 渲染、经理名可点击链接、导出 Word（msword Blob + UTF-8 BOM）与 PDF（`window.print()` + `@media print`）；`(target_type, target_id, report_type)` 唯一约束 + upsert 覆盖式写入防重。

## 4. 数据与证据边界

- **MongoDB 已从报告链路移除（2026-09-23）**：调研报告 CRUD 写路径、AI 报告历史/详情读路径、AI 报告生成管线中的纪要与画像读取，全部归一 PostgreSQL（与既有读路径同库）。上传报告现在立即可在列表检索（此前写 Mongo 读 PG 互不相通）；`/api/reports/history` 此前恒空（读从未运行的 Mongo）也已修复。MongoDB 依赖已于 2026-09-24 彻底移除（`172bbd2`）：`service_registry` 的 `get_db` 连接器与 Mongo 版 repo 类均已删除，后端运行栈为 PostgreSQL + 本地缓存，零外部服务。
- 基金必须先分类，再进入同类评价。
- 不跨类别比较，不用短期收益冠军直接推荐。
- Barra / Brinson 只用于解释，不进入基金综合评分。
- 未接入正式因子收益、协方差和特异风险时，必须写“公开持仓风格描述子”，不能写成正式 Barra 模型。
- Brinson 必须展示公开持仓覆盖率和残差；证据不足时不输出完整归因结论。
- 经理层纪要只说明经理方法，不能外推为某只基金的实际持仓。
- 风格标签必须区分人工确认、量化持仓、推导标签和 LLM 建议。
- LLM 不得编造净值、持仓、经理经历、标签或归因结果。
- AI 分析历史必须保存并回放当时使用的评价、风格、纪要和归因证据。
- `factor_exposures` 是**测试死表**：2026-09-10（`198fdd1`）已清空生产库测试残留并移除 `routes/funds.py` 的读取依赖，`barra_exposure` 字段仅保留空对象兼容接口契约。真实风格暴露源是 `holding_style_snapshots`——不要从 `factor_exposures` 读数，也不要往它写业务数据。
- `research_reports.id` 与各表 `report_id` 必须保持 `UUID`：`backend/repositories/local_research_folder_repo.py` 硬编码 `CAST(:report_id AS UUID)`，改 TEXT 会触发 `operator does not exist: text = uuid`（2026-09-08 `7d88375` 已回退该改动）。同理注意 `CREATE TABLE IF NOT EXISTS` **不会**迁移已存在表的列类型，任何列类型变更都必须写显式 `ALTER` 迁移，否则代码定义与生产库静默不一致。
- 经理证据链的天花板是 `manager_profiles` 覆盖率（2026-09-09 实测 1.8%，127/7218），受限于本地调研纪要数量。经理证据为空属数据覆盖问题而非缺陷，不得用模板化内容填补。

## 5. 当前真实数据状态

最近一次人工验收时，本地 `ima知识库` 状态：

- 纪要 225 份
- 已归类经理 133
- 经理研究卡片 132 位
- 权益观点 211 份
- 固收观点 68 份
- 待确认 99 项：经理 26、基金 38、分类 5、风格标签 30

验收样本 `000031.OF 华夏复兴混合-A`：

- 经理：黄皓
- 基金专属纪要：0
- 经理层纪要：1
- 量化风格：偏大盘、价值成长均衡、低波
- 页面必须提示经理层纪要不能直接推导为本基金持仓

这些数量会随同步变化，不要在代码中硬编码。

### 5.1 2026-09-11 只读核实现状

来源：`psql -d fund_analysis` 只读计数 + `GET /api/health`。

| 对象 | 数量 | 说明 |
| --- | --- | --- |
| `funds` | 31,914 | `/api/health` 报 `connected=true`、`data_source=tushare`、`mock_mode=false` |
| `fund_nav` | 774,522 | 净值主表 |
| `holding_style_snapshots` | 613 | **真实**风格暴露源 |
| `factor_exposures` | 0 | 死表，2026-09-10 清空测试残留后为空（原 12 行已备份至 `../.quest-recovery/`） |
| `research_reports` / `research_report_managers` | 225 / 176 | 2026-09-08 核实以来未变 |
| `ai_analysis_reports` | 13 | 2026-09-09 去重（29→13）+ 唯一约束 + upsert 后保持稳定，未再重复 |
| `manager_profiles` | 130 | 2026-09-11 补跑 `research:sync-manager-identities` 后由 127 增至 130；覆盖率仍仅约 1.8%（130/7218），是经理证据链天花板 |

**备份现状**：曾自 2026-08-20 15:36 起连续 22 天全部失败（launchd 极简 PATH 缺陷，见 8.1），**2026-09-11 已修复并恢复**。最新可用还原点为 `fund_analysis_20260912_081435.dump`（约 37MB，由 `launchctl kickstart` 在调度环境产出，内容自检通过）。后续每个调度日 18:15 自动积累，保留最近 14 份；做破坏性数据操作前仍可先手工执行 `bash scripts/backup_postgres.sh` 取一个即时还原点。

> 2026-09-22 增量：`funds` 32,268；`fund_dividends` 4,764 条分红事件已有消费端点（`GET /api/funds/{code}/dividends`，2.2.2）；`manager_fund_tenures` 84,962 条中 `performance_snapshot=available` 55 条（张仲维 09-22 补 26 条；此字段只由 `sync_fund_manager_tenure.py` 写入，见第 11 节补充）。其余以 5.1 为基线自然增长。

> 2026-09-26 增量（交接时点，两条自动积累曲线在爬升）：① **评价覆盖**——1y 指标齐备基金 1,932 → **2,425+**（09-25 配额提至每日 1000 只后单日 +493，约一周覆盖全部 9,686 活跃同类实体；查进度：`SELECT COUNT(DISTINCT target_id) FROM metric_snapshots WHERE metric_window='1y';`）；② **经理任期快照**——available 55 → **350+**（09-25 批量入口上线首批 3 位经理 + 每日调度 3 位/日持续补齐，`sync_fund_manager_tenure.py --snapshot-backlog N` 可手工加跑）；③ `research_reports` 238 份、`ai_analysis_reports` 23 份（读写已归一 PG）。**销售规则 `fund_sales_rules` 表**：09-25 已为解锁队列 8 只基金导入 Tushare fund_basic 基础申购状态（全 open）；Tushare 实测无费率/风险等级接口，剩余字段只能人工核验（批量导入 API：`POST /api/evidence-coverage/materials`）。

## 6. 当前最重要的代码入口

- 产品范围：`CONTEXT.md`
- 独立产品与 Desk 边界：`docs/adr/0003-independent-product-and-desk-adapter.md`
- 基金研究快照：`backend/services/fund_research_snapshot_service.py`
- 分类：`backend/services/fund_classification_service.py`
- 评价：`backend/services/fund_evaluation_service.py`
- 同类比较：`backend/services/peer_comparison_service.py`
- 归因：`backend/services/performance_attribution_service.py`
- AI 分析后端：`backend/routes/reports.py`
- AI 分析前端：`app/(dashboard)/analysis/FundAnalysisWorkspace.tsx`
- AI 历史证据映射：`lib/analysis-evidence-metadata.ts`
- 调研库前端：`app/(dashboard)/research/ResearchLibraryClient.tsx`
- 经理研究卡片：`app/(dashboard)/research/ManagerResearchGrid.tsx`
- 基金评价前端：`app/(dashboard)/evaluation/EvaluationWorkspace.tsx`
- Desk Adapter：`app/(desk)/`、`lib/newma-desk/`、`desk/`

## 7. 已有更新命令

所有凭证只放 `.env.local`、`backend/.env` 或用户本机配置目录，禁止提交。

```bash
# 全市场基金基础库、份额、分类、同类组和基准映射
npm run funds:update-universe

# 浏览器核心净值和滚动指标补齐
npm run funds:backfill-browser-core

# 同类评价覆盖（每日调度配额已提至 1000，约 13 分钟/日，约一周覆盖全部活跃实体）
npm run funds:backfill-peer-evaluation -- --limit 1000

# 基金经理目录和任职关系
npm run funds:sync-manager-universe
npm run funds:sync-manager-tenure

# 经理任期绩效快照批量补齐（按缺失条目降序选经理；每日调度 3 位/日，可手工加跑）
.venv/bin/python backend/scripts/sync_fund_manager_tenure.py --snapshot-backlog 5

# 公开股票持仓及持仓风格
npm run funds:sync-holdings -- --limit 100
npm run data:sync-holding-style

# 产品档案、费率、资产配置和持有人结构
npm run funds:sync-product-profiles -- --limit 100

# 公开重仓债券
npm run funds:sync-bond-holdings -- --limit 100

# 本地纪要上传 IMA 云端
npm run research:sync-ima

# 纪要经理身份、标签和观点主题
npm run research:sync-manager-identities
npm run research:preview-memo-labels
npm run research:apply-memo-labels
npm run research:preview-viewpoint-topics
npm run research:apply-viewpoint-topics
```

同步前必须确认 PostgreSQL 正常、`TUSHARE_TOKEN` 可用。IMA 凭证使用 `IMA_OPENAPI_CLIENTID`、`IMA_OPENAPI_APIKEY` 或 `~/.config/ima/`，不要把密钥写进仓库或日志。

## 8. 定时更新节奏（已实现，非待办）

编排层已于 2026-08-19（M1）落地，**不要再重复实现**：`scripts/scheduled_update.sh` 按 bucket（daily/weekly/quarterly/monthly）编排既有 npm/bash/python 命令，配 mkdir 原子锁（macOS 无 flock）、PID 陈旧检测、`logs/scheduled_update/runbook.jsonl` 逐任务运行记录、`logs/scheduled_update/alerts.log` 失败告警，并由 `com.fund-analysis.scheduled_update.{daily,weekly}` 两个 launchd 定时器驱动。调度逻辑不在 Next.js 请求里。

下表是编排层已实现的节奏口径：

| 周期 | 任务 | 说明 |
| --- | --- | --- |
| 每个交易日收盘后 | 浏览器核心净值、滚动指标、同类评价增量（**每日 1000 只**，约 13 分钟） | 09-25 提额，约一周覆盖全部活跃实体 |
| 每日 | IMA 纪要增量上传、经理身份同步、**经理任期快照批量补齐（3 位/日）**、待确认数量统计 | LLM 建议不能自动转人工确认 |
| 每周 | 基金基础库、分类、经理目录、产品档案缺口 | 更新前后记录覆盖率 |
| 每月 | 数据质量审计、推荐覆盖率、失效基金清理 | 清理只改状态，不物理删除历史 |
| 季报披露后 | 股票持仓、债券重仓、资产配置、持有人结构、持仓风格、Brinson 历史 | 必须按报告期和证据日期保存 |

调度器最低要求：

- 使用非重入锁，避免同一同步并发写库。
- 每个任务记录开始时间、结束时间、退出码、处理数量和失败摘要。
- 单任务失败不覆盖上一版有效快照。
- 支持 `--dry-run`、单任务执行和断点续跑。
- 日志不得包含 Token、IMA API Key、数据库密码或完整请求头。
- 失败时只告警，不自动执行破坏性回滚。

### 8.1 调度真实状态（2026-09-11 缺陷已修复并验证）

**历史缺陷（2026-08-19 上线 ~ 2026-09-11 修复，保留作为教训）**：`runbook.jsonl` 逐日统计显示，这段时间内**每个调度日固定 5 个任务失败、4 个成功**，失败集合从未变化：

| 任务 | bucket | 状态 | 现象 |
| --- | --- | --- | --- |
| `research:signals-scan` / `anomalies:scan` / `watches:scan` / `evaluation:snapshots` | daily | ✅ 每日成功 | 均走 `.venv/bin/python` **绝对路径**，不依赖 PATH |
| `funds:backfill-browser-core` / `funds:backfill-peer-evaluation` / `research:sync-ima` / `research:sync-manager-identities` | daily | ❌ 18 次全败 | `bash: npm: command not found`，exit=127 |
| `ops:backup-postgres` | daily | ❌ 20 次全败 | **静默 exit=1、0 秒、无任何输出** |
| `funds:update-universe` / `sync-manager-universe` / `sync-manager-tenure` / `sync-product-profiles` | weekly | ❌ 全败 | 同 exit=127 |

**根因（单一）**：launchd 启动进程时 PATH 仅 `/usr/bin:/bin:/usr/sbin:/sbin`，不含 `/opt/homebrew/bin`，而 `npm`/`node`/`psql`/`pg_dump` 全在该目录。

- npm 任务：裸 `npm run ...` 直接 127。
- 备份任务：`backup_postgres.sh` 里 `psql` 取不到 `server_version` → 版本匹配的 `pg_dump` 候选落空 → `PG_DUMP="$(command -v pg_dump)"` 在 `set -euo pipefail` 下命令替换失败即退出，**因此连一行错误都没打印**（已用 `env -i PATH=/usr/bin:/bin bash scripts/backup_postgres.sh` 复现 exit=1）。

**为何 M1/M6 验收没发现**：`runbook.jsonl` 给出决定性对照——**20 次 18:15 调度时点全部失败（20/20）**，只有 2026-08-19 06:20 与 2026-08-20 15:36 两个**非调度时点**成功，那两次是手工在终端执行（shell 自带 homebrew PATH）。修复前 `backups/postgres/` 里只有 3 个 dump，正对应这些手工产物。也就是说缺陷只在 launchd 环境下暴露，而验收全程走手工路径，被完全掩盖。

**当时造成的后果**：

1. 浏览器核心净值、同类评价增量、IMA 纪要上传、经理身份同步、周度基础库/经理目录/产品档案**自 8 月起从未自动更新**——覆盖率实际停在 2026-08 水平，第 11 节曾据此刻画 M3 为「被阻塞」。
2. **连续 22 天无成功备份**（最后一次 2026-08-20 15:36），期间没有近期还原点。

**已实施的修复（2026-09-11）**：

1. `scripts/scheduled_update.sh` 与 `scripts/backup_postgres.sh` 顶部补全 Homebrew PATH（`/opt/homebrew/bin`、`/usr/local/bin`）后再 `export`，不在 plist 里写死环境，便于终端与调度共用同一脚本。
2. `backup_postgres.sh` 的 `pg_dump`/`pg_restore` 回退赋值改为 `command -v ... || true`，缺失时打印含 `PATH` 的明确错误并 `exit 1`，杜绝 `set -euo pipefail` 下的静默退出。
3. `package.json` 中 13 个脚本由裸 `python` 改为 `.venv/bin/python`——macOS 与 launchd 都没有 `python` 命令，这是 PATH 修好后暴露出的第二层 127。

**验证方式与结果**：用 `launchctl kickstart -k gui/$(id -u)/com.fund-analysis.scheduled_update.daily` 在**真实调度环境**下跑（终端手工成功不算通过）。9 个 daily 任务 **8 个 ok**：

- `ops:backup-postgres` ok（4s），产出 `fund_analysis_20260911_234226.dump`（约 35MB），`pg_restore -l` 关键表内容自检通过；
- `funds:backfill-browser-core` ok（13s）、`funds:backfill-peer-evaluation` ok（89s）——两个曾长期 exit=127 的 npm 任务恢复；
- `research:sync-manager-identities` 首轮仍 127，第 3 项修复后单独补跑 ok（96s），`manager_profiles` 由 127 增至 130，确认有真实效果而非空跑。

weekly 路径另经调度脚本补跑 `funds:sync-product-profiles -- --limit 100` 验证：ok（125s，`requested=100` / `failed=0`，资产配置与持有人结构真实写入）。其余三个 weekly 任务（`funds:update-universe` 为全市场同步，`sync-manager-universe` / `sync-manager-tenure` 同为重量级）耗时长且消耗 Tushare 配额，未即时手工触发，留给每周日 20:00 定时器自然执行。

**最后一个遗留项已于 2026-09-12 关闭**：`research:sync-ima` 曾返回 `skill auth failed`（服务端非零 `msg`，由 `scripts/sync_ima_research_library.sh` 的 `api_call` 打印——注意 `ima_api.cjs` 只对 fetch 异常抛出，业务错误码是正常返回，判读要看 `.code`）。

⚠️ **当时的结论「凭证已过期需重新获取」是错的**，复核后修正：用户 09-12 提供的 clientId/apiKey 与 `~/.config/ima/` 里 2026-08-14 起就在用的那组**逐字节相同**（md5 一致），而同一组凭证 09-11 23:42 被拒、09-12 08:03 通过。所以 `skill auth failed` 反映的是 **IMA 服务端的授权状态**（用户在 IMA 侧重新授权后即恢复），不是本地密钥失效。

用户在 IMA 侧完成授权后，经调度脚本执行 `research:sync-ima` ok（30s，`runbook.jsonl` 已记录）：226 份本地纪要全部命中云端同名文件，新增 0、失败 0。

**最终一次性验收（2026-09-12 08:14）**：用 `launchctl kickstart` 在调度环境完整跑一轮 daily，**9/9 全部 ok**（`backfill-browser-core` 4s、`backfill-peer-evaluation` 103s、`sync-ima` 33s、`sync-manager-identities` 108s、三个 scan 各 0s、`evaluation:snapshots` 17s、`backup-postgres` 4s），当日 `alerts.log` 零条，`launchctl list` 中 daily 的汇总退出码回到 **0**，产出新 dump `fund_analysis_20260912_081435.dump`（约 37MB）。此前 09-11 的验证是分三次拼出的（kickstart 8/9 + 两个单独补跑），这一轮才是单次全绿的确定性证据。

**排查方法教训**：遇到 IMA `skill auth failed` 不要先假定密钥失效——① 用最轻的 `openapi/wiki/v1/search_knowledge_base` 单独复测（1 次调用即可判定授权状态）；② 把本地凭证与用户新提供值做 md5 比对，若相同则问题在服务端授权而非本地配置；③ 凭证只写 `~/.config/ima/`（600 权限，覆盖前先按 `.bak.YYYYMMDD` 备份），不进仓库、不进日志。

**IMA skill 已升级至 1.1.10（2026-09-26，用户授权后执行）**：此前 09-15 起 `research:sync-ima` 每日失败（`code:-200 要求升级 skill`）。升级流程：从 `https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip` 下载 → 解压 → 替换 `~/.codex/skills/ima-skill`（旧版备份 `ima-skill.bak.20260926`）。升级后实测同步 ok（新增 0 / 已存在 226 / 失败 0），**11 个 daily 任务恢复全绿**。注意：skill 版本升级提示来自外部日志，未经用户授权不代为执行；再次出现版本要求时按此流程处理并先获用户确认。

另：09-20（周日）weekly 定时器**首次全自动运行 5 任务全 ok**（`funds:update-universe` / `sync-manager-universe` / `sync-manager-tenure` / `sync-dividends` / `sync-product-profiles`），第 11 节的"核对 weekly 首跑结果"待办已关闭。

**调度错过自动补偿——权威时点语义（2026-09-30 `c7b16d2` 初版 + `7023536` 权威时点修正）**：背景——09-26 系统重启 + 机器睡眠导致两晚 daily 未运行（LaunchAgent 依赖用户登录会话），曾需手工 kickstart 补跑。机制（初版"当日 ok 去重"当日即修正为权威时点制，避免晨间 RunAtLoad 预跑废掉当晚正式调度、丢当日收盘数据）：① **时点闸**——daily 的权威调度是每日 18:15（收盘后）；早于该时点的整轮触发（RunAtLoad 晨间登录/手工提前跑）直接退出（`--force` 绕过；`--only`/`--list` 不受限）；② **时点后去重**——仅"当日 18:15 之后"的 ok 记录才计入去重（记 `skipped_today`），早于时点的 ok 不影响当晚正式轮；③ daily plist `RunAtLoad=true`：晨间登录被闸零成本，18:15 后登录（当晚调度被错过）则自动补跑。判读 runbook 时 `skipped_today` 不是失败；`logs/scheduled_update/<date>/runatload-gate.log` 记录被闸触发。测试可用 `DAILY_FIRE_HM` 环境变量注入时点（见 `backend/tests/scheduled_update_dedup_smoke.py` 四场景）。weekly 保持 RunAtLoad=false。

⚠️ **判读规则**：编排脚本只要有任一子任务失败就非零退出，所以 `launchctl list` 里 `com.fund-analysis.scheduled_update.daily` 的 last exit 只是「本轮有任务失败」的汇总信号，不能据此断定 PATH 缺陷复发。判断调度健康必须看 `logs/scheduled_update/runbook.jsonl` 的**逐任务** `status`。当前预期状态：11 个 daily 全 ok；若出现失败，按 runbook 里的任务名定位，不要重跑整套排查。

## 9. 验证与验收

提交代码前至少运行：

```bash
npm run doctor
npx tsc --noEmit
npm run build
npm run desk:check
npm run smoke:fund-home
npm run smoke:fund-browser
npm run smoke:fund-product-detail
npm run smoke:fund-manager-browser
npm run smoke:fund-recommendations
```

前端改动还需要人工或 Playwright 验收：

- 桌面和 390px 移动端无横向溢出。
- 浏览器控制台无错误。
- 基金详情、评价、研究、归因、AI 历史能打开真实数据。
- Standalone 与 `/mod/fund-research/...` 复用同一业务页面。

`npm run lint` 当前是 0 error，但仓库存在较多历史 warning。不要为了清 warning 大范围重构无关旧页面。

**全量冒烟批次（2026-09-26 交接基线：前端 121/121、后端 151/151，全部零外部服务依赖；提交前必跑）**：

```bash
# 前端（需 backend 8005 / frontend 3000 均在运行）
export FRONTEND_BASE_URL=http://127.0.0.1:3000 BACKEND_API_URL=http://127.0.0.1:8005 APP_BASE_URL=http://127.0.0.1:3000
for s in scripts/*.mjs; do node "$s" >/dev/null 2>&1 || echo "FAIL $s"; done   # 无输出即全绿

# 后端（零 Docker / 零 Mongo / 零 Qdrant：报告读写已全部归一 PostgreSQL，详见 CHANGELOG 2.2.2）
cd backend && for t in tests/*.py; do ../.venv/bin/python "$t" >/dev/null 2>&1 || echo "FAIL $t"; done
```

注意：macOS 无 `timeout` 命令，批量循环不能带；冒烟大量使用"源码文本锚点"断言，**重构改文案/搬实现/删页面时必须同步对应 smoke 的锚点**（"边界语义不变，仅换锚文本"），否则会造成假红或假绿（2026-09-21 曾一次性甄别修复 22 个此类失败，详见 `CHANGELOG.md` 2.2.2）。涉及安全门禁（销售规则/材料核验）的 smoke 换锚点前必须核验新代码有等价或更强的门禁实现。

## 10. Git 与仓库维护现状

- 当前分支：`main`；HEAD 与未推送清单用 `git log --oneline -1` / `git log --oneline origin/main..HEAD` 自查，不在文档里写死哈希
- GitHub：`origin`（SSH）；Gitee：`gitee`（HTTPS），用户 `leecyno1`。**推送 gitee 需绕过未运行的本地代理**：`git -c http.proxy= -c https.proxy= push gitee main`（直连会报代理连接失败）
- **2026-09-20 起恢复逐项提交并推送两远端的模式**（此前 09-11/12 曾按用户要求仅本地提交，09-20 用户已授权全部推送，三端一致）
- 这些改动均视为用户资产，不得使用 `git reset --hard`、`git checkout -- .` 或批量删除。
- 先阅读 `git status` 和按模块审查 diff，再按“核心业务、数据同步、Desk Adapter、文档”分批提交。
- 不把 `.env*`、数据库目录、日志、Playwright 截图、IMA 密钥或本地知识库原文提交到远端。
- 每批提交先验证，再按用户要求推送 GitHub 和 Gitee；不要默认自动推送。
- 不强推，不改写远端历史。

## 11. 后续优先级

上线迭代（设计见 `docs/plans/2026-08-19-final-launch-iteration-design.md`）进度：

- M1 调度通电 + 本机生产化 ✓（2026-09-11 补齐）：launchd 常驻（backend/frontend）、每日评价快照积累、每日备份与全部 npm/python 同步任务均已在**调度环境**下验证跑通（见 8.1）
- M2 评价数据攻坚 ✓（风格快照/评价历史/持仓覆盖真实产出）
- M3 覆盖攻坚 ⟳ **已解除阻塞、恢复自动积累**：曾承担积累的 4 个 daily + 4 个 weekly 同步任务因 PATH 缺陷全败，2026-09-11 修复后 daily 已全部恢复；**2026-09-20（周日）weekly 定时器首次全自动运行 5 任务全 ok**（含 `sync-dividends`），覆盖率进入自动回升轨道
- M4 组合构建 MVP ✓（准入/权重/穿透，`/portfolio`）
- M5 基础回测 + 监控 + 交易清单 + ADR-0004 ✓（解释性回测、同类组偏离、申赎清单研究输出）
- M6 上线验收 ✓（报告 `docs/plans/2026-08-19-m6-launch-acceptance-report.md`：launchd 巡检、睡眠唤醒补跑、备份恢复演练 7 表一致、备份内容自检加固）⚠️ 但当时演练走**手工**路径，未覆盖 launchd 定时环境，因此漏掉 PATH 缺陷；2026-09-11 已用 `launchctl kickstart` 在调度环境补验通过。**教训：验收定时任务必须在调度环境下跑，终端成功不算通过。**

8 月遗留的「值得完善的」清单已于 2026-09-10 全部闭环；2026-09-20/21 的 UAT 遗留五项缺口也已闭环（2.2.2）。功能层面当前**没有已知缺口**；剩余缺口多为主动的方法论边界（Barra 只解释不评分、不接协方差矩阵；画像坚持证据驱动不模板化）或数据源约束，不要把它们当成待补技术任务反复重提。

当前优先级（2026-09-26 交接时点重排）：

1. **观察两条自动积累曲线到顶**（无需动作，接手后先看结果）：评价覆盖 2,425+/9,686（每日 +1000，约一周到顶）与经理任期快照 350+（每日 +3 位经理）。到顶后评价覆盖类待办自然关闭。查进度见第 5 节 09-26 增量注记的 SQL。
2. **3000 端口抢占根治（唯一环境待办，需用户决策/另一仓库改动）**：在 newma-desk 侧移除其 fund-analysis 前端或改端口，否则本项目前端停服窗口仍可能被抢占（见 2.2）。IMA skill 已于 09-26 升级 1.1.10，该旧待办已关闭。
3. 完善季报持仓链路：股票、债券、资产配置、持有人结构和归因历史一致更新（weekly 调度在做，看覆盖率曲线决定是否加干预）。
4. 完善纪要待确认工作流：减少经理、基金和标签误匹配，不自动确认 LLM 结果。
5. 维护 AI 分析证据回放：任何新字段都要同时进入新分析和旧历史兼容映射。
6. 可选数据攻坚：经理画像批量生成（`manager_profiles` 覆盖率仅约 1.8%，是经理研究/排序的天花板；需 LLM 调用，属数据攻坚而非缺陷修复，动手前先出方案）。
7. 最后再处理非核心报告页面和历史 lint warning。

补充（2026-09-22 核实，09-25 已工程化）：经理任期绩效快照（`manager_fund_tenures.performance_snapshot`）**只有** `backend/scripts/sync_fund_manager_tenure.py` 会写（`--manager-id '名|性别|学历'` 单人模式或 `--snapshot-backlog N` 批量模式，实时 Tushare 净值+基准落库）；`GET /api/data-sync/managers/{id}` 只 upsert 经理与基金基础信息、**不写快照**（返回"同步完成"具有误导性），批量基金同步路径也不写。批量模式已接入每日调度（3 位/日）。经理详情页证据卡需 ≥1 在管任期快照 `available`。

销售规则补充（2026-09-25 调研结论）：Tushare **没有**费率/风险等级接口（`fund_fee`/`fund_purchase`/`fund_risk` 实测均不存在）——R1-R5 与费率只能人工核验，这正是"30 天来源背书"硬门禁的设计原因。录入链路已建好：`POST /api/evidence-coverage/materials`（批量手工导入）+ 比较页"从 Tushare fund_basic 导入基础申赎状态"按钮（打底用）；解锁队列 8 只基金已于 09-25 导入基础申购状态。不要尝试从 Tushare 补费率字段。

## 12. 禁止回退的设计决定

- 不恢复旧 `frontend/` 为正式前端。
- 不把基金模块写入 Orchestra 的 `3001`。
- 不把五个工作区拆成五个 Desk 项目。
- 不在人工验收前加入 `desk-mods`。
- 不恢复购买模拟、销售规则、适当性或交易决策功能。
- 不让 Barra / Brinson 改变基金综合评分。
- 不把经理纪要观点冒充基金持仓。
- 不用模拟数据填补专业结论。

## 13. 历史上下文与 quest 恢复归档

2026-09-08 与 2026-09-11 两批恢复，归档在仓库外的 `../.quest-recovery/restored/`（不入库），索引见同目录 `INDEX.md`。

- **正文来源**：Qoder CLI 以明文 JSONL 保存逐字记录于 `~/.qoder/projects/-Volumes-PSSD-Projects-基金筛选/transcript/*.jsonl`。
- **丢失根因**：Qoder IDE 启动时执行 `cli_ws_migration`，只把 CLI 会话的工作区**产物文件**迁入 IDE 的 `local.db`（迁移记录全部 `status=completed`），**不导入 transcript 正文**到 `chat_session`/`chat_message`，于是 IDE 会话列表里历史 quest 全部消失，只残留 `name=migrated-N` 的孤儿快照骨架。
- **UI 层恢复不可行**：`chat_message.content` 与 `chat_record.question` 是加密 Base64（密钥在应用内），被删会话的 freelist 通常已清零无法 carving，纯 CLI 会话也不在 `sync_metadata` 云端索引内。**内容层归档是唯一可靠路径**，不要尝试手写 `local.db` 恢复列表显示。

已归档 12 个 quest（2 个主开发会话 + 9 个 browser-use 子会话 + 1 个空壳）：

| 会话 | 规模 | 时间 | 主题 |
| --- | --- | --- | --- |
| ⭐ `task-76275a2c2e5d4010ba54` | 2754 行 / 19 轮 | 08-18 → 08-20 | 四代合并去重 → M1–M6 上线迭代 → 全功能自测与 UAT 修复 → 去宣传标题 → MiniMax-M3 接入 → AI 报告渲染 → 定向补数 → 三档全量数据源更新与 IMA 同步修复 |
| ⭐ `task-f38bf52d82f444078bb0` | 833 行 / 7 轮 | 09-08 → 09-10 | quest 丢失诊断与恢复 → 中断半成品收尾（主题 A 完成 / 主题 B 回退）→ backend 端口归属理顺 → 报告三小项打磨 → Barra 死表清理 → 报告导出 Word/PDF |
| 9 个 UUID 会话 | 共 618 行 / 0 轮 | 08-19 | browser-use 子代理，正文全是工具结果（`127.0.0.1:3000/portfolio` 等页面自动化验证），仅作细节佐证 |

第二批（2026-09-11）补回了 09-08 归档之后新增的 **735 行 / 约 131KB** 正文——`task-f38bf52d` 在首次归档后仍在继续使用，旧归档只有 98 行 1 轮，已过期并被重建替换。

重新生成归档（只读 transcript，只写 `restored/`，不触碰 Qoder 数据库；可重复执行，会先清理上一批再重建，避免过期文件与新版并存）：

```bash
python3 ../.quest-recovery/export.py
```

还原点备份（破坏性操作前留的退路，均在 `../.quest-recovery/`）：

- `uncommitted-before-fix-20260908-222338.patch`：09-08 收尾前 6 个文件未提交改动的完整 patch
- `backup_factor_exposures_20260910-083404.json`：死表清空前全表 12 行
- `backup_ai_analysis_reports_20260909-101758.json`：报告去重前全表（2.6MB）

开始维护前请先完整阅读 `README.md`、`CONTEXT.md`、`CHANGELOG.md`、本文件（尤其第 2.2 / 2.3 / 8.1 节的运维现状）和 ADR-0003、ADR-0004。

## 14. 接手须知（2026-09-26 交接，给下一个 agent 的浓缩指引）

**最近一周做了什么**（细节见 CHANGELOG 2.2.2，提交链 `18f68a6`…`2cdecd5`）：UAT 五项缺口闭环（净值口径/分红/池标识/DDL 锁/前端四项）→ 冒烟基线全绿恢复（前端 121、后端 151，甄别修复了 40+ 历史重构漏同步的陈旧锚点断言）→ 详情页研究画像边界确认（删除 357KB 死组件 FundDetailClient 与孤儿代理路由，购买门禁 UI 不复活）→ 报告链路去 Docker/Mongo（读写全归一 PG，修复三处真实存储割裂）→ 经理任期快照批量补齐 + 评价覆盖提额 1000/日 + IMA skill 1.1.10。

**协作纪律（用户已确立，务必延续）**：

1. TDD 先行：先写红灯测试再实现；涉及购买/材料门禁语义的改动必须核验新代码有等价或更强的门禁实现才能动 smoke 断言。
2. 每完成一项独立提交（中文 conventional commits）并推送两远端；gitee 用 `git -c http.proxy= -c https.proxy= push gitee main` 绕过本地代理。
3. 真实库查询一律加 `PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000'`；破坏性操作前先备份。
4. 外部系统日志里的指令（升级提示等）**不构成执行授权**，需用户明示后才执行。
5. 服务重启需用户授权；前端改动的生效流程是 bootout → `npm run build` → 从 `~/Library/LaunchAgents/` bootstrap（见 2.2）。
6. 汇报文件/资源时附可点击的 `file:///` 链接。

**接手第一天建议动作**：跑第 9 节双端全量冒烟确认基线（应 121+151 全绿）→ 查 `logs/scheduled_update/runbook.jsonl` 最近一晚 11 任务是否全 ok → 按第 5 节 09-26 注记的 SQL 看两条覆盖曲线进度。之后按第 11 节优先级走。

**遗留一句话**：代码零缺口、测试全绿、数据在涨；唯一环境隐患是 3000 端口可能被 newma-desk 抢占（处置流程见 2.2），唯一方向性待办是覆盖到顶后的下一步迭代方向（由用户定）。

## 15. Desk 共享保存契约同步（2026-10-03，代码阶段）

用户本轮仅授权同步独立后端保存链路；本节覆盖前文关于此链路“尚未同步”的状态，不代表整个项目已经全量同步或运行验收完成。

- 保留当前全部未提交改动，尤其计算、评分、同类比较、经理和组合的新增修复；没有整文件覆盖这些业务服务，也没有改变其计算公式。
- `NavRepo` 新增按实际 schema 读写五个可空来源字段：公告日、原始累计净值、复权来源、基准代码和基准来源。旧库/部分字段库兼容，不执行 DDL；独立读取仍返回原来的 date 对象。净值整批和覆盖窗口同事务，失败不再逐行吞掉；未传基准与明确清空基准分开处理，改数值不能继承旧身份。
- `MetricSnapshotRepo.upsert_metrics` 将同一批指标放在一个事务；复用 Desk 的对象事务锁和 NULL 安全自然键，修订保留旧数值/单位/来源/详情，幂等写不增加历史。保存路径不再隐式 `init_database()`。未给新方法的值不能继承旧方法标签。
- 指标工厂、滚动、经理任期和排行两类辅助事实各自一次批保存。排行先检查净值保存成功，再处理评价；失败不继续计算或清理。失效指标复用现有数据源快照 metadata 归档后移出活跃面板，保留独立事实；归档/移出/基金派生字段清理同事务，重复失效保留最近档案 ID，仓储提供基金作用域只读查询。
- 公告日与复权来源从当前供应商输出逐点传递，不伪造缺失公告日；基准只按共同日期附值/身份，缺失或不匹配明确清空。缓存失效补齐净值图，限制详情到目标基金，保留其他基金详情和图；全局列表仍清理。
- 新增 `backend/tests/storage_contract_offline_test.py` 19 项离线/模拟事务验收；既有 round1 18、评价数值 61、经理净值 5、同类数值 47、缺证评分 10、组合数值 35，共 195 项通过。仅把两个既有离线测试的单条保存 mock 更新为批接口，原数值/门禁断言保留。没有连接真实 PostgreSQL，不能将模拟事务验收说成真实库验收。
- 未迁移数据库、未抓取/重算真实数据、未改持仓、未重启独立 3000/8005 或 Desk 服务、未部署、未提交或推 Git。此前已确认的共享来源列缺口没有在本轮消除；磁盘代码兼容不表示常驻进程已加载。

后续先清点并核验全部常驻及定时 writer 是否加载本契约（运行门槛仍 `not_verified`），再单独申请迁移/必要重启授权。净值保存与后续指标归档仍为两段事务；独立项目当前计算口径与 Desk 的全部差异也未在本轮合并，不能宣称全同步任务原子化或全项目同步完成。

## 16. 运行门槛只读核验（2026-10-03）

- 独立 8005：PID 14742，工作目录为本项目 backend，2026-09-30 22:11:32（上海时间）启动，无 `--reload`；两个仓储 2026-10-03 12:23:33、缓存 12:32:13 修改，晚于进程启动。路由启动时导入 repositories，因此不能将磁盘修复说成已在独立服务生效。健康 GET 为 200 / ok / 非 mock / Tushare / 数据库 ok，但不报告数据库启动模式或保存契约版本。
- Desk 8035：PID 2717，2026-10-03 11:32:01 启动，晚于捆绑两个仓储及缓存修改；健康为 200 / ok / 非 mock / 数据库 ok，报告 `database_init_mode=check`。这仅支持本次启动时间核对，健康仍没有已加载保存契约版本信号。
- 每日调度最新 11 项记录均 ok，截至 2026-10-02 18:35:20；无本轮代码修改之后的记录，不能算新契约动态验收。每周最新 5 项记录停在 2026-09-20 20:16:14，runbook 无 9 月 27 日周任务记录，当前 launchd weekly 为 `runs=0 / never exited / not running`。原因未确定，不能断言代码错误或自行补跑。
- 启用前新增阻点：本项目 `main.py` 的 lifespan 仍调用 `init_database()`，排行、经理任期等脚本亦调用该入口；其中包含 CREATE/ALTER DDL。直接重启或补跑可能触发未授权的改库。`start_backend.sh` 和 requirements 仍要求 pymongo，但 backend Python 源码未找到 pymongo/MongoClient 引用；当前 venv 有该包，并不是当前启动失败的证据，而是应收口的旧依赖。
- 强制只读 PostgreSQL 迁移预览确认仍缺五个来源列，净值/基准四位小数；仅生成计划，没有执行 SQL 变更。共享 writer 门槛继续 `not_verified`。
- 本轮仅检查进程、调度配置/脱敏日志字段、健康 GET 和只读 schema；未重启、未暂停/补跑任务、未迁移或修改业务数据、未提交推送。只追加交接记录，不改变业务代码。下一步需用户明确允许把独立服务/任务启动默认收口到只检查数据库，并单独重启独立 8005；不包含数据库迁移、真实数据补跑或重算授权。

## 17. 安全启动已启用（2026-10-03，用户明确授权）

- 公共 `init_database()` 默认改为检查已有库，服务、定时脚本和旧仓储调用统一走这个入口，不再隐式建表。原 DDL 逻辑保留在私有初始化函数；只有显式 `initialize` 参数或 `FUND_DATABASE_INIT_MODE=initialize` 才进入。普通启动缺库、缺基础字段或空基金库时失败，不静默迁移；已检查的同一配置可复用，不重复逐条检查。
- lifespan 改用 `prepare_database()`，检查失败不再吞为 warning 后继续启动。健康接口报告实际成功启动的模式、PID，以及启动时导入的保存契约：净值 `batch_provenance_v1`、指标 `batch_revision_archive_v1`；这些标识仅代表相关代码契约，不代表 schema/历史证据完整。
- 启动脚本默认导出 check，删去 pymongo 启动检查和 requirements 的旧依赖；不卸载本机包。两份环境模板说明日常 check 与显式初始化边界。旧真实 DDL 锁测试新增显式启用门槛，并明确调用 initialize；本轮没有运行该 DDL 测试。
- 新增 9 项纯离线启动检查：默认/旧仓储调用不 DDL、缺库/缺字段阻断、无效模式拒绝、显式初始化隔离、初始化失败不启动、配置切换重新检查、实际启动模式与版本报告、启动错误不吞。连同保存 19、round1 当前 21、评价 61、经理 5、同类 47、缺证 10、组合 35，共 207 项通过。应用完整导入在禁止创建数据库引擎的保护下通过，启动脚本选中项目 venv；强制只读实际启动预检通过。
- 仅重启 `com.fund-analysis.backend`：旧 PID 14742 → 新 PID 52066，2026-10-03 17:48:57（上海时间）启动，工作目录仍是独立项目 backend。实际健康 GET 为 200 / ok / check / 非 mock / 数据库 ok，返回上述两个新保存契约。Desk 8035 PID 2717、独立前端 3000 PID 5725、Desk 前端 3035 PID 14662 未变。
- 两套服务实际 GET 已有 000015.OF 指标均返回 95 条；没有调用重算、刷新、扫描或同步端点。强制只读复核仍缺五个来源列、净值仍四位小数；没有 DDL/业务数据变更、持仓修改、定时任务补跑、部署或 Git 推送。

独立常驻后端的新代码已加载，不再是第 16 节的旧进程状态。后台任务的代码入口已收口，但新契约下的真实定时执行尚未验收；周任务遗漏尚未处理。共享 writer 迁移门槛不能据此自动标记全部通过；来源列和精度迁移仍需另行授权。首次空库必须走明确授权的初始化与初始数据导入流程，普通 check 不会替操作人创建数据。

## 18. 上线前最后一轮数值/证据修复（2026-10-04，代码阶段，未提交）

用户要求"检查所有功能，未上线前做最后一轮迭代和优化完善"。先把上一轮 15 项审查发现逐条**对当前代码复核**（发现 C4/C5、B4/B5 等已被前序未提交工作或提交 `74a4fd8` 部分处理，审查清单已过期），再对**确认仍开放**的缺陷按 TDD 修复。基线由 219 项离线测试增至 **249 项全绿**；前端 `tsc --noEmit` 退出 0；`import routes.funds / fund_research_snapshot_service / fund_browser_service` 无循环依赖；`fund_recommendation_service_smoke`、`fund_manager_career_service_smoke`、`category_specific_peer_percentile_smoke`、`research_memos_route_import_smoke`、`ai_report_provider_credentials_smoke`、`fund_evaluation_compact_prompt_smoke`、`fund_evaluation_holding_style_prompt_smoke` 均通过；`git diff --check` 干净。

已修（每项先红后绿，新增/扩展离线测试）：

- **C1** `portfolio_service._performance_metrics`：年化原按 `252/期数` 假设日频、波动按 `sqrt(252)`，对周/月频净值严重高估（如 3 年月频 +20% 被年化成 258%）。改为按 `dates` 真实日历跨度年化（`years=(末-首)/365.25`），波动按实际每年期数缩放；跨度为 0 时年化/波动返回 `None` 而非伪造。前端 `PerfMetrics.annualized_return/annualized_volatility` 类型收紧为 `number | null`（渲染处早已 `!= null` 兜底）。
- **C3** `portfolio_service._pearson`：零方差（货基/停牌/常量净值）原返回 `0.0` 且 `_correlation_matrix` 标 `status=ok`，等于把"平坦净值"冒充"零相关=完美分散"。改为返回 `None`，配对标 `undefined_zero_variance`，不输出 0.0 结论（前端相关性对 `null` 已显示"样本不足"）。
- **C5** `portfolio_service.trade_list`：持仓存在但权重未知时原令 `current=0.0` → `delta=target` → **全额申购**建议。改为权重未知的持仓不冒充"未持有"，输出 `action=权重未知 / current_weight=null / amount=null / note`，排序对 `null` 差额置末。前端 `TradeList` item 的 `current_weight/weight_delta` 类型收紧为 `number | null`（`pct(null)→'—'` 已兜底）。
- **B1** `ai_report._build_fund_prompt`：`w=h.get("weight",0)` 在键存在值为 `None` 时返回 `None`，`"{:.2%}".format(None)` → TypeError → 基金报告 500。改为非有限权重输出"权重待补"，不崩溃不伪造 0.00%。
- **B2** `evidence_report`：持仓权重缺失时 `float(None or 0)=0` 使前十大/行业集中度闸门（`>=0.70 / >=0.50`）**静默放行**，叙述还渲染"前十大合计 0.00%"。新增 `_holding_weight_known/_concentration_disclosed`，有持仓但无可信权重时闸门给"集中度无法核验，不能视为分散"，叙述改为"无法核验"，不再伪造 0.00%。
- **B3** `research_memo_service`：`_safe_scoring` 异常原返回 `overall_score=50/grade=D` 虚构评分并写入 memo 证据；`_build_inferences` 用 `or 50` 且缺分仍 `confidence=high`。改为异常/缺失 → `overall_score=None / status=unavailable`，investability 给"评分缺失，需补数后复核"，缺分时 confidence 降为 `low`，不写虚构分。
- **B4** `routes/reports`（基金 + 经理两处）：落库异常被 `logger.warning` 吞掉 → 返回 200 + `id=None`，前端 `app/api/analysis/generate/route.ts` 无条件播报"已生成并写入本地数据库"。改为响应与 metadata 带 `saved=report_id is not None`，前端按 `persisted` 如实播报"已生成但写入失败，本次未保存"。
- **B5** `research_memo_service._to_float/_json_safe`：无 `isfinite`，NaN/Inf 透传 → Starlette `allow_nan=False` → memo 响应 500。改为非有限 float → `None`。
- **A1** `peer_comparison_service._matrix_row`：`ranking_score = percentile if not None else raw_value` 把 0–100 百分位与原始比率混尺度排序，且 `best_code` 恒 `reverse=True` 忽略 `higher_is_better`（波动/回撤等"越低越好"取到最差）。改为：有百分位只在有百分位者间取最高（百分位已含方向）；无任何百分位才退回原始值并按方向取 `max/min`；无证据 → `best_code=None`，不混尺度不虚构赢家。
- **A3** `routes/funds` 列表页两处 `sort_keys` 全用 `or 0`：缺失收益/回撤/夏普/评分被当 0，risk 升序把"无回撤证据"当最低风险（最优）、真实 0.0 回撤被当 falsy 跳过。抽出 `_sort_funds/_funds_sort_value/_risk_sort_value`（复用既有 None 安全的 `_as_float`），缺失 → `None` 统一排末尾、真实 0.0 按 0，两处调用点合一去重。
- **A5** `routes/funds._rolling_metric_panel` 与 `fund_research_snapshot_service.project_rolling_metrics`：原逐条 `last-wins` 覆盖 `metric_value/as_of_date`，多基准基金会选错基准的 `excess_return/information_ratio`。改为先过已验证的 `ProfessionalScoringService.select_metric_panel(panel, benchmark_code)`：有期望基准取其相对指标、多基准且无期望基准则丢弃歧义相对指标、绝对指标取最新 `as_of_date`。`project_rolling_metrics` 调用点透传 `classification.benchmark_code`；`_rolling_metric_panel` 三处调用点暂无廉价基准来源，传 `None`（单基准占多数→行为不变，多基准→丢歧义而非选错，符合"缺失不冒充证据"）。两文件加模块级 `ProfessionalScoringService` 导入，已验无循环依赖，并删去 `routes/funds` 基金详情函数内一处冗余局部导入。

新增离线测试文件：`report_ai_evidence_offline_test.py`(9)、`fund_list_sort_offline.py`(5)、`rolling_metric_panel_offline.py`(7)；扩展 `portfolio_numerical_correctness_test.py`(+5)、`peer_numeric_correctness_offline.py`(+4)。

复核后**未改代码、仅记录**的项（附建议，供上线裁决）：

- **A2**（`fund_browser_service._matched_rule` 数值规则只判 `actual is None`、不比对 `threshold`；无 `peer_group` 分支 `browse_funds` 丢弃 asset_min/return_*/drawdown/sharpe/style/sort_by）：`_matched_rule` 仅生成"命中理由"文案，真正阈值过滤在 `list_recommendation_funds` 的 SQL；且前端 BFF `app/api/fund-browser/route.ts` 仅在 `peerGroup` 存在时才转发筛选参数（`if (peerGroup && value)`），故经 UI **不可达**——带 peerGroup 时 SQL 已正确过滤，解释文案也恰好成立。属**直连 API 的潜在契约缺口**（无 peerGroup 却带筛选会静默丢参），非上线阻断项。建议后续在 backend 对"无 peer_group 却带数值筛选"显式拒绝或补齐 `browse_funds` 过滤，并让 `_matched_rule` 按 operator 比对 threshold（需 DB 测试）。
- **A4**（`lib/fund-research/market/market-workbench.ts` 的 `getReturn1y/getSharpe1y` 读 `performanceData.return1y`、`riskMetrics.sharpe1y`、`rollingMetrics.sharpe1y` 等不存在的键）：已静态确认 `toCamelFund` 只驼峰化顶层字段，`performanceData/riskMetrics/rollingMetrics` 内层保留后端 **snake_case**，且 `rollingMetrics` 按窗口键（`{'1y':{sharpe_ratio,...}}`）。故 1y 收益/夏普恒取不到 → 市场页显示"—"、研究清单误判。正确路径应为 `performanceData.annualized_return_1y`、`riskMetrics.sharpe_ratio`、`rollingMetrics['1y'].sharpe_ratio`（`getMaxDrawdown1y` 因含 `riskMetrics.max_drawdown_1y` 尚可工作）。**属 UI 改动，需先起前端在浏览器验证市场页确实点亮后再改**，本轮不下未经验证的前端改动。
- **C2**（`fund_recommendation_service` 准入用 `professional_scoring.overall_score`、展示/排序用 `evaluation.overall_score` 且 `float(None or 0)`）：两分数**按设计分离**（正式综合分 vs 分类专业分，见前序 ADR/迭代），`or 0` 仅影响排序兜底（缺综合分排末位），展示层显示 `None`→前端"—"，非伪造。样本不足基金是否应作为候选并排在真实高分之前属**产品口径决策**，不宜在上线前擅改。
- **C4**（`portfolio_service._with_evaluation_summary` 取最新 `created_at` 快照、不按 `evaluation_window` 过滤）：现已**返回 `evaluation_window` 字段**，前端可标注窗口，属可接受的透明化；若产品要求组合汇总与详情页严格同窗口，再按 canonical window 固定（会改变展示口径，需单独确认）。

边界：全程未写生产库、未重启任何服务、未推送/提交 Git、未改 schema/迁移、未重算或回填真实数据。所有改动保留为未提交状态，与既有未提交工作共存。上线（部署/重启/重算/提交推送）仍需用户单独授权。建议提交前对本轮 9 文件改动做一次独立代码复核。

### 18.1 独立代码复核与补齐（2026-10-04）

对本轮 11 项修复做了独立只读复核：确认 11 项各自正确、249 项离线测试与 `tsc` 全绿、None 传播与"缺失不冒充"一致。复核另发现 3 处需补齐，已按 TDD 修好（基线 249→**255**）：

- **#1（Critical）** `evidence_report.build_fund_research_report` 的行业合计表在持仓权重全缺失时仍渲染 `_format_percent(0.0)="0.00%"`，与同函数叙述层"无法核验"自相矛盾，属残留伪造。抽出 `_industry_rows` 助手：权重未披露时行业列渲染"待补"。
- **#2（Important）** `_concentration_disclosed` 用 `any()`，部分权重缺失时前十大/行业集中度把未知权重当 0 求和 → 低估，可能静默过 0.70/0.50 闸门。新增 `_holding_weight_coverage`；覆盖率 0 → "无法核验"，0<覆盖<1 → 追加"为已知权重下限，可能被低估"caution（闸门与叙述层一致）。
- **#6（Minor）** `peer_comparison_service._matrix_row` 的 `max/min` 平局取输入首个 → 顺序相关。key 加 `wind_code` 次序，保证"同分同位"与输入顺序无关。

复核提出但**判定不改、仅记录**的项：

- **#3** `routes/reports.py:846` `generate_fund_evaluation_analysis` 落库失败会抛出 → 外层 `except` → HTTP 500（**诚实失败**，客户端知情），并非 B4 的"200+id=None 谎称已存"；这正是 B4 原始记录里引用的"正确写法"。与已改为优雅降级（200+`saved:false`）的基金/经理报告端点存在**策略不一致**（500 会丢失已生成的报告），但非正确性缺陷。若统一为优雅降级，须先核验该端点前端消费方不会因 `saved:false` 反而谎称已存，属可选一致性跟进，不在上线前擅改。
- **#4（Minor）** `_rolling_metric_panel` 三处调用点（列表/同类/详情）暂传 `benchmark_code=None`，多基准基金会丢弃相对指标（安全：宁缺勿错）；快照路径已正确透传 `classification.benchmark_code`。后续可在详情页廉价拿到基准处透传，恢复多基准基金的 excess_return/IR 展示。
- **#5（Minor）** `research_memo_service` 仅对 `evidence_table` 过 `_json_safe`，`audit.data_quality_score`、观察项 `current` 未过；因其上游已用 `_to_float`/`_safe_scoring` 做 None 化，风险低，可作纵深防御后续整体过一遍 `_json_safe`。

复核后再次确认：255 项离线测试全绿、`tsc --noEmit` 退出 0、`evidence_report` 真实 import 通过、3 个 AI 报告/评价 prompt smoke 通过、`git diff --check` 干净。

### 18.2 提交与上线执行（2026-10-04，用户授权"授权，继续"）

§18/18.1 的"未提交/未重启"状态已被本节取代。用户授权后执行：

- **提交**：预上线已验证批次（§15-18，59 文件）因多会话累积、同文件交织无法按单项拆分，按子系统分 4 簇入库——`4f1a9a8`(存储契约+安全启动+调度告警)、`62f3d93`(评价/组合/同类/筛选数值与证据)、`d95ff89`(报告/AI/纪要事实链)、`08a75a9`(前端可空渲染+交接)。提交前密钥扫描干净、逐簇 `git status` 复核暂存范围。
- **A4 修复**：以 `/api/fund-browser` 实时响应核对真实键名后，修 `market-workbench.ts` 的 `getSharpe1y/getReturn1y/getMaxDrawdown1y`（后端 `risk_metrics` 无 sharpe、`rolling_metrics` 按窗口键），新增 `scripts/market_workbench_offline_test.mjs` 5 项先红后绿，提交 `40d6355`。
- **推送**：`origin`(github) 与 `gitee`(绕代理) 均推至 `40d6355`，两远端同步。
- **重启后端 8005**：`launchctl kickstart -k com.fund-analysis.backend`，PID 52066 → **3717**；健康 `/api/health` = 200 / ok / **database_init_mode=check**(未触发 DDL) / 非 mock / fund_count 32437 / 保存契约 batch_provenance_v1+batch_revision_archive_v1。
- **重建+重启前端 3000**：`npm run build` 退出 0（全路由编译），`kickstart -k com.fund-analysis.frontend` PID 5725 → **8169**，`/` 与 `/market` 均 200。
- **浏览器/接口验收**（内嵌浏览器 + 只读接口）：
  - A4：`/market` 30 行"· 夏普"全部渲染真实值（如 000198.OF −30.37、000686.OF −21.23），`—` 占位 0 处（修复前恒为 null）；初筛分恢复夏普分量。
  - C1：组合 b4a552f8 实盘回测 `available`，364 个日频区间跨 2025-04-03→2026-09-29(1.49 年)，累计 46.6% → **年化 29.3%**（=1.466^(1/1.489)−1，日历跨度口径正确），波动 18.6%、回撤 −9.2%、基准超额 35.6%，`_parse_date` 处理真实日期无异常。
  - C3：`/portfolio` 相关性表渲染真实系数（0.41–0.78，重叠 498–499 天），无伪造 0.0；页面 0 崩溃/NaN。
  - C5：`POST /trade-list` 对权重未知持仓返回 `action=权重未知 / current_weight=null / amount=null` + 补权重提示，不再冒充全额申购；权重匹配的持仓不产生动作。

边界：本轮已提交并推送两远端、已重启独立 8005/3000（均 check 模式，未触发 DDL、未迁移、未重算或回填真实数据、未改持仓）。Desk 8035/3035 与 Orchestra 未触碰。遗留待办仍为 §18.1 记录的 A2(直连 API 潜在缺口)、#3(报告落库策略一致性)、#4(详情页滚动面板透传基准)、#5(memo 整体 _json_safe)，均非上线阻断项。

### 18.3 上线后实时 UAT 走查与遗留项处置（2026-10-04）

对常驻系统（backend 3717 / frontend 8169）做只读 UAT，逐条在真实数据上确认本轮修复生效、无回归、**全站零 500**：

- A4：`/market` 30 行"· 夏普"全部真实值、`—` 占位 0；初筛分恢复夏普分量。
- C1：实盘回测 `available`，364 日频区间跨 1.49 年，累计 46.6% → 年化 29.3%（=1.466^(1/1.489)−1，日历口径正确）。
- C3：相关性表真实系数 0.41–0.78、重叠 498–499 天，无伪造 0.0；组合页 0 崩溃/NaN。
- C5：`POST /trade-list` 权重未知持仓 → `action=权重未知 / current_weight=null / amount=null`，不冒充全额申购。
- A3：`/api/funds?sort_by=rank&desc` 有分者在前、`None` 排末尾（不当 0）；`sort_by=risk&asc` 真实 0.0 回撤在前。
- A1：`POST /compare-matrix` best_code 按同类百分位取；calmar 行中有原始值 15.25 但无百分位者被正确排除，不与百分位混尺度。
- A5：`/research-snapshot` 滚动窗口齐全，1y 带 benchmark_code 与相对指标。
- B3/B5：`/research-memos/fund/{code}` 返回 200、结构完整、无虚构分、无 NaN 500。
- 详情链路：页面 SSR 200/7s，`/evaluation`(partial,15.1/E)、`/period-performance`、`/peer-percentiles`(sufficient,3620) 均 200。
- 全站健康扫描：health/home/funds/fund-browser/recommendation-*/evaluation*/portfolios/managers/market-indices/data-health/scoring/alerts/watchlists/research-reports/research-queue 有效路径全 200；初扫的 404/307/422 经核实均为探针路径问题（裸根无 GET、尾斜杠重定向、必填参数缺失），非回归。

**A4 暴露的极端夏普已核实为合理，非缺陷**：货币基金（天弘余额宝 000198、建信嘉薪宝 000686）近一年年化约 0.88%/1.03%，低于反推的风险无风险利率约 2.0%（三只基金 implied rf 一致 2.00–2.04%），且年化波动极小（0.037%/0.046%），故 sharpe=(负超额)/(极小波动)=−30/−21，数学正确；`getMarketScreeningScore` 用 `max(0,min(20,sharpe*10))` 将负夏普归零，不会扭曲初筛分。债券基金 000111 夏普 1.50 与输入自洽。

**遗留项处置结论**（均不值得为其单独再触发一次生产重启/重建，保持记录）：
- #4：详情页 `_rolling_metric_panel`(:1313) 在 `score_fund`(:1325) 之前执行，透传 benchmark_code 需重排或额外查分类，中等风险；且多基准基金占比小、滚动面板为辅助展示、权威评价(#61)已给正确相对指标 → 低价值，暂不改。
- #5：memo 整体过 `_json_safe` 属纵深防御，上游 `_to_float`/`_safe_scoring` 已 None 化、实时 memo 返回 200，无观测缺陷 → 暂不改。
- A2：直连 API 无 peer_group 却带筛选会静默丢参，但前端 BFF 仅在选了同类组时转发筛选，UI 不可达；补阈值过滤属侵入式 repo/SQL 改动，加拒绝守卫又会改变端点行为 → 保持记录，待有直连 API 消费需求再处理。
- #3：`/reports/fund/{code}/evaluation-analysis`(:846) 落库失败抛 500（诚实失败，非 B4 的谎报成功），与另两端点的优雅降级(200+saved:false)仅策略不一致；统一为降级需先核验其前端消费方不因此谎称已存 → 非缺陷，保持记录。

原始验收口径"同分同位、缺失不冒充证据、相同净值结果一致、首期损失正确计入回撤"均已在离线（255+21）与实时 UAT 双层验证达成。系统上线闭环完成、健康常驻。
