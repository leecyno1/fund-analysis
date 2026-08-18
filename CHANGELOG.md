# Changelog

本项目的重要变更记录。历史版本（1.0.0 及以前的阶段总结）见 `docs/history/CHANGELOG.md`。

## [2.0.0] - 2026-08-18

### Removed — 四代合并去重

- 删除旧独立前端 `frontend/` 整目录（迁移参考使命完成，业务实现已全部由根目录 Next.js 承载）。
- 删除一代 Wind 数据链路：`backend/wind_service/`、`services/wind_service.py`、`service_registry` 的 Wind 分支与 `get_wind_service()`。数据源统一为 Tushare。
- 删除一代筛选/评分前端链路：`/screening`、`/sync` 完整页面，`app/api/screening`、`app/api/scores`、`app/api/sync/wind` 转发路由，`backend/routes/screening.py`，`lib/scoring.ts`、`lib/wind.ts`、`lib/score/`。
- 删除 backend 根目录运行残留：`batch_sync*` 日志、`restart_8005.log`、`generated_reports/`、`init_system.py`、`check_progress.py`、`test_vector_db.py`、`final_report.md`、`VECTOR_DB_SETUP.md`。
- 归档一代/二代文档至 `docs/history/`：PROGRESS、CHANGELOG(旧)、ARCHITECTURE(旧)、DEPLOYMENT、DOCKER、FAQ、FINAL_SUMMARY、PHASE4/5_SUMMARY、FIXES_SUMMARY、PROJECT_COMPLETE、SUMMARY。

### Changed

- 工作区壳「数据与方法」入口与基金详情净值刷新指引从 `/sync` 改指 `/evidence-coverage`（数据健康页承接调度 runbook 与待确认计数）。
- 旧路由（investor-selection / sales-rules / alerts / pools / rankings / overview）保留薄重定向页，历史 AI 分析报告中的旧链接经 `canonicalResearchHref` 映射到新研究平台页面。
- 更新静态 smoke 断言以匹配页面删除后的现实；修复 `professional_fund_research_architecture_smoke` 中断言 AppNavigation 的历史失效（layout 已使用 FundWorkspaceShell）。
- 重写 `ARCHITECTURE.md` 为当前主干架构；更新 `README.md` 移除 `frontend/` 迁移参考说明。

### Preserved — 前代有效资产

- 二代语义搜索链路（Qdrant + SentenceTransformer 懒加载 + warmup 端点）、Mongo AI 分析历史（含降级）、Redis 缓存回退、`backend/scripts/start_backend.sh` 解释器选择。
- 一代评分引擎 `scoring_engine`（AI 分析内部使用，不对外输出跨类别综合评分）。
- 三代证据驱动核心与四代研究工作流闭环全部保留。

## [1.0.0] - 2026-04-18

见 `docs/history/CHANGELOG.md`。
