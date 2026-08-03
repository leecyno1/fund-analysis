'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ArrowUpRight,
  BellRing,
  BookOpenCheck,
  CheckCircle2,
  CircleAlert,
  Clock3,
  DatabaseZap,
  FileSearch,
  Gauge,
  ListChecks,
  RefreshCcw,
  Route,
  ShieldCheck,
  Target,
} from 'lucide-react'
import { useTransition } from 'react'
import type {
  DailyCockpitSourceStatus,
  DailyCockpitTone,
  DailyResearchCockpitSnapshot,
  ProfessionalResearchStage,
} from '@/lib/fund-research'
import type { FundSelection } from '@/lib/newma-desk/context'

function formatDateTime(value: string | null | undefined) {
  if (!value) return '待补'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function metricValue(value: number | null, suffix = '') {
  if (value === null) return '—'
  return `${value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })}${suffix}`
}

function toneLabel(tone: DailyCockpitTone) {
  if (tone === 'danger') return '阻断'
  if (tone === 'warning') return '需复核'
  if (tone === 'positive') return '就绪'
  return '观察'
}

function sourceStatusLabel(status: DailyCockpitSourceStatus) {
  if (status === 'healthy') return '正常'
  if (status === 'stale') return '陈旧'
  return '不可用'
}

function dataQualityLabel(value: string) {
  const normalized = value.toLowerCase()
  if (['healthy', 'strong', 'ready', 'good'].includes(normalized)) return '数据质量正常'
  if (['weak', 'stale', 'warning', 'partial'].includes(normalized)) return '数据需复核'
  if (['blocked', 'error', 'failed'].includes(normalized)) return '数据质量阻断'
  return '数据质量待核'
}

export default function FundResearchDailyCockpit({
  snapshot,
  stages,
  selection,
}: {
  snapshot: DailyResearchCockpitSnapshot
  stages: ProfessionalResearchStage[]
  selection: FundSelection | null
}) {
  const router = useRouter()
  const [isRefreshing, startRefresh] = useTransition()
  const selected = snapshot.selectedFund
  const metrics = [
    { label: '研究范围', value: metricValue(snapshot.metrics.totalFunds), unit: '只基金', detail: 'point-in-time 业务库' },
    { label: '证据覆盖', value: metricValue(snapshot.metrics.evidenceCoverage, '%'), unit: '非评价总分', detail: '字段覆盖与可追溯性' },
    { label: '研究清单', value: metricValue(snapshot.metrics.candidateCount), unit: '只候选', detail: `${metricValue(snapshot.metrics.blockedCandidateCount)} 只被门槛阻断` },
    { label: '未决复核', value: metricValue(snapshot.metrics.unresolvedAlertCount), unit: '个事件', detail: `${metricValue(snapshot.metrics.highAlertCount)} 个高严重度` },
    { label: '数据健康', value: metricValue(snapshot.metrics.staleDatasetCount), unit: '个陈旧集', detail: `${metricValue(snapshot.metrics.failedSyncCount)} 次近期失败` },
  ]

  return (
    <div className="fund-cockpit" data-vibe-block="summary" data-vibe-block-id="daily-research-cockpit">
      <section className={`fund-cockpit-brief fund-cockpit-tone--${snapshot.brief.tone}`}>
        <div className="fund-cockpit-brief__signal" aria-hidden="true">
          <Target />
        </div>
        <div className="fund-cockpit-brief__copy">
          <div className="fund-cockpit-brief__meta">
            <span>{snapshot.brief.label}</span>
            <span>{formatDateTime(snapshot.generatedAt)} 更新</span>
            <span>{snapshot.status === 'ready' ? '数据链完整' : snapshot.status === 'partial' ? '部分数据可用' : '数据链不可用'}</span>
          </div>
          <h2>{snapshot.brief.title}</h2>
          <p>{snapshot.brief.detail}</p>
        </div>
        <button
          type="button"
          className="fund-cockpit-refresh"
          disabled={isRefreshing}
          onClick={() => startRefresh(() => router.refresh())}
        >
          <RefreshCcw aria-hidden="true" className={isRefreshing ? 'is-spinning' : undefined} />
          {isRefreshing ? '刷新中' : '刷新快照'}
        </button>
      </section>

      {snapshot.errors.length > 0 ? (
        <section className="fund-cockpit-error" aria-label="暂不可用的数据入口">
          <CircleAlert aria-hidden="true" />
          <div>
            <strong>部分入口未返回数据</strong>
            <p>{snapshot.errors.join('；')}</p>
          </div>
        </section>
      ) : null}

      <section
        className="fund-cockpit-metrics"
        data-vibe-block="metrics"
        data-vibe-block-id="daily-research-metrics"
        data-vibe-value-path="dailyCockpit.metrics"
      >
        {metrics.map((metric) => (
          <article key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.unit}</small>
            <p>{metric.detail}</p>
          </article>
        ))}
      </section>

      <div className="fund-cockpit-grid">
        <section
          className="fund-cockpit-panel fund-cockpit-panel--selected"
          data-vibe-block="summary"
          data-vibe-block-id="selected-research-object"
          data-vibe-value-path="dailyCockpit.selectedFund"
        >
          <div className="fund-cockpit-panel__heading">
            <div>
              <span className="fund-research-kicker">Current research object</span>
              <h3>当前研究对象</h3>
            </div>
            <FileSearch aria-hidden="true" />
          </div>

          {selected ? (
            <>
              <div className="fund-cockpit-selected__identity">
                <div>
                  <span>{selected.symbol}</span>
                  <h4>{selected.name}</h4>
                  <p>{selected.type} · {selected.styleLabel}</p>
                </div>
                <div className="fund-cockpit-selected__coverage">
                  <span>证据覆盖</span>
                  <strong>{metricValue(selected.evidenceCoverage, '%')}</strong>
                </div>
              </div>
              <dl className="fund-cockpit-selected__facts">
                <div><dt>最新净值</dt><dd>{selected.nav === null ? '待补' : selected.nav.toFixed(4)}</dd><small>{selected.navDate || '时点待补'}</small></div>
                <div><dt>基金规模</dt><dd>{selected.totalAsset === null ? '待补' : `${selected.totalAsset.toFixed(2)} 亿`}</dd><small>容量与清盘风险入口</small></div>
                <div><dt>同类组</dt><dd>{selected.peerGroup}</dd><small>比较前置条件</small></div>
                <div><dt>适配基准</dt><dd>{selected.benchmark}</dd><small>alpha 解释前置条件</small></div>
              </dl>
              <div className="fund-cockpit-selected__trust">
                <ShieldCheck aria-hidden="true" />
                <div>
                  <strong>{dataQualityLabel(selected.dataQualityStatus)}</strong>
                  <span>对象数据截至 {formatDateTime(selected.dataAsOf)}</span>
                  <span>{selected.managers.length ? `现任经理：${selected.managers.join('、')}` : '经理任期切片待补'}</span>
                </div>
              </div>
              <div className="fund-cockpit-panel__actions">
                <Link href={selected.detailHref}>打开对象研究页 <ArrowUpRight aria-hidden="true" /></Link>
                <Link href={`/mod/fund-research/due-diligence?symbol=${encodeURIComponent(selected.symbol)}&name=${encodeURIComponent(selected.name)}`}>进入结构化尽调</Link>
              </div>
            </>
          ) : selection ? (
            <div className="fund-cockpit-empty">
              <CircleAlert aria-hidden="true" />
              <h4>{selection.symbol} 对象快照不可用</h4>
              <p>当前基金已经进入 Desk 上下文，但对象数据入口没有返回可核验快照。驾驶舱不会把全市场统计或旧缓存冒充为该基金结论。</p>
              <Link href={`/market?search=${encodeURIComponent(selection.symbol)}&source=fund_daily_cockpit`}>检查对象与数据入口 <ArrowUpRight aria-hidden="true" /></Link>
            </div>
          ) : (
            <div className="fund-cockpit-empty">
              <Route aria-hidden="true" />
              <h4>尚未选择基金</h4>
              <p>选择对象后，这里会展示真实净值时点、证据覆盖、同类组、基准、经理和数据质量；缺失字段不会被自动补写。</p>
              <Link href="/market?source=fund_daily_cockpit">从研究清单选择 <ArrowUpRight aria-hidden="true" /></Link>
            </div>
          )}
        </section>

        <section
          className="fund-cockpit-panel fund-cockpit-panel--tasks"
          data-vibe-block="table"
          data-vibe-block-id="daily-research-queue"
          data-vibe-rows-path="dailyCockpit.tasks"
        >
          <div className="fund-cockpit-panel__heading">
            <div>
              <span className="fund-research-kicker">Action queue</span>
              <h3>今日研究队列</h3>
            </div>
            <ListChecks aria-hidden="true" />
          </div>
          <div className="fund-cockpit-task-list">
            {snapshot.tasks.map((task, index) => (
              <Link key={task.id} href={task.href} className={`fund-cockpit-task fund-cockpit-tone--${task.tone}`}>
                <span className="fund-cockpit-task__index">{String(index + 1).padStart(2, '0')}</span>
                <span className="fund-cockpit-task__body">
                  <span className="fund-cockpit-task__meta">{toneLabel(task.tone)} · {task.source}</span>
                  <strong>{task.title}</strong>
                  <small>{task.detail}</small>
                </span>
                <ArrowUpRight aria-hidden="true" />
              </Link>
            ))}
            {snapshot.tasks.length === 0 ? (
              <div className="fund-cockpit-empty fund-cockpit-empty--compact">
                <CheckCircle2 aria-hidden="true" />
                <h4>当前没有待处理队列</h4>
                <p>这不代表基金通过研究，只表示现有事件和覆盖入口没有返回待办。</p>
              </div>
            ) : null}
          </div>
        </section>

        <section
          className="fund-cockpit-panel"
          data-vibe-block="table"
          data-vibe-block-id="evidence-source-health"
          data-vibe-rows-path="dailyCockpit.sources"
        >
          <div className="fund-cockpit-panel__heading">
            <div>
              <span className="fund-research-kicker">Evidence health</span>
              <h3>证据与数据健康</h3>
            </div>
            <DatabaseZap aria-hidden="true" />
          </div>
          <div className="fund-cockpit-source-list">
            {snapshot.sources.map((source) => (
              <article key={source.id}>
                <span className={`fund-cockpit-source__status is-${source.status}`} />
                <div>
                  <strong>{source.label}</strong>
                  <p>{source.detail}</p>
                  <small>{source.asOf ? `截至 ${formatDateTime(source.asOf)}` : '未返回可核验时点'}</small>
                </div>
                <span className={`fund-cockpit-source__label is-${source.status}`}>{sourceStatusLabel(source.status)}</span>
              </article>
            ))}
          </div>
        </section>

        <section
          className="fund-cockpit-panel"
          data-vibe-block="table"
          data-vibe-block-id="review-events"
          data-vibe-rows-path="dailyCockpit.alerts"
        >
          <div className="fund-cockpit-panel__heading">
            <div>
              <span className="fund-research-kicker">Reversal signals</span>
              <h3>复核与反转信号</h3>
            </div>
            <BellRing aria-hidden="true" />
          </div>
          <div className="fund-cockpit-alert-list">
            {snapshot.alerts.map((alert) => (
              <Link key={alert.id} href={alert.href} className={`is-${alert.severity}`}>
                <span className="fund-cockpit-alert__icon"><CircleAlert aria-hidden="true" /></span>
                <span>
                  <span>{alert.fundCode || '全局事件'} · {alert.severity === 'high' ? '高' : alert.severity === 'medium' ? '中' : '低'}严重度</span>
                  <strong>{alert.title}</strong>
                  <small>{alert.detail}</small>
                </span>
              </Link>
            ))}
            {snapshot.alerts.length === 0 ? (
              <div className="fund-cockpit-empty fund-cockpit-empty--compact">
                <BellRing aria-hidden="true" />
                <h4>没有读到未决复核事件</h4>
                <p>若事件入口不可用，请以数据健康状态为准，不能据此判断风险已经消失。</p>
              </div>
            ) : null}
          </div>
          <div className="fund-cockpit-panel__actions">
            <Link href="/evidence-coverage?section=review-events">打开完整事件台账 <ArrowUpRight aria-hidden="true" /></Link>
          </div>
        </section>
      </div>

      <section
        className="fund-cockpit-workflow"
        data-vibe-block="table"
        data-vibe-block-id="professional-workflow"
        data-vibe-rows-path="methodology.stages"
      >
        <div className="fund-cockpit-panel__heading">
          <div>
            <span className="fund-research-kicker">Research backbone</span>
            <h3>驾驶舱背后的九段研究内核</h3>
          </div>
          <div className="fund-cockpit-workflow__policy"><Gauge aria-hidden="true" /> 不使用合成总分</div>
        </div>
        <div className="fund-cockpit-stage-rail">
          {stages.map((stage) => (
            <article key={stage.id}>
              <span>{String(stage.order).padStart(2, '0')}</span>
              <BookOpenCheck aria-hidden="true" />
              <strong>{stage.name}</strong>
              <small>{stage.hardGates[0]}</small>
            </article>
          ))}
        </div>
        <div className="fund-cockpit-workflow__footer">
          <span><Clock3 aria-hidden="true" /> 所有结论绑定 as-of、来源和方法版本</span>
          <span><ShieldCheck aria-hidden="true" /> Gates + Pillars + Confidence + Counter-evidence</span>
        </div>
      </section>
    </div>
  )
}
