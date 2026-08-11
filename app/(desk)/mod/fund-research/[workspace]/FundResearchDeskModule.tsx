'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ArrowRight,
  BarChart3,
  Bot,
  Database,
  FolderSearch,
  Search,
  Sparkles,
} from 'lucide-react'
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
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

type BridgeStatus = 'standalone' | 'connecting' | 'connected'

const workspaceIcons = {
  discover: Search,
  research: FolderSearch,
  analysis: Bot,
  recommendations: Sparkles,
  advanced: BarChart3,
} as const

function workspaceHref(workspace: FundResearchWorkspace, selection: FundSelection | null) {
  if (!selection) return workspace.primaryHref
  const code = encodeURIComponent(selection.symbol)
  if (workspace.id === 'discover') return `/funds/${code}`
  if (workspace.id === 'analysis') return `/analysis?fundCode=${code}`
  if (workspace.id === 'advanced') return `/analysis/advanced?fundCode=${code}`
  return workspace.primaryHref
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
}: {
  workspace: FundResearchWorkspace
  initialSelection: FundSelection | null
}) {
  const router = useRouter()
  const [selection, setSelection] = useState<FundSelection | null>(initialSelection)
  const [symbolDraft, setSymbolDraft] = useState(initialSelection?.symbol ?? '')
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>(() => (
    typeof window !== 'undefined' && window.self !== window.top ? 'connecting' : 'standalone'
  ))
  const bridgeRef = useRef<NewmaDeskBridge | null>(null)
  const context = useMemo(
    () => buildFundResearchPageContext({ workspace, selection }),
    [selection, workspace],
  )
  const contextRef = useRef(context)

  useEffect(() => {
    const bridge = createNewmaDeskBridge({ modId: workspace.modId, initialContext: contextRef.current })
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
    void bridge.ready.then((config) => setBridgeStatus(config ? 'connected' : 'standalone'))
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

  const CurrentIcon = workspaceIcons[workspace.id]

  return (
    <main className="fund-research-mod" data-vibe-page="1.0" data-vibe-title={workspace.title}>
      <header className="fund-research-hero">
        <div className="fund-research-hero__content">
          <div className="fund-research-eyebrow">
            <Database aria-hidden="true" />
            <span>基金选择助手 · 真实数据优先</span>
          </div>
          <h1>{workspace.title}</h1>
          <p>{workspace.purpose}</p>
          <div className="fund-research-status-row" aria-label="运行状态">
            <span className="fund-research-status">
              <span className={`fund-research-status__dot fund-research-status__dot--${bridgeStatus}`} />
              {bridgeStatus === 'connected' ? '已连接牛马 Desk' : bridgeStatus === 'connecting' ? '正在连接 Desk' : '独立运行'}
            </span>
            <span className="fund-research-status">不生成虚构数据</span>
            <span className="fund-research-status">不提供交易建议</span>
          </div>
        </div>

        <form className="fund-research-selector" onSubmit={selectFund} aria-label="选择基金">
          <label htmlFor="fund-symbol">当前基金</label>
          <div className="fund-research-selector__row">
            <Search aria-hidden="true" />
            <input
              id="fund-symbol"
              value={symbolDraft}
              onChange={(event) => setSymbolDraft(event.target.value)}
              placeholder="输入基金代码，例如 000390.OF"
              maxLength={24}
            />
            <button type="submit">选择这只基金</button>
          </div>
          <p>{selection ? `已选择：${selection.name || selection.symbol}（${selection.symbol}）` : '未选择基金时只展示功能入口，不生成对象级评价。'}</p>
        </form>
      </header>

      <nav className="fund-research-tabs" aria-label="基金选择助手页面">
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

      <section
        className="fund-research-section"
        data-vibe-block="summary"
        data-vibe-block-id="fund-selection-summary"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">当前功能</span>
            <h2>直接进入 {workspace.title}</h2>
          </div>
          <Link className="fund-research-primary-link" href={workspaceHref(workspace, selection)}>
            {workspace.primaryLabel}
            <ArrowRight aria-hidden="true" />
          </Link>
        </div>
        <div className="fund-research-principles">
          {workspace.capabilities.map((capability) => (
            <article key={capability.name}>
              <CurrentIcon aria-hidden="true" />
              <div>
                <strong>{capability.name}</strong>
                <span>{capability.purpose}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section
        className="fund-research-section"
        data-vibe-block="table"
        data-vibe-block-id="fund-selection-capabilities"
        data-vibe-rows-path="capabilities"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">证据说明</span>
            <h2>每项结果从哪里来</h2>
          </div>
          <span className="fund-research-count">{workspace.capabilities.length} 项能力</span>
        </div>
        <div className="fund-research-table-wrap">
          <table>
            <thead><tr><th>功能</th><th>用途</th><th>主要证据</th></tr></thead>
            <tbody>
              {workspace.capabilities.map((capability) => (
                <tr key={capability.name}>
                  <th scope="row">{capability.name}</th>
                  <td>{capability.purpose}</td>
                  <td>{capability.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section
        className="fund-research-section"
        data-vibe-block="actions"
        data-vibe-block-id="fund-selection-actions"
      >
        <div className="fund-research-section__heading">
          <div>
            <span className="fund-research-kicker">Desk Actions</span>
            <h2>Agent 可调用的真实能力</h2>
          </div>
        </div>
        <div className="fund-research-source-grid">
          {workspace.actions.map((action) => (
            <article key={action.id}>
              <div className="fund-research-source-grid__meta"><span>{action.id}</span></div>
              <h3>{action.label}</h3>
              <p>通过基金选择应用的真实数据入口执行；现场分析会保存历史记录。</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="fund-research-footer">
        <span>业务数据保留在基金数据库；Desk 不接收上游数据源密钥。</span>
        <span>事件：security.selected · Context：ViewSpec 1.0</span>
      </footer>
    </main>
  )
}
