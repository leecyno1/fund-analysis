# Qoder 项目交接

更新时间：2026-09-12

当前状态：`main` 上有 2026-09-11/12 的若干本地提交（调度修复 `629be0a` 起，含多批文档记忆重建与纠正），**均未推送，按用户要求 local 领先 `origin` / `gitee`**；确切数量用 `git log --oneline origin/main..HEAD` 自查，不要在文档里写死。前端 3000 与后端 8005 均由 launchd 从**本仓库**常驻托管。`docs/plans/2026-08-19-final-launch-iteration-design.md` 的 M1–M6 全部完成（M1 的调度缺陷于 2026-09-11 补齐并在调度环境验证，见 8.1），8 月遗留的「值得完善的」清单已于 2026-09-10 全部闭环。2026-09-12 IMA 授权恢复后 **9 个 daily 调度任务全绿，当前无已知技术待办**；下一步只需核对周日 20:00 weekly 定时器首次全自动运行的结果。

历史沿革：2026-08-18 完成四代合并去重大重构（v2.0.0）：删除旧 `frontend/`、Wind 数据链路、一代 screening/sync 页面与对应 API；旧路由保留薄重定向；历史文档归档至 `docs/history/`。2026-08-19 起进入上线迭代（v2.1.0），2026-09-10 收敛至 v2.2.0，2026-09-11 发布 v2.2.1（修复 launchd 调度环境缺陷 + 重建项目上下文记忆）。逐条变更见 `CHANGELOG.md`，架构见 `ARCHITECTURE.md`。

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

怀疑改动不生效时，先确认端口实际由谁管理、跑哪份代码：

```bash
lsof -nP -iTCP:8005 -sTCP:LISTEN -t          # 取 PID
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

PATH 修复后曾暴露的第二个问题（`research:sync-ima` 返回 `skill auth failed`）已于 2026-09-12 关闭，且**不是本地凭证失效**——是 IMA 服务端授权状态，用户在 IMA 侧重新授权后即恢复。排查方法与判读规则见 8.1。

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

# 同类评价覆盖
npm run funds:backfill-peer-evaluation -- --limit 100

# 基金经理目录和任职关系
npm run funds:sync-manager-universe
npm run funds:sync-manager-tenure

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
| 每个交易日收盘后 | 浏览器核心净值、滚动指标、同类评价增量 | 控制批次和 Tushare 频率 |
| 每日 | IMA 纪要增量上传、经理身份同步、待确认数量统计 | LLM 建议不能自动转人工确认 |
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

⚠️ **判读规则**：编排脚本只要有任一子任务失败就非零退出，所以 `launchctl list` 里 `com.fund-analysis.scheduled_update.daily` 的 last exit 只是「本轮有任务失败」的汇总信号，不能据此断定 PATH 缺陷复发。判断调度健康必须看 `logs/scheduled_update/runbook.jsonl` 的**逐任务** `status`。2026-09-12 起 9 个 daily 任务全绿，该退出码应回到 0；若再次变 1，按 runbook 里的任务名定位，不要重跑整套排查。

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

## 10. Git 与仓库维护现状

- 当前分支：`main`；HEAD 与未推送清单用 `git log --oneline -1` / `git log --oneline origin/main..HEAD` 自查，不在文档里写死哈希
- GitHub：`origin`（SSH）；Gitee：`gitee`（HTTPS），用户 `leecyno1`
- **2026-09-11/12 的提交全部未推送**（按用户要求）：调度 PATH 修复 `629be0a`（唯一代码提交）+ 其后多批文档提交（记忆重建、调度健康度判读、纠正 IMA 误判、daily 全绿验收）。推送前先 `git status` 复核、按批次确认
- 已推双远端的提交链：`7d88375`（数据层加固 + 回退 report_id TEXT）→ `eb741d2`（报告三小项打磨）→ `198fdd1`（Barra 死表清理）→ `105454e`（报告导出）
- 这些改动均视为用户资产，不得使用 `git reset --hard`、`git checkout -- .` 或批量删除。
- 先阅读 `git status` 和按模块审查 diff，再按“核心业务、数据同步、Desk Adapter、文档”分批提交。
- 不把 `.env*`、数据库目录、日志、Playwright 截图、IMA 密钥或本地知识库原文提交到远端。
- 每批提交先验证，再按用户要求推送 GitHub 和 Gitee；不要默认自动推送。
- 不强推，不改写远端历史。

## 11. 后续优先级

上线迭代（设计见 `docs/plans/2026-08-19-final-launch-iteration-design.md`）进度：

- M1 调度通电 + 本机生产化 ✓（2026-09-11 补齐）：launchd 常驻（backend/frontend）、每日评价快照积累、每日备份与全部 npm/python 同步任务均已在**调度环境**下验证跑通（见 8.1）
- M2 评价数据攻坚 ✓（风格快照/评价历史/持仓覆盖真实产出）
- M3 覆盖攻坚 ⟳ **已解除阻塞、恢复自动积累**：曾承担积累的 4 个 daily + 4 个 weekly 同步任务因 PATH 缺陷全败，2026-09-11 修复后 daily 已全部恢复，weekly 路径已用 `funds:sync-product-profiles`（100 只，0 失败）抽样补跑验证；剩余三个重量级 weekly 任务由每周日 20:00 定时器继续
- M4 组合构建 MVP ✓（准入/权重/穿透，`/portfolio`）
- M5 基础回测 + 监控 + 交易清单 + ADR-0004 ✓（解释性回测、同类组偏离、申赎清单研究输出）
- M6 上线验收 ✓（报告 `docs/plans/2026-08-19-m6-launch-acceptance-report.md`：launchd 巡检、睡眠唤醒补跑、备份恢复演练 7 表一致、备份内容自检加固）⚠️ 但当时演练走**手工**路径，未覆盖 launchd 定时环境，因此漏掉 PATH 缺陷；2026-09-11 已用 `launchctl kickstart` 在调度环境补验通过。**教训：验收定时任务必须在调度环境下跑，终端成功不算通过。**

8 月遗留的「值得完善的」清单已于 2026-09-10 全部闭环（组合目标配置 UI、基金详情页 AI 报告入口、报告导出 PDF/Word、定向补数、三项打磨）。功能层面当前**没有已知缺口**；剩余缺口多为主动的方法论边界（Barra 只解释不评分、不接协方差矩阵；画像坚持证据驱动不模板化）或数据源约束，不要把它们当成待补技术任务反复重提。

当前优先级：

1. **核对 weekly 调度首次全自动运行结果**：下一个周日 20:00 后查 `logs/scheduled_update/runbook.jsonl`，确认 `funds:update-universe` / `sync-manager-universe` / `sync-manager-tenure` 三个重量级任务 ok（`sync-product-profiles` 已于 2026-09-11 抽样验证通过），并对比覆盖率是否开始回升。
2. 再提升基金评价覆盖：优先补齐可分类但缺少净值/指标的同类样本（调度已恢复，可依赖每日增量）。
3. 完善季报持仓链路：股票、债券、资产配置、持有人结构和归因历史一致更新。
4. 完善纪要待确认工作流：减少经理、基金和标签误匹配，不自动确认 LLM 结果。
5. 维护 AI 分析证据回放：任何新字段都要同时进入新分析和旧历史兼容映射。
6. 可选数据攻坚：经理画像批量生成（`manager_profiles` 覆盖率仅约 1.8%，是经理研究/排序的天花板；需 LLM 调用，属数据攻坚而非缺陷修复，动手前先出方案）。
7. 最后再处理非核心报告页面和历史 lint warning。

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
