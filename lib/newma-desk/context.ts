import {
  PROFESSIONAL_METHODOLOGY_VERSION,
  professionalResearchStages,
  type DailyResearchCockpitSnapshot,
} from '@/lib/fund-research'
import type { NewmaDeskPageContext } from './bridge'

export const FUND_RESEARCH_WORKSPACE_IDS = [
  'overview',
  'selection',
  'due-diligence',
  'peer-comparison',
  'monitoring',
  'methodology',
] as const

export type FundResearchWorkspaceId = (typeof FUND_RESEARCH_WORKSPACE_IDS)[number]

export type FundSelection = {
  symbol: string
  name?: string
  assetType: 'fund' | 'etf'
}

export type FundResearchWorkspace = {
  id: FundResearchWorkspaceId
  modId: string
  title: string
  shortTitle: string
  purpose: string
  primaryHref: string
  primaryLabel: string
  stageIds: Array<(typeof professionalResearchStages)[number]['id']>
  actions: Array<{ id: string; label: string; inputSchema?: unknown }>
}

const fundSelectionSchema = {
  type: 'object',
  properties: {
    symbol: { type: 'string', minLength: 1, maxLength: 24 },
    name: { type: 'string', maxLength: 80 },
    assetType: { enum: ['fund', 'etf'] },
  },
  additionalProperties: false,
}

export const fundResearchWorkspaces: FundResearchWorkspace[] = [
  {
    id: 'overview',
    modId: 'fund-research-overview',
    title: '每日基金研究驾驶舱',
    shortTitle: '每日驾驶舱',
    purpose: '把证据健康、研究对象、补证任务和复核事件压缩到一个日常工作入口；方法与结论仍由九段式研究内核负责。',
    primaryHref: '/market',
    primaryLabel: '选择研究对象',
    stageIds: professionalResearchStages.map((stage) => stage.id),
    actions: [
      { id: 'fund.research.explain', label: '解释当前研究状态', inputSchema: fundSelectionSchema },
      { id: 'fund.evidence.snapshot', label: '读取证据覆盖快照', inputSchema: fundSelectionSchema },
    ],
  },
  {
    id: 'selection',
    modId: 'fund-selection',
    title: '基金准入与初筛',
    shortTitle: '准入初筛',
    purpose: '先处理份额、生命周期、数据覆盖、同类和基准，再生成可进入尽调的研究清单。',
    primaryHref: '/market',
    primaryLabel: '打开全市场研究库',
    stageIds: ['universe-identity', 'evidence-quality', 'peer-benchmark', 'quantitative-evaluation'],
    actions: [
      { id: 'fund.universe.query', label: '查询研究范围' },
      { id: 'fund.research.explain', label: '解释准入门槛', inputSchema: fundSelectionSchema },
    ],
  },
  {
    id: 'due-diligence',
    modId: 'fund-due-diligence',
    title: '基金投资与运营尽调',
    shortTitle: '尽调工作台',
    purpose: '把 People、Process、Parent、Price、持仓行为、载体和运营完整性放在统一证据框架。',
    primaryHref: '/managers',
    primaryLabel: '进入经理与公司研究',
    stageIds: ['holdings-style', 'qualitative-due-diligence', 'decision-governance'],
    actions: [
      { id: 'fund.due-diligence.evaluate', label: '生成尽调问题清单', inputSchema: fundSelectionSchema },
      { id: 'fund.research.explain', label: '解释尽调反证', inputSchema: fundSelectionSchema },
    ],
  },
  {
    id: 'peer-comparison',
    modId: 'fund-peer-comparison',
    title: '同类组、基准与风格横评',
    shortTitle: '同类横评',
    purpose: '在可解释同类组和适配基准内比较滚动收益、风险、因子、风格与容量证据。',
    primaryHref: '/analysis/comparison',
    primaryLabel: '打开基金对比',
    stageIds: ['peer-benchmark', 'quantitative-evaluation', 'holdings-style'],
    actions: [
      { id: 'fund.peer.evaluate', label: '执行同类评价' },
      { id: 'fund.research.explain', label: '解释比较差异', inputSchema: fundSelectionSchema },
    ],
  },
  {
    id: 'monitoring',
    modId: 'fund-monitoring',
    title: '基金持续监控与复核',
    shortTitle: '监控复核',
    purpose: '用经理、持仓、风格、风险、费用和数据变化触发有原因、有期限的研究复核。',
    primaryHref: '/evidence-coverage?section=review-events',
    primaryLabel: '打开复核事件',
    stageIds: ['monitoring', 'decision-governance', 'methodology-audit'],
    actions: [
      { id: 'fund.monitoring.review', label: '创建复核任务', inputSchema: fundSelectionSchema },
      { id: 'fund.evidence.snapshot', label: '刷新证据快照', inputSchema: fundSelectionSchema },
    ],
  },
  {
    id: 'methodology',
    modId: 'fund-methodology',
    title: '基金研究方法论与审计',
    shortTitle: '方法论',
    purpose: '公开研究方法、引用来源、版本、硬门槛和现有能力映射，保证结论可复现。',
    primaryHref: '/evidence-coverage',
    primaryLabel: '查看证据台账',
    stageIds: ['methodology-audit'],
    actions: [
      { id: 'fund.methodology.audit', label: '审计当前方法版本' },
      { id: 'fund.research.explain', label: '解释方法论' },
    ],
  },
]

export function isFundResearchWorkspace(value: string): value is FundResearchWorkspaceId {
  return FUND_RESEARCH_WORKSPACE_IDS.includes(value as FundResearchWorkspaceId)
}

export function fundResearchWorkspaceById(workspaceId: FundResearchWorkspaceId) {
  return fundResearchWorkspaces.find((workspace) => workspace.id === workspaceId)!
}

export function buildFundResearchPageContext(input: {
  workspace: FundResearchWorkspace
  selection?: FundSelection | null
  filters?: Record<string, unknown>
  asOf?: string
  tasks?: NewmaDeskPageContext['tasks']
  cockpit?: DailyResearchCockpitSnapshot | null
}): NewmaDeskPageContext {
  const stages = input.workspace.stageIds
    .map((stageId) => professionalResearchStages.find((stage) => stage.id === stageId))
    .filter((stage): stage is (typeof professionalResearchStages)[number] => Boolean(stage))

  const cockpit = input.workspace.id === 'overview' ? input.cockpit : null
  const visibleBlocks = cockpit
    ? [
        { id: 'daily-research-cockpit', type: 'summary', title: '今日研究判断' },
        { id: 'daily-research-metrics', type: 'metrics', title: '研究与数据状态' },
        { id: 'selected-research-object', type: 'summary', title: '当前研究对象' },
        { id: 'daily-research-queue', type: 'table', title: '今日研究队列' },
        { id: 'evidence-source-health', type: 'table', title: '证据与数据健康' },
        { id: 'review-events', type: 'table', title: '复核与反转信号' },
        { id: 'professional-workflow', type: 'table', title: '九段式研究内核' },
      ]
    : [
        { id: 'research-position', type: 'summary', title: '当前研究位置' },
        { id: 'professional-workflow', type: 'table', title: '专业研究流程' },
        { id: 'decision-policy', type: 'methodology', title: '门槛与分柱判断' },
        { id: 'source-foundation', type: 'sources', title: '公开方法来源' },
      ]
  const cockpitFreshness = cockpit?.status === 'unavailable'
    ? 'unknown'
    : cockpit?.sources.some((source) => source.status === 'stale')
      ? 'stale'
      : cockpit ? 'fresh' : undefined
  const cockpitTasks = cockpit?.tasks.map((task) => ({
    id: task.id,
    status: task.tone === 'danger' ? 'blocked' : 'pending',
    actionId: task.actionId,
  })) ?? []

  return {
    view: {
      id: input.workspace.modId,
      title: input.workspace.title,
    },
    visibleBlocks,
    selection: input.selection ? {
      symbol: input.selection.symbol,
      name: input.selection.name ?? input.selection.symbol,
      market: 'CN',
      assetType: input.selection.assetType,
    } : {},
    filters: input.filters ?? {},
    data: {
      asOf: input.asOf ?? cockpit?.generatedAt ?? new Date().toISOString(),
      source: cockpit
        ? `fund-analysis/daily-cockpit+methodology/${PROFESSIONAL_METHODOLOGY_VERSION}`
        : `fund-analysis/methodology/${PROFESSIONAL_METHODOLOGY_VERSION}`,
      freshness: cockpitFreshness ?? 'fresh',
      summary: {
        methodologyVersion: PROFESSIONAL_METHODOLOGY_VERSION,
        workflow: stages.map((stage) => ({
          id: stage.id,
          order: stage.order,
          name: stage.name,
          hardGates: stage.hardGates,
        })),
        decisionPolicy: 'gates-plus-pillars-no-synthetic-total-score',
        methodology: {
          version: PROFESSIONAL_METHODOLOGY_VERSION,
          stageCount: stages.length,
          decisionPolicy: 'gates-plus-pillars-no-synthetic-total-score',
          stages: stages.map((stage) => ({
            id: stage.id,
            order: stage.order,
            name: stage.name,
            purpose: stage.purpose,
            hardGates: stage.hardGates,
          })),
        },
        ...(cockpit ? {
          dailyCockpit: {
            status: cockpit.status,
            brief: cockpit.brief,
            metrics: cockpit.metrics,
            selectedFund: cockpit.selectedFund,
            tasks: cockpit.tasks,
            alerts: cockpit.alerts,
            sources: cockpit.sources,
          },
        } : {}),
      },
    },
    actions: input.workspace.actions.map((action) => ({
      ...action,
      available: true,
    })),
    tasks: input.tasks ?? cockpitTasks,
  }
}
