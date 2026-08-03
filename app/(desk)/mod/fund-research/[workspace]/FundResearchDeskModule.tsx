'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  CircleAlert,
  DatabaseZap,
  FileSearch,
  GitCompareArrows,
  Landmark,
  Network,
  RefreshCcw,
  Scale,
  Search,
  ShieldCheck,
  UsersRound,
} from 'lucide-react'
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  PROFESSIONAL_METHODOLOGY_VERSION,
  methodologySources,
  professionalResearchStages,
  type DailyResearchCockpitSnapshot,
} from '@/lib/fund-research'
import {
  buildFundSelectionEventPayload,
  createNewmaDeskBridge,
  type NewmaDeskBridge,
} from '@/lib/newma-desk/bridge'
import {
  buildFundResearchPageContext,
  fundResearchWorkspaces,
  type FundResearchWorkspace,
  type FundSelection,
} from '@/lib/newma-desk/context'
import FundResearchDailyCockpit from './FundResearchDailyCockpit'

type BridgeStatus = 'standalone' | 'connecting' | 'connected'

const stageIcons = [
  Network,
  DatabaseZap,
  Scale,
  GitCompareArrows,
  FileSearch,
  UsersRound,
  ShieldCheck,
  RefreshCcw,
  BookOpenCheck,
]

const workspaceDeliverables: Record<FundResearchWorkspace['id'], Array<{
  name: string
  output: string
  gate: string
}>> = {
  overview: [
    { name: '研究身份', output: '基金实体、份额、生命周期、策略分类', gate: '身份或生命周期不可判定则停止' },
    { name: '可用证据', output: '来源、as-of、版本、覆盖率、缺口', gate: '关键字段缺失转补证队列' },
    { name: '研究结论', output: '论点、反证、置信度、反转条件', gate: '禁止由单一总分直接晋级' },
  ],
  selection: [
    { name: '研究范围准入', output: 'point-in-time 基金范围与终止基金保留', gate: '幸存者偏差或份额重复时阻断' },
    { name: '同类与基准', output: '类别、策略、规模、年限、合同基准', gate: '样本不足只允许观察性比较' },
    { name: '量化轨迹', output: '净费后滚动收益、回撤、捕获率、因子与容量', gate: '短期收益排名不能独立形成候选' },
  ],
  'due-diligence': [
    { name: 'People', output: '任期切片、团队结构、人员稳定性与关键人风险', gate: '关键人员证据不可核验时阻断' },
    { name: 'Process', output: '理念、组合构建、卖出纪律、风险预算与实际持仓一致性', gate: '宣称流程与行为矛盾时复核' },
    { name: 'Parent / Price / ODD', output: '公司治理、费用、载体、估值和运营控制', gate: '重大运营完整性缺口阻断' },
  ],
  'peer-comparison': [
    { name: 'Peer group', output: '资产类别、策略、主动/被动、风格、规模、年限', gate: '同类组不可解释则不出优劣结论' },
    { name: 'Benchmark', output: '合同基准、风格基准、RBSA/HBSA 交叉验证', gate: '基准不适配则 alpha 无效' },
    { name: 'Comparison', output: '滚动分布、下行捕获、回撤修复、Active Share、容量', gate: '证据必须披露不确定性和反例' },
  ],
  monitoring: [
    { name: '人员触发', output: '经理、团队或公司治理变化', gate: '关键人变化进入强制复核' },
    { name: '组合触发', output: '持仓、风格、集中度、流动性与规模漂移', gate: '超阈值变化不得沿用旧结论' },
    { name: '证据触发', output: '费用、材料、数据源或覆盖率变化', gate: '失效证据自动降级置信度' },
  ],
  methodology: [
    { name: '版本合同', output: '方法版本、变更理由、适用范围与迁移说明', gate: '禁止静默改变口径' },
    { name: '可复现快照', output: '输入、as-of、来源、计算与输出快照', gate: '无法重放的结论不能通过审计' },
    { name: '研究审阅', output: '复核人、反证、未决问题与结论反转条件', gate: 'AI 输出不得跳过人工研究责任' },
  ],
}

function relatedSources(workspace: FundResearchWorkspace) {
  const sourceIds = new Set(
    professionalResearchStages
      .filter((stage) => workspace.stageIds.includes(stage.id))
      .flatMap((stage) => stage.sourceIds),
  )
  return methodologySources.filter((source) => sourceIds.has(source.id))
}

function encodedViewData(value: unknown) {
  return JSON.stringify(value).replace(/</g, '\\u003c')
}

function workspaceHref(workspace: FundResearchWorkspace, selection: FundSelection | null) {
  if (!selection) return workspace.primaryHref
  const params = new URLSearchParams({
    symbol: selection.symbol,
    name: selection.name || selection.symbol,
    assetType: selection.assetType,
  })
  const separator = workspace.primaryHref.includes('?') ? '&' : '?'
  return `${workspace.primaryHref}${separator}${params.toString()}`
}

function workspaceSelectionHref(workspace: FundResearchWorkspace, selection: FundSelection) {
  const params = new URLSearchParams({
    symbol: selection.symbol,
    name: selection.name || selection.symbol,
    assetType: selection.assetType,
  })
  return `/mod/fund-research/${workspace.id}?${params.toString()}`
}

export default function FundResearchDeskModule({
  workspace,
  initialSelection,
  initialCockpitSnapshot,
}: {
  workspace: FundResearchWorkspace
  initialSelection: FundSelection | null
  initialCockpitSnapshot: DailyResearchCockpitSnapshot | null
}) {
  const router = useRouter()
  const [selection, setSelection] = useState<FundSelection | null>(initialSelection)
  const [symbolDraft, setSymbolDraft] = useState(initialSelection?.symbol ?? '')
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>(() => (
    typeof window !== 'undefined' && window.self !== window.top ? 'connecting' : 'standalone'
  ))
  const bridgeRef = useRef<NewmaDeskBridge | null>(null)
  const context = useMemo(
    () => buildFundResearchPageContext({ workspace, selection, cockpit: initialCockpitSnapshot }),
    [initialCockpitSnapshot, selection, workspace],
  )
  const contextRef = useRef(context)
  const stages = useMemo(
    () => professionalResearchStages.filter((stage) => workspace.stageIds.includes(stage.id)),
    [workspace],
  )
  const sources = useMemo(() => relatedSources(workspace), [workspace])

  useEffect(() => {
    const bridge = createNewmaDeskBridge({
      modId: workspace.modId,
      initialContext: contextRef.current,
    })
    bridgeRef.current = bridge
    const unregisterContext = bridge.setContextProvider(() => contextRef.current)
    const unsubscribeEvent = bridge.subscribeEvent((event) => {
      if (event.event !== 'security.selected') return
      if (!['fund', 'etf'].includes(String(event.payload.assetType ?? 'fund'))) return
      if (typeof event.payload.symbol !== 'string') return
      const nextSelection: FundSelection = {
        symbol: event.payload.symbol.trim().toUpperCase().slice(0, 24),
        name: typeof event.payload.name === 'string' ? event.payload.name.slice(0, 80) : undefined,
        assetType: event.payload.assetType === 'etf' ? 'etf' : 'fund',
      }
      if (!nextSelection.symbol) return
      setSelection(nextSelection)
      setSymbolDraft(nextSelection.symbol)
      router.replace(workspaceSelectionHref(workspace, nextSelection))
    })
    void bridge.ready.then((config) => {
      setBridgeStatus(config ? 'connected' : 'standalone')
    })
    return () => {
      unregisterContext()
      unsubscribeEvent()
      bridge.close()
      bridgeRef.current = null
    }
  }, [router, workspace])

  useEffect(() => {
    contextRef.current = context
    void bridgeRef.current?.publishContext()
  }, [context])

  function selectFund(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const symbol = symbolDraft.trim().toUpperCase().slice(0, 24)
    if (!symbol) return
    const nextSelection: FundSelection = { symbol, name: symbol, assetType: 'fund' }
    setSelection(nextSelection)
    bridgeRef.current?.emitEvent('security.selected', buildFundSelectionEventPayload(nextSelection))
    router.replace(workspaceSelectionHref(workspace, nextSelection))
  }

  return (
    <main
      className="fund-research-mod"
      data-vibe-page="1.0"
      data-vibe-title={workspace.title}
    >
      <header className="fund-research-hero">
        <div className="fund-research-hero__content">
          <div className="fund-research-eyebrow">
            <Landmark aria-hidden="true" />
            <span>Professional Fund Research · Methodology {PROFESSIONAL_METHODOLOGY_VERSION}</span>
          </div>
          <h1>{workspace.title}</h1>
          <p>{workspace.purpose}</p>
          <div className="fund-research-status-row" aria-label="运行状态">
            <span className="fund-research-status">
              <span className={`fund-research-status__dot fund-research-status__dot--${bridgeStatus}`} />
              {bridgeStatus === 'connected' ? '已连接牛马 Desk' : bridgeStatus === 'connecting' ? '正在连接 Desk' : '独立运行'}
            </span>
            <span className="fund-research-status">ViewSpec 1.0</span>
            <span className="fund-research-status">Level 3 Context</span>
          </div>
        </div>

        <form className="fund-research-selector" onSubmit={selectFund} aria-label="选择研究对象">
          <label htmlFor="fund-symbol">当前研究对象</label>
          <div className="fund-research-selector__row">
            <Search aria-hidden="true" />
            <input
              id="fund-symbol"
              value={symbolDraft}
              onChange={(event) => setSymbolDraft(event.target.value)}
              placeholder="输入基金代码，例如 000001.OF"
              maxLength={24}
            />
            <button type="submit">设为当前对象</button>
          </div>
          <p>
            {selection
              ? `已选择：${selection.name || selection.symbol}（${selection.symbol}）`
              : workspace.id === 'overview'
                ? '尚未选择基金；驾驶舱仍展示全局证据、数据健康和复核队列，不生成对象级虚构评价。'
                : '尚未选择基金；当前页面只展示方法与工作流，不生成虚构评价。'}
          </p>
        </form>
      </header>

      <nav className="fund-research-tabs" aria-label="基金研究模组页面">
        {fundResearchWorkspaces.map((item) => (
          <Link
            key={item.id}
            href={selection ? workspaceSelectionHref(item, selection) : `/mod/fund-research/${item.id}`}
            aria-current={item.id === workspace.id ? 'page' : undefined}
            className={item.id === workspace.id ? 'is-active' : undefined}
          >
            {item.shortTitle}
          </Link>
        ))}
      </nav>

      {workspace.id === 'overview' && initialCockpitSnapshot ? (
        <FundResearchDailyCockpit snapshot={initialCockpitSnapshot} stages={stages} selection={selection} />
      ) : (
        <>
      <section
        className="fund-research-section"
        data-vibe-block="metrics"
        data-vibe-block-id="research-position"
        data-vibe-value-path="research.position"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">研究位置</span>
            <h2>先判断证据是否足以研究，再判断基金表现如何</h2>
          </div>
          <Link className="fund-research-primary-link" href={workspaceHref(workspace, selection)}>
            {workspace.primaryLabel}
            <ArrowRight aria-hidden="true" />
          </Link>
        </div>
        <div className="fund-research-principles">
          <article>
            <CheckCircle2 aria-hidden="true" />
            <div><strong>净费后与长期</strong><span>滚动窗口、回撤修复和费用影响优先于单年榜单。</span></div>
          </article>
          <article>
            <Scale aria-hidden="true" />
            <div><strong>同类与基准先行</strong><span>没有可解释 peer group 和适配基准，不输出相对优势。</span></div>
          </article>
          <article>
            <CircleAlert aria-hidden="true" />
            <div><strong>反证与不确定性</strong><span>每个结论都记录反例、置信度和反转条件。</span></div>
          </article>
        </div>
      </section>

      <section
        className="fund-research-section"
        data-vibe-block="table"
        data-vibe-block-id="professional-workflow"
        data-vibe-rows-path="methodology.stages"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">CFA Manager Selection Backbone</span>
            <h2>{workspace.id === 'overview' ? '九段式专业研究流程' : `${workspace.shortTitle}覆盖的研究阶段`}</h2>
          </div>
          <span className="fund-research-count">{stages.length} 个阶段</span>
        </div>
        <div className="fund-research-stage-grid">
          {stages.map((stage) => {
            const Icon = stageIcons[stage.order - 1] ?? BookOpenCheck
            return (
              <article key={stage.id} className="fund-research-stage-card">
                <div className="fund-research-stage-card__top">
                  <span className="fund-research-stage-card__number">{String(stage.order).padStart(2, '0')}</span>
                  <Icon aria-hidden="true" />
                </div>
                <h3>{stage.name}</h3>
                <p>{stage.purpose}</p>
                <div className="fund-research-stage-card__gate">
                  <ShieldCheck aria-hidden="true" />
                  <span>{stage.hardGates[0]}</span>
                </div>
              </article>
            )
          })}
        </div>
        <script
          type="application/json"
          data-vibe-chart-option
          dangerouslySetInnerHTML={{
            __html: encodedViewData(stages.map((stage) => ({
              id: stage.id,
              order: stage.order,
              name: stage.name,
              requiredEvidence: stage.requiredEvidence,
              hardGates: stage.hardGates,
            }))),
          }}
        />
      </section>

      <section
        className="fund-research-section"
        data-vibe-block="table"
        data-vibe-block-id="decision-policy"
        data-vibe-rows-path="workspace.deliverables"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">Gates + Pillars</span>
            <h2>本页面交付物与阻断规则</h2>
          </div>
          <span className="fund-research-no-score">不使用合成总分</span>
        </div>
        <div className="fund-research-table-wrap">
          <table>
            <thead>
              <tr>
                <th>研究单元</th>
                <th>结构化输出</th>
                <th>治理门槛</th>
              </tr>
            </thead>
            <tbody>
              {workspaceDeliverables[workspace.id].map((item) => (
                <tr key={item.name}>
                  <th scope="row">{item.name}</th>
                  <td>{item.output}</td>
                  <td>{item.gate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section
        className="fund-research-section"
        data-vibe-block="table"
        data-vibe-block-id="source-foundation"
        data-vibe-rows-path="methodology.sources"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">Research Foundation</span>
            <h2>本页面采用的论文与公开方法</h2>
          </div>
          <span className="fund-research-count">{sources.length} 个来源</span>
        </div>
        <div className="fund-research-source-grid">
          {sources.map((source) => (
            <article key={source.id}>
              <div className="fund-research-source-grid__meta">
                <span>{source.year}</span>
                <span>{source.authors}</span>
              </div>
              <h3><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></h3>
              <p>{source.contribution}</p>
              <small>{source.limitation}</small>
            </article>
          ))}
        </div>
      </section>
        </>
      )}

      <footer className="fund-research-footer">
        <span>数据存储：业务研究库使用 dedicated PostgreSQL；Desk 不接收数据库凭据。</span>
        <span>事件：security.selected · Context：ViewSpec 1.0</span>
      </footer>
    </main>
  )
}
