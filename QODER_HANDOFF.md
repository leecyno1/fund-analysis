# Qoder 项目交接

更新时间：2026-08-16

## 1. 项目定位

本项目是面向普通用户的独立基金研究与选择工具，核心流程是：

`基金数据库 -> 基金浏览与比较 -> 基金分类与评价 -> 经理纪要研究 -> 业绩归因 -> AI 现场分析 -> 标签候选`

不开发交易执行、购买金额、销售规则、个人适当性和投资决策。报告系统不是核心。

Newma Desk 只是可选宿主。独立应用和 Desk Adapter 共用业务页面，禁止复制两套业务实现。人工验收前不要加入 `desk-mods`。

## 2. 当前运行入口

- 正式前端：Next.js，`http://127.0.0.1:3000`
- 正式后端：FastAPI，`http://127.0.0.1:8005`
- PostgreSQL：仓库内 `.data/postgres/`
- 后端健康检查：`GET http://127.0.0.1:8005/api/health`
- Desk 描述：`desk/suite.json`
- Desk 发现：`GET /.well-known/newma-desk-suite.json`
- 旧目录 `frontend/` 只用于迁移参考，不再是开发入口
- `3001` 属于 Orchestra，本项目不得占用

启动顺序：

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
7. AI 分析：用户选中单只基金后现场运行，读取评价、归因和纪要，保存完整历史与版本。
8. 标签候选：按标准类别和风格返回不超过 10 只候选基金。
9. Newma Desk Adapter：独立 Suite 描述、工作区映射、上下文和数据能力健康检查。

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

## 8. 建议的定时更新节奏

当前仓库有同步脚本，但还没有统一的定时任务编排、互斥锁、运行记录和失败告警。Qoder 后续应先实现一个薄的 `scripts/scheduled_update.sh` 编排层，再接 macOS `launchd` 或服务器 `systemd timer`。不要把调度逻辑写进 Next.js 请求。

建议节奏：

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

- 当前分支：`main`
- GitHub：`origin`
- Gitee：`gitee`
- 当前工作树有大量尚未提交的历史改动和新增文件，交接时约 350 项。
- 这些改动均视为用户资产，不得使用 `git reset --hard`、`git checkout -- .` 或批量删除。
- 先阅读 `git status` 和按模块审查 diff，再按“核心业务、数据同步、Desk Adapter、文档”分批提交。
- 不把 `.env*`、数据库目录、日志、Playwright 截图、IMA 密钥或本地知识库原文提交到远端。
- 每批提交先验证，再按用户要求推送 GitHub 和 Gitee；不要默认自动推送。
- 不强推，不改写远端历史。

## 11. 后续优先级

1. 先稳定数据更新：统一调度、锁、运行记录、增量更新和失败告警。
2. 再提升基金评价覆盖：优先补齐可分类但缺少净值/指标的同类样本。
3. 完善季报持仓链路：股票、债券、资产配置、持有人结构和归因历史一致更新。
4. 完善纪要待确认工作流：减少经理、基金和标签误匹配，不自动确认 LLM 结果。
5. 维护 AI 分析证据回放：任何新字段都要同时进入新分析和旧历史兼容映射。
6. 最后再处理非核心报告页面和历史 lint warning。

## 12. 禁止回退的设计决定

- 不恢复旧 `frontend/` 为正式前端。
- 不把基金模块写入 Orchestra 的 `3001`。
- 不把五个工作区拆成五个 Desk 项目。
- 不在人工验收前加入 `desk-mods`。
- 不恢复购买模拟、销售规则、适当性或交易决策功能。
- 不让 Barra / Brinson 改变基金综合评分。
- 不把经理纪要观点冒充基金持仓。
- 不用模拟数据填补专业结论。

开始维护前请先完整阅读 `README.md`、`CONTEXT.md`、本文件和 ADR-0003。
