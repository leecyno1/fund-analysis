# 基金经理评价分析系统

一个面向基金研究的基金筛选、基金分析和基金经理评价系统，集成 Wind API 数据采集、调研报告管理、研究备忘录生成和多维度评分功能。

## ✨ 核心功能

### 1. 全市场基金浏览器
- 🌐 全市场基金搜索、筛选、排序
- 🧭 列表 / 卡片双视图切换
- ⚡ 快捷筛选与核心指标概览
- ➕ 从市场页直接加入候选池

### 2. 基金池研究工作流
- 🗂️ 候选 / 观察 / 核心 / 淘汰状态流转
- 📝 最新结论、复查日期、风险备注维护
- 🧾 证据 JSON 沉淀与回看
- 🔁 面向持续跟踪的研究维护界面

### 3. 预警中心
- 🚨 预警规则创建、启停、删除
- 📡 手动触发扫描
- 📬 预警事件查看、过滤、处理
- 🔍 支撑重点基金复核节奏

### 4. 调研报告与基金研究
- 📄 调研报告管理与检索
- 🤖 基金 / 基金经理 / 对比研究报告
- 🧠 可信度、证据数、报告数摘要
- 📋 面向研究复核的内容沉淀

### 5. 基础数据与评分能力
- 📊 基金与基金经理基础信息管理
- 🔄 数据同步与快照体系
- 🏆 多维评分与筛选框架
- 📈 为研究结论提供数据底座

## 🚀 快速开始

### 方式一：一键启动（推荐）

```bash
# 克隆项目
git clone <your-repo-url>
cd fund-analysis

# 运行快速启动脚本
./scripts/quick-start.sh
```

脚本会自动：
- 检查环境依赖
- 创建环境变量文件
- 安装依赖
- 初始化数据库
- 启动应用

### 方式二：Docker 部署

```bash
# 1. 配置环境变量
cp .env.example .env.local
# 编辑 .env.local 填入 API Keys

# 2. 启动所有服务
docker-compose up -d

# 3. 运行数据库迁移
docker-compose exec app npx prisma migrate deploy

# 4. 访问应用
# http://localhost:3000
```

详见 [Docker 部署指南](./DOCKER.md)

### 方式三：手动安装

#### 环境要求
- Node.js 18+
- PostgreSQL 15+ (with pgvector)
- Python 3.8+
- Wind 终端 (可选)

#### 安装步骤

1. **克隆项目**
```bash
git clone <your-repo-url>
cd fund-analysis
```

2. **安装依赖**
```bash
npm install
```

3. **配置环境变量**
```bash
cp .env.example .env.local
# 编辑 .env.local 填入实际配置
```

4. **启动数据库**
```bash
./scripts/start-db.sh
```

如果 Docker 数据卷或端口映射异常，可以改用本机 PostgreSQL 兜底：
```bash
./scripts/start-local-postgres.sh
export DATABASE_URL="postgresql://postgres:fundanalysis2024@localhost:5432/fund_analysis"
```

5. **运行数据库迁移**
```bash
npx prisma migrate dev
npx prisma generate
```

6. **启动应用**
```bash
# 终端 1: Next.js
npm run dev

# 终端 2: Wind 服务
cd backend/wind_service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

7. **访问应用**
```
http://localhost:3000
```

## ✅ 基金研究模块验收

本项目当前聚焦于基金筛选、基金分析和基金经理评价。启动本地应用后，可用一条命令跑完整验收烟测，避免只看演示页面却没有真实功能闭环。

```bash
# 默认验收 http://127.0.0.1:3001
npm run smoke:fund-research

# 如果本地端口不同
FRONTEND_BASE_URL=http://127.0.0.1:3000 npm run smoke:fund-research
```

如需验收“真实数据进入本地 + 生成一组基金研究报告”的闭环：

```bash
# 默认从本地最近基金中取 3 只，逐只同步 Tushare 数据并保存基金研究报告
npm run research:real-data-report

# 指定基金代码和数量
npm run research:real-data-report -- 260104.OF 519674.OF --limit=2

# 如果端口不同
BACKEND_API_URL=http://127.0.0.1:8005 FRONTEND_BASE_URL=http://127.0.0.1:3000 npm run research:real-data-report
```

该命令会检查后端不是 mock 数据源，调用 Tushare 同步到本地 PostgreSQL，再生成并保存基金研究报告，最后确认报告能从前端报告详情读取到。

验收覆盖范围：
- 全市场基金浏览器：搜索、筛选、排序和加入基金池入口
- 投资者筛选页：基金池状态、严格销售规则模式和缺口统计
- 基金详情页：核心指标、分析入口、销售规则硬缺口扫描
- 基金对比与购买前模拟：只保留基金研究相关判断，不耦合组合配置或交易执行
- 基金池门禁：销售规则硬缺口未补齐时，禁止进入购买候选或核心状态
- 销售规则补证：候选和观察补证范围同步检查，拒绝过薄或伪造式证据
- 报告门禁：硬缺口未清除前，不生成或保存正式购买前、候选池、对比报告

验收前请确保：
- Next.js 本地服务正在运行
- 数据库已迁移并有可查询基金数据
- `DATABASE_URL` 指向当前本地验收数据库
- 如需接入 Tushare、Wind 或大模型服务，请只通过环境变量配置密钥，不要写入代码或文档

## 📖 文档

- [开发进度](./PROGRESS.md) - 详细的开发进度和功能清单
- [部署文档](./DEPLOYMENT.md) - 完整的部署指南
- [Docker 部署](./DOCKER.md) - Docker 容器化部署
- [常见问题](./FAQ.md) - FAQ 和故障排查
- [贡献指南](./CONTRIBUTING.md) - 如何贡献代码
- [更新日志](./CHANGELOG.md) - 版本更新记录
- [最终总结](./FINAL_SUMMARY.md) - 项目完整总结
- [Phase 4 总结](./PHASE4_SUMMARY.md) - 基金研究引擎
- [Phase 5 总结](./PHASE5_SUMMARY.md) - 评分筛选系统

## 🛠️ 技术栈

### 前端
- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript
- **样式**: TailwindCSS
- **图表**: Recharts
- **图标**: Lucide React

### 后端
- **API**: Next.js API Routes
- **ORM**: Prisma
- **数据库**: PostgreSQL 15 + pgvector
- **Python**: FastAPI (Wind 服务)

### AI
- **分析**: Claude 3.5 Sonnet
- **向量**: OpenAI Embeddings
- **流式**: Server-Sent Events

## 📊 项目统计

- **代码行数**: 12,500+
- **前端页面**: 25+
- **API 端点**: 30+
- **React 组件**: 40+
- **完成度**: 85%

## 🎯 核心特性

### 1. 流式响应
使用 Server-Sent Events 实现研究报告的实时流式生成，用户可以看到逐字生成的过程。

### 2. 语义搜索
基于 pgvector 和 OpenAI Embeddings 实现调研报告的语义搜索，支持自然语言查询。

### 3. 科学评分
多维度评分算法，综合考虑业绩、风险、稳定性和管理能力，自动生成评级。

### 4. 智能提示词
自动构建分析提示词，整合基金数据、业绩指标、风险指标和调研报告。

## 📝 环境变量

```env
# 数据库
DATABASE_URL="postgresql://user:pass@localhost:5432/fund_analysis"

# AI API
ANTHROPIC_API_KEY="sk-ant-xxx"
OPENAI_API_KEY="sk-xxx"

# Wind 服务
WIND_SERVICE_URL="http://localhost:8000"
```

## 🔧 开发

### 运行测试
```bash
npm test
```

### 构建生产版本
```bash
npm run build
npm start
```

### 数据库管理
```bash
# 查看数据库
npx prisma studio

# 重置数据库
npx prisma migrate reset

# 生成客户端
npx prisma generate
```

## 📦 部署

详见 [部署文档](./DEPLOYMENT.md)

### 使用 PM2
```bash
pm2 start npm --name "fund-analysis" -- start
pm2 save
```

### 使用 Docker
```bash
docker-compose up -d
```

## 🐛 故障排查

### 数据库连接失败
```bash
# 检查 PostgreSQL 状态
sudo systemctl status postgresql

# 测试连接
psql $DATABASE_URL
```

### Prisma 迁移失败
```bash
# 重置数据库
npx prisma migrate reset

# 手动修复
npx prisma migrate resolve --applied <migration-name>
```

更多问题请查看 [部署文档](./DEPLOYMENT.md#故障排查)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- Anthropic Claude
- OpenAI
- Next.js
- Prisma
- PostgreSQL
- Wind

---

**开发时间**: 2024-04-17 至 2024-04-18  
**开发者**: Claude (AI Assistant)  
**版本**: 1.0.0
