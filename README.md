# 选基助手

面向普通用户的基金浏览、分类、评价、归因和候选推荐工具，也是 Newma Desk 的基金研究模组。

## 核心功能

1. 基金数据库：同步基金档案、净值、指标、经理和持仓。
2. 找基金：搜索基金、查看净值曲线、同类评价和多基金比较。
3. 调研库：连接本地纪要文件夹，按基金经理归档并提取可引用标签。
4. 综合基金数据库：合并基础数据、同类评价、纪要标签和数据质量。
5. 业绩归因：Barra 风格/风险暴露、Brinson 行业归因，以及明确标注的净值行为补充解释。
6. AI 分析：用户现场运行，读取评价、归因和纪要，保存分析历史。
7. 标签推荐：按类别和风格返回不超过十只候选基金。

不包含交易执行、购买金额、个人适当性、观察池晋级和投资决策。

LLM 不可用时，AI 分析只生成基于真实评价、归因和纪要的规则化摘要；调研库不会把普通关键词冒充已确认风格。

## 唯一运行入口

- 前端：仓库根目录 Next.js，`http://127.0.0.1:3000`
- 后端：`backend/main.py`，`http://127.0.0.1:8005`
- 后端健康检查：`GET /api/health`
- Newma Desk 发现文件：`GET /.well-known/newma-desk-suite.json`

`frontend/` 是迁移前的旧独立前端，只保留作代码迁移参考，不再作为开发或部署入口。

## 本地启动

环境要求：Node.js 20+、Python 3.11+、PostgreSQL。

```bash
# 1. 启动并初始化本地 PostgreSQL
./scripts/start-local-postgres.sh

# 2. 启动 FastAPI
./backend/scripts/start_backend.sh

# 3. 另开终端启动正式前端
npm install
npm run dev
```

已有真实基金基础数据后，生成标准分类和同类评价样本：

```bash
./scripts/update_fund_classification.sh --apply
./scripts/update_fund_ranking_metrics.sh --peer-evaluation-coverage --limit 100
```

`start-local-postgres.sh` 默认不导入演示基金；只有显式设置 `SEED_COMPLETION_SAMPLE=1` 才导入验收样本。

打开：

- 找基金：`http://127.0.0.1:3000/discover`
- AI 分析：`http://127.0.0.1:3000/analysis`
- 业绩归因：`http://127.0.0.1:3000/analysis/advanced`
- 标签推荐：`http://127.0.0.1:3000/recommendations`

## Docker

```bash
docker compose up -d --build
```

Docker 使用仓库根目录正式前端和 `backend/main.py`，不再构建旧 `frontend/`。

## 数据原则

- 基金必须先分类，再做同类评价。
- 不用短期收益冠军直接推荐。
- 不用模拟数据或名称猜测冒充持仓、风格和归因。
- Barra 因子库未接入时，只展示持仓行业暴露。
- Brinson 持仓披露不足时，明确显示覆盖率和残差。
- 净值行为解释不得标记为 Barra 或 Brinson。

## 主要验证

```bash
npm run build
PYTHONPATH=backend python3 -m py_compile backend/main.py backend/services/performance_attribution_service.py
curl http://127.0.0.1:8005/api/health
```

产品范围见 [CONTEXT.md](./CONTEXT.md) 和 [ADR-0002](./docs/adr/0002-simple-fund-selection-product-scope.md)。
