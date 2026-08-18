# 基金筛选评价系统 - 系统架构文档

> 版本: 2.0.0 | 更新日期: 2026/04/23 | 数据源: Tushare (Token: ccff9ae1a...2177)

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [技术栈](#2-技术栈)
3. [架构原则](#3-架构原则)
4. [目录结构](#4-目录结构)
5. [核心模块设计](#5-核心模块设计)
6. [数据流设计](#6-数据流设计)
7. [API 网关设计](#7-api-网关设计)
8. [缓存策略](#8-缓存策略)
9. [数据库设计](#9-数据库设计)
10. [容错与降级](#10-容错与降级)
11. [部署架构](#11-部署架构)
12. [开发规范](#12-开发规范)

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      用户层 (Browser)                        │
└────────────────────────────┬────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Next.js Frontend (3000)                   │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌────────────┐ │
│  │  Dashboard │  │ Fund Pages │  │ Manager Pages │ │ Research Library │ │
│  └─────────┘  └──────────┘  └─────────┘  └────────────┘ │
│                                                             │
│  ┌────────────────── API Proxy ──────────────────────────┐ │
│  │   /api/[...path]  ─────►  Backend:8005/api/...        │ │
│  └───────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                           │ HTTP (内部网络)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (8005)                    │
│                                                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Funds API │  │Managers API│  │Scoring API│  │ Barra API │ │
│  └──────────┘  └───────────┘  └──────────┘  └──────────┘ │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Brinson  │  │Reports API│  │Research API│  │Export API │ │
│  └──────────┘  └───────────┘  └──────────┘  └──────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Service Registry (全局单例)              │  │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────────┐ │  │
│  │  │TushareData │  │FundScoring  │  │MongoDB Client │ │  │
│  │  │  Service   │  │  Engine     │  │              │ │  │
│  │  └────────────┘  └─────────────┘  └──────────────┘ │  │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────────┐ │  │
│  │  │Redis/Memory│  │   AI Report │  │  Cache Service│ │  │
│  │  │   Cache    │  │   Generator │  │              │ │  │
│  │  └────────────┘  └─────────────┘  └──────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐   ┌──────────────┐   ┌──────────┐
    │ Tushare  │   │ PostgreSQL   │   │  Redis   │
    │  Cloud   │   │  (fund_data) │   │ (cache)  │
    └──────────┘   │  ┌─────────┐ │   └──────────┘
                   │  │ MongoDB  │ │
                   │  │(reports) │ │
                   │  └─────────┘ │
                   └──────────────┘
```

---

## 2. 技术栈

### 前端
| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | Next.js (App Router) | 14+ | React SSR 框架 |
| UI 库 | TailwindCSS + 自定义组件 | — | 样式系统 |
| 图表 | Recharts | 2.10+ | 数据可视化 |
| 图标 | Lucide React | — | SVG 图标库 |
| 状态管理 | React Context + SWR | — | 全局状态 + 数据获取 |

### 后端
| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | FastAPI | 0.110+ | REST API |
| 数据源 | Tushare Pro | 1.4+ | 基金/经理数据 |
| 数据库 | PostgreSQL | 15+ | 结构化数据持久化 |
| 文档库 | MongoDB | 6+ | 调研报告存储 |
| 缓存 | Redis (开发: 内存) | 7+ | 多层缓存 |
| AI | Anthropic Claude | — | 报告生成 |
| ORM | SQLAlchemy 2.0 | — | PostgreSQL 访问 |

### DevOps
| 组件 | 技术 | 用途 |
|------|------|------|
| 容器化 | Docker + Docker Compose | 一键部署 |
| 初始化 | `init_system.py` | 数据同步/预热 |

---

## 3. 架构原则

### 3.1 数据源可插拔
```
WindDataService / TushareDataService 实现统一接口
通过 DATA_SOURCE=wind|tushare 环境变量切换
```
- 所有数据服务实现相同的公开方法（`get_fund_info`, `get_fund_nav`, `get_manager_info` 等）
- 切换数据源时无需修改业务代码
- Mock 模式保证开发环境可在无外部依赖时运行

### 3.2 分层缓存
```
请求 → Redis → 内存缓存 → 数据源
         ↓         ↓         ↓
       (命中)   (命中)   (从 Tushare 拉取)
```
- 缓存键统一通过 `CacheKey` 类管理
- TTL 按数据类型分级（净值 1h、业绩 15m、列表 5m）
- 自动降级：Redis 不可用 → 内存 → 空缓存

### 3.3 单例注册表
```
service_registry.py 解决模块循环引用
所有服务通过 get_xxx() 函数获取单例
```

### 3.4 数据库双写
```
查询: PostgreSQL (快) → 兜底: Tushare (全)
写入: PostgreSQL (持久化) + Redis (加速)
```

---

## 4. 目录结构

```
fund-analysis/
│
├── frontend/                          # Next.js 前端
│   ├── src/
│   │   ├── app/                       # App Router 页面
│   │   │   ├── api/[...path]/         # API 代理路由 ★
│   │   │   ├── funds/                 # 基金详情页
│   │   │   ├── managers/              # 基金经理页
│   │   │   ├── screening/            # 筛选页
│   │   │   ├── research/              # 调研报告库
│   │   │   ├── barra/                 # Barra 风险分析
│   │   │   ├── brinson/               # Brinson 归因
│   │   │   ├── reports/               # AI 报告页
│   │   │   ├── layout.tsx             # 根布局
│   │   │   └── page.tsx               # Dashboard 首页
│   │   ├── components/                # React 组件
│   │   │   ├── common/                # 通用组件
│   │   │   ├── layout/                # 布局组件
│   │   │   ├── profile/               # 画像组件
│   │   │   ├── barra/                 # Barra 组件
│   │   │   ├── brinson/               # Brinson 组件
│   │   │   └── scoring/               # 评分组件
│   │   └── lib/
│   │       ├── api.ts                 # API 客户端 ★
│   │       └── utils.ts               # 工具函数
│   ├── Dockerfile                     # 前端容器
│   ├── next.config.js                  # Next.js 配置 ★
│   └── package.json
│
├── backend/                           # FastAPI 后端
│   ├── main.py                        # 应用入口 ★
│   ├── .env                           # 环境变量 ★
│   ├── service_registry.py            # 服务注册表 ★
│   ├── database.py                    # 数据库初始化 ★
│   ├── init_system.py                 # 初始化工具 ★
│   │
│   ├── routes/                        # API 路由
│   │   ├── funds.py                   # 基金 API ★
│   │   ├── managers.py                # 经理 API
│   │   ├── scoring.py                 # 评分 API
│   │   ├── reports.py                 # AI 报告 API
│   │   ├── research_reports.py        # 调研报告 API
│   │   ├── screening.py               # 筛选 API
│   │   ├── barra.py                   # Barra 风险
│   │   ├── brinson.py                 # Brinson 归因
│   │   ├── export.py                  # 数据导出
│   │   └── data_sync.py               # 数据同步
│   │
│   ├── services/                      # 业务逻辑层
│   │   ├── tushare_service.py         # Tushare 数据服务 ★
│   │   ├── wind_service.py            # Wind 数据服务
│   │   ├── scoring_engine.py          # 评分引擎
│   │   ├── ai_report.py               # AI 报告生成
│   │   ├── cache_service.py           # 多层缓存 ★
│   │   ├── cache.py                   # 缓存装饰器
│   │   ├── search_service.py           # 搜索服务
│   │   └── profile_extractor.py       # 画像提取
│   │
│   ├── repositories/                 # 数据访问层
│   │   ├── fund_repo.py               # 基金 Repository
│   │   ├── manager_repo.py            # 经理 Repository
│   │   ├── holding_repo.py            # 持仓 Repository
│   │   ├── nav_repo.py                # 净值 Repository
│   │   └── factor_repo.py            # 因子 Repository
│   │
│   ├── models/                        # Pydantic 模型
│   ├── schemas/                       # 请求/响应模型
│   └── Dockerfile                     # 后端容器
│
├── docker-compose.yml                 # Docker 编排 ★
├── prisma/                            # Prisma Schema (备选)
│   └── schema.prisma
└── ARCHITECTURE.md                    # 本文档
```

---

## 5. 核心模块设计

### 5.1 Tushare 数据服务 (`tushare_service.py`)

```python
class TushareDataService:
    def get_fund_info(wind_code: str) -> Dict       # 基金基本信息
    def get_fund_list(fund_type, page, page_size)   # 基金列表
    def get_fund_nav(wind_code, start, end)          # 净值序列
    def get_fund_performance(wind_code)              # 业绩指标
    def get_fund_risk_metrics(wind_code)             # 风险指标
    def get_fund_holdings(wind_code, quarter)        # 持仓数据
    def get_fund_style(wind_code)                    # 风格因子
    def get_manager_info(manager_id)                 # 经理信息
    def get_manager_funds(manager_id)                # 经理旗下基金
```

**Mock 模式**：Tushare 不可用或未安装时使用确定性 hash 生成 mock 数据，保证开发环境可运行。

### 5.2 评分引擎 (`scoring_engine.py`)

```python
class FundScoringEngine:
    def score_fund(performance, risk_metrics, style) -> FundScoring
    def score_manager(manager_data, reports) -> ManagerScoring
    def get_overall_grade(score) -> str  # A/B/C/D/E
    def get_dimension_scores(score) -> Dict[str, float]
```

评分维度：
- **收益维度 (40%)**: 年化收益 1Y/3Y、Calmar 比率
- **风险维度 (30%)**: 最大回撤、波动率、VaR
- **风险调整收益 (20%)**: 夏普比率、索提诺比率、信息比率
- **定性维度 (10%)**: 风格稳定性、经理调研评分

### 5.3 缓存服务 (`cache_service.py`)

三层缓存后端：
```
RedisCache (生产) → MemoryCache (开发) → NullCache (测试)
```

关键缓存键：
```
fund:detail:{wind_code}      TTL=10min   基金详情
fund:list:{type}:{page}     TTL=5min    基金列表
fund:perf:{wind_code}       TTL=30min   业绩数据
fund:risk:{wind_code}       TTL=30min   风险指标
holdings:{wind_code}:{q}    TTL=60min   持仓数据
nav:{wind_code}:{s}:{e}     TTL=60min   净值序列
manager:profile:{id}        TTL=30min   经理画像
```

---

## 6. 数据流设计

### 6.1 基金列表查询流程
```
浏览器 → GET /api/funds/?page=1&fund_type=stock
        ↓
  Next.js API Proxy [GET /api/funds/]
        ↓ 拼接 URL: BACKEND_URL/api/funds/?page=1
  FastAPI /api/funds/
        ↓
  检查 PostgreSQL (funds 表)
        ├─ 有数据 → 计算评分 → 返回
        └─ 无数据 → Tushare 查询
                   ├─ 获取列表
                   ├─ 遍历获取详情/业绩/风险
                   ├─ 并行写入 PostgreSQL
                   └─ 返回
        ↓
  Next.js 响应
        ↓
  前端 SWR 缓存 (stale-while-revalidate)
```

### 6.2 AI 报告生成流程
```
POST /api/reports/fund/{wind_code}
        ↓
  1. 获取基金详情 (from 缓存/数据库)
  2. 获取持仓数据
  3. 获取经理画像
  4. RAG: 检索相似调研报告 (top-K)
  5. 构造 prompt (基金数据 + 持仓 + 风格 + 调研报告)
  6. 调用 Claude API
  7. 解析响应 → 结构化报告
  8. 存储到 PostgreSQL
  9. 缓存报告
  10. 返回 report_id
```

---

## 7. API 网关设计

### 7.1 Next.js API Proxy

**问题背景**: Next.js 独立部署时 API 路由 `app/api/[...path]` 无法通过 rewrites 代理到后端（独立模式下 rewrites 不生效）。

**解决方案**: 显式代理路由 `[...path]` 转发所有请求。

```typescript
// 前端路由: GET /api/funds/?page=1
// 代理到:  http://127.0.0.1:8005/api/funds/?page=1

const BACKEND_URL = 'http://127.0.0.1:8005/api'
const path = request.nextUrl.pathname
  .replace(/^\/api/, '')          // /api/funds/ → /funds/
  .replace(/^\/+/, '/')            // 去除多余斜杠
const cleanPath = path.endsWith('/') ? path.slice(0, -1) : path
const url = `${BACKEND_URL}${cleanPath}?${searchParams}`
```

### 7.2 API 版本管理

| 前缀 | 版本 | 说明 |
|------|------|------|
| `/api/funds/` | v1 | 基金数据 |
| `/api/managers/` | v1 | 基金经理 |
| `/api/scoring/` | v1 | 评分系统 |
| `/api/barra/` | v1 | Barra 风险 |
| `/api/reports/` | v1 | AI 报告 |

---

## 8. 缓存策略

### 8.1 缓存穿透防护
```python
# 使用空值缓存防止缓存穿透
CACHE_MISS_TTL = 60  # 未命中时缓存"无数据"状态 60 秒
```

### 8.2 缓存雪崩防护
```python
# TTL 随机抖动 ±10%
actual_ttl = int(ttl * random.uniform(0.9, 1.1))
```

### 8.3 批量预热
```bash
# 启动时预热高频访问基金缓存
python init_system.py --warm-cache --top-n 50
```

---

## 9. 数据库设计

### 9.1 PostgreSQL 表 (核心数据)

```
funds                    基金基础信息
fund_nav                 基金净值历史
managers                 基金经理表
scores                   评分记录
holdings                 基金持仓 (季度)
factor_exposures         Barra 因子暴露
performance_attributions Brinson 归因
manager_profiles         经理画像
research_reports         调研报告
screening_criteria       筛选条件
ai_analysis_reports      AI 分析报告
```

### 9.2 MongoDB 集合 (文档数据)

```
research_reports         调研纪要原文 (全文检索)
interview_transcripts    访谈记录
manager_dossiers         经理档案袋 (附件)
```

### 9.3 索引策略

```sql
-- 高频查询字段
CREATE INDEX idx_funds_wind_code ON funds(wind_code);
CREATE INDEX idx_funds_name ON funds(name);              -- ILIKE 搜索
CREATE INDEX idx_funds_type ON funds(type);             -- 类型过滤
CREATE INDEX idx_nav_wind_date ON fund_nav(wind_code, trade_date);
CREATE INDEX idx_scores_target ON scores(target_type, target_id);
CREATE INDEX idx_holdings_wind_quarter ON holdings(wind_code, quarter);
```

---

## 10. 容错与降级

### 10.1 降级策略

| 组件故障 | 影响 | 降级行为 |
|---------|------|---------|
| Tushare 不可用 | 数据拉取失败 | Mock 数据 + 警告日志 |
| PostgreSQL 不可用 | 持久化失败 | 内存缓存 + 警告日志 |
| Redis 不可用 | 缓存失效 | 降级到 MemoryCache → NullCache |
| Claude API 不可用 | AI 报告不可生成 | 返回错误 + 模板报告 |
| MongoDB 不可用 | 调研报告不可查 | 返回空列表 |

### 10.2 超时配置

```python
# Tushare 单次请求超时
TUSHARE_TIMEOUT = 10  # 秒

# Claude API 超时
AI_TIMEOUT = 60  # 秒

# 数据库连接超时
DB_CONNECT_TIMEOUT = 5  # 秒
```

### 10.3 重试机制

```python
# 指数退避重试 (仅 GET 请求)
def retry_request(url, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return requests.get(url, timeout=10)
        except (TimeoutError, ConnectionError) as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

---

## 11. 部署架构

### 11.1 开发环境
```
本地:  next dev (3000)  +  uvicorn main:app (8005)
```

### 11.2 Docker Compose (生产)
```yaml
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
    environment:
      - NEXT_PUBLIC_API_URL=/api

  backend:
    build: ./backend
    ports: ["8005:8005"]
    depends_on: [postgres, redis, mongo]
    environment:
      - DATABASE_URL=postgresql://postgres:fundanalysis2024@postgres:5432/fund_analysis
      - REDIS_URL=redis://redis:6379/0
      - TUSHARE_TOKEN=${TUSHARE_TOKEN}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

  postgres:
    image: postgres:15-alpine
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine

  mongo:
    image: mongo:6
```

---

## 12. 开发规范

### 12.1 API 路由规范

```python
# ✓ 正确
@router.get("/")
@router.get("/{wind_code}")
@router.post("/batch-query")

# ✗ 错误
@router.get("")          # 缺少 /
@router.post("/")         # 不应 POST 到列表
```

### 12.2 错误处理规范

```python
# 统一错误格式
{
    "detail": "错误描述",
    "code": "FUND_NOT_FOUND",  # 可选: 业务错误码
    "suggestion": "尝试使用基金代码"  # 可选: 建议
}

# FastAPI HTTPException
raise HTTPException(status_code=404, detail="基金不存在")
```

### 12.3 日志规范

```python
# INFO: 正常流程关键节点
logger.info(f"Fund synced: {wind_code}")

# WARNING: 可恢复的错误（降级生效）
logger.warning(f"DB unavailable, using cache: {e}")

# ERROR: 需要处理的错误
logger.error(f"Fund sync failed for {wind_code}: {e}")

# DEBUG: 开发调试
logger.debug(f"[CACHE HIT] {cache_key}")
```

### 12.4 数据校验

```python
from pydantic import BaseModel, Field, validator

class FundNavRequest(BaseModel):
    wind_code: str = Field(..., pattern=r"^\d{6}\.OF$")
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")

    @validator('end_date')
    def end_after_start(cls, v, values):
        if v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
```

---

## 附录: 关键文件清单

| 文件 | 用途 | 关键配置 |
|------|------|---------|
| `frontend/next.config.js` | Next.js 配置 | `trailingSlash: true` |
| `frontend/src/app/api/[...path]/route.ts` | API 代理 | `BACKEND_URL` 拼接 |
| `backend/main.py` | FastAPI 入口 | 路由注册、服务初始化 |
| `backend/.env` | 环境变量 | `TUSHARE_TOKEN` 等 |
| `backend/service_registry.py` | 服务单例 | `DATA_SOURCE` 切换 |
| `backend/services/tushare_service.py` | Tushare 客户端 | Token + Mock 模式 |
| `backend/services/cache_service.py` | 多层缓存 | Redis/Memory/Null |
| `backend/database.py` | PostgreSQL 初始化 | 10+ 表 + 索引 |
| `backend/init_system.py` | 系统初始化 | `--full` 一键启动 |
| `docker-compose.yml` | 容器编排 | 5 服务 |

---

*文档版本: 2.0.0 | 维护者: 开发团队 | 更新: 2026/04/23*
