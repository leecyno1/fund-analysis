import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  const fullPath = join(root, relativePath)
  if (!existsSync(fullPath)) throw new Error(`Missing required file: ${relativePath}`)
  return readFileSync(fullPath, 'utf8')
}

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) throw new Error(`${label} missing: ${expected}`)
}

const schema = read('prisma/schema.prisma')
const migrationDir = 'prisma/migrations/20260819000100_portfolio_construction'
if (!existsSync(join(root, migrationDir, 'migration.sql'))) throw new Error('portfolio migration sql missing')
const service = read('backend/services/portfolio_service.py')
const repo = read('backend/repositories/portfolio_repo.py')
const routes = read('backend/routes/portfolio.py')
const mainPy = read('backend/main.py')
const page = read('app/(dashboard)/portfolio/page.tsx')
const client = read('app/(dashboard)/portfolio/PortfolioClient.tsx')
const navigation = read('components/shell/fund-workspace-navigation.ts')

// 数据模型四表齐全（组合/目标配置/持仓/画像快照）
assertIncludes(schema, 'model Portfolio {', 'portfolio model')
assertIncludes(schema, 'model PortfolioTarget {', 'portfolio target model')
assertIncludes(schema, 'model PortfolioHolding {', 'portfolio holding model')
assertIncludes(schema, 'model PortfolioSnapshot {', 'portfolio snapshot model')

// 边界与研究口径：准入推荐就绪、单只上限、权重合计、不做交易
assertIncludes(service, 'MAX_SINGLE_WEIGHT = 0.40', 'single fund weight cap')
assertIncludes(service, '权重合计必须为 100%', 'weight sum validation')
assertIncludes(service, '不满足推荐就绪口径', 'admission requires recommendation-ready metric panel')
assertIncludes(service, '不执行交易、不做适当性判断、不生成销售规则', 'portfolio research boundary')
assertIncludes(service, '穿透只基于公开披露持仓与历史净值', 'analysis evidence boundary')

// 权重来源仅等权/自定义（不做风险平价）
assertIncludes(routes, "source: str = Field(default=\"custom\")", 'custom weight source')
assertIncludes(routes, '/weights/equal', 'equal weight endpoint')
assertIncludes(repo, 'VALID_WEIGHT_SOURCES = {"equal", "custom"}', 'weight sources limited to equal/custom')

// 穿透复用现有证据服务
assertIncludes(service, 'from services.fund_holding_similarity_service import FundHoldingSimilarityService', 'overlap reuses holding similarity service')
assertIncludes(service, 'CORRELATION_MIN_DAYS = 60', 'correlation minimum overlap gate')
assertIncludes(service, 'coverage_note', 'style aggregate discloses coverage residual')

// 路由注册与前端接线
assertIncludes(mainPy, 'app.include_router(portfolio.router', 'backend registers portfolio router')
assertIncludes(client, 'api/portfolios', 'frontend calls portfolio API')
assertIncludes(navigation, "href: '/portfolio'", 'workspace navigation exposes portfolio entry')

console.log('OK portfolio construction keeps research boundary: admission gate, equal/custom weights only, overlap/style/correlation penetration with coverage disclosure')
