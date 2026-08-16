import Link from 'next/link'
import {
  ArrowRight,
  BarChart3,
  Bookmark,
  BookOpenText,
  Bot,
  Search,
  Tags,
  UserRoundSearch,
} from 'lucide-react'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const dynamic = 'force-dynamic'

type HomeSummary = {
  fund_share_count: number
  classified_fund_count: number
  recommendation_ready_category_count: number
  recommendation_ready_fund_count: number
  fund_manager_count: number
  research_memo_count: number
  watchlist_group_count: number
  watchlist_fund_count: number
}

type PeerGroup = {
  key: string
  name: string
  classified_fund_count: number
  recommendation_ready_fund_count: number
  style_ready_fund_count: number
  href: string
}

type Manager = {
  id: string
  name: string
  company?: string | null
  category_labels?: string[]
  current_fund_count?: number
  tenure_metric_fund_count?: number
  memo_count?: number
}

type Memo = {
  id: string
  title: string
  manager_name?: string | null
  report_date?: string | null
  report_date_source?: string | null
  report_date_precision?: string | null
  source?: string | null
  summary?: string | null
  tags?: string[]
  classifications?: string[]
  style_labels?: string[]
  href: string
}

type HomePayload = {
  interface_version: string
  summary: HomeSummary
  featured_peer_groups: PeerGroup[]
  featured_managers: Manager[]
  latest_research_memos: Memo[]
}

const emptySummary: HomeSummary = {
  fund_share_count: 0,
  classified_fund_count: 0,
  recommendation_ready_category_count: 0,
  recommendation_ready_fund_count: 0,
  fund_manager_count: 0,
  research_memo_count: 0,
  watchlist_group_count: 0,
  watchlist_fund_count: 0,
}

async function loadHome() {
  try {
    const response = await fetch(`${backendApiBaseUrl}/api/home`, { cache: 'no-store' })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail || 'home unavailable')
    return { data: payload as HomePayload, error: '' }
  } catch {
    return {
      data: {
        interface_version: 'fund_selection_home_v1',
        summary: emptySummary,
        featured_peer_groups: [],
        featured_managers: [],
        latest_research_memos: [],
      } satisfies HomePayload,
      error: '本地基金数据库暂时无法连接，请先启动后端服务。',
    }
  }
}

function numberText(value: number) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function formatMemoDate(memo: Memo) {
  const value = memo.report_date?.slice(0, 10)
  if (!value) return '日期待确认'
  if (memo.report_date_precision === 'quarter') {
    const month = Number(value.slice(5, 7))
    return `${value.slice(0, 4)} Q${Math.floor((month - 1) / 3) + 1}`
  }
  if (memo.report_date_precision === 'month') return `${value.slice(0, 7)} 月`
  return value
}

export default async function HomePage() {
  const { data, error } = await loadHome()
  const summary = data.summary || emptySummary

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden border border-[#c9d5ce] bg-[#173f35] px-6 py-9 text-white sm:px-9 sm:py-12">
        <div className="absolute -right-28 -top-28 h-80 w-80 rounded-full border border-white/10" />
        <div className="absolute right-16 top-20 h-40 w-40 rounded-full border border-white/10" />
        <div className="relative grid gap-9 xl:grid-cols-[minmax(0,1fr)_390px] xl:items-end">
          <div className="max-w-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a9d0bf]">Fund selection home</p>
            <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">先找基金，再看懂它</h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-[#dbe7e1] sm:text-base">
              从基金、经理或调研纪要进入；分类、同类评价和业绩归因在后台完成，缺少证据时会明确告诉你。
            </p>
            <form action="/discover" className="mt-7 grid max-w-2xl gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#71867c]" />
                <input name="search" type="search" placeholder="输入基金名称或代码" className="h-12 w-full border border-white/20 bg-white pl-11 pr-4 text-sm text-[#18231e] outline-none focus:border-[#9ac2b0]" />
              </label>
              <button type="submit" className="h-12 bg-[#e8c475] px-7 text-sm font-bold text-[#243027] hover:bg-[#f0d493]">查找基金</button>
            </form>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#bed4ca]">
              <Link href="/managers" className="hover:text-white">按基金经理查找</Link>
              <Link href="/companies" className="hover:text-white">按基金公司查找</Link>
              <Link href="/research" className="hover:text-white">搜索调研纪要</Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-px overflow-hidden border border-white/20 bg-white/20 text-[#18231e]">
            <div className="bg-[#f7f5ed] p-5"><strong className="block text-2xl">{numberText(summary.fund_share_count)}</strong><span className="mt-1 block text-[11px] text-[#68756e]">基金份额</span></div>
            <div className="bg-[#f7f5ed] p-5"><strong className="block text-2xl">{numberText(summary.fund_manager_count)}</strong><span className="mt-1 block text-[11px] text-[#68756e]">基金经理</span></div>
            <div className="bg-[#f7f5ed] p-5"><strong className="block text-2xl">{numberText(summary.research_memo_count)}</strong><span className="mt-1 block text-[11px] text-[#68756e]">调研纪要</span></div>
            <div className="bg-[#f7f5ed] p-5"><strong className="block text-2xl">{numberText(summary.recommendation_ready_category_count)}</strong><span className="mt-1 block text-[11px] text-[#68756e]">可生成候选的类别</span></div>
          </div>
        </div>
      </section>

      {error ? <div className="border border-[#e6c9a0] bg-[#fff8ec] px-5 py-4 text-sm text-[#7c5b2d]">{error}</div> : null}

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div><h2 className="text-xl font-bold">从这里开始</h2><p className="mt-1 text-xs text-[#748079]">一次只做一件事，复杂方法留在后台。</p></div>
        </div>
        <div className="grid gap-px overflow-hidden border border-[#d7ded9] bg-[#d7ded9] sm:grid-cols-2 xl:grid-cols-4">
          {[
            { href: '/discover', icon: Search, title: '找一只基金', detail: '看净值、收益、回撤、经理和同类位置' },
            { href: '/recommendations', icon: Tags, title: '看同类候选', detail: `已有 ${summary.recommendation_ready_fund_count} 只基金通过类别证据门槛` },
            { href: '/research', icon: BookOpenText, title: '读经理纪要', detail: '按经理归档原文、标签和人工确认结果' },
            { href: '/watchlist', icon: Bookmark, title: '查看我的自选', detail: summary.watchlist_fund_count ? `已收藏 ${summary.watchlist_fund_count} 只基金` : '把感兴趣的基金放在一起继续研究' },
          ].map((item) => {
            const Icon = item.icon
            return (
              <Link key={item.href} href={item.href} className="group bg-white p-5 transition hover:bg-[#f3f7f4]">
                <span className="grid h-10 w-10 place-items-center bg-[#e7efe9] text-[#28624e]"><Icon className="h-5 w-5" /></span>
                <strong className="mt-5 block text-base text-[#1f2d26] group-hover:text-[#28624e]">{item.title}</strong>
                <span className="mt-2 block text-xs leading-6 text-[#748079]">{item.detail}</span>
                <ArrowRight className="mt-5 h-4 w-4 text-[#8c9992] transition group-hover:translate-x-1 group-hover:text-[#28624e]" />
              </Link>
            )
          })}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]">
        <div className="border border-[#d9e0db] bg-white p-5 sm:p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><BarChart3 className="h-4 w-4" />同类候选入口</div><h2 className="mt-2 text-2xl font-bold">哪些类别现在能用</h2></div>
            <Link href="/recommendations" className="text-xs font-bold text-[#28745c]">查看全部<ArrowRight className="ml-1 inline h-3.5 w-3.5" /></Link>
          </div>
          <p className="mt-2 text-xs leading-6 text-[#748079]">只展示分类和关键量化证据已经齐全的同类组，不跨类别排名。</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {data.featured_peer_groups.length ? data.featured_peer_groups.map((group) => (
              <Link key={group.key} href={group.href} className="group border border-[#e0e5e1] bg-[#fafbf9] p-4 hover:border-[#8eb09f]">
                <div className="flex items-start justify-between gap-3"><strong className="text-sm text-[#27362f] group-hover:text-[#28745c]">{group.name}</strong><ArrowRight className="h-4 w-4 shrink-0 text-[#9aa59f]" /></div>
                <div className="mt-4 flex flex-wrap gap-3 text-[11px] text-[#748079]"><span>{group.classified_fund_count} 只同类基金</span><span className="font-bold text-[#28745c]">{group.recommendation_ready_fund_count} 只可评价</span>{group.style_ready_fund_count ? <span>{group.style_ready_fund_count} 只有风格证据</span> : null}</div>
              </Link>
            )) : <div className="sm:col-span-2 border border-dashed border-[#cbd3cd] px-5 py-12 text-center text-sm text-[#748079]">暂无可用同类候选，需先补齐真实量化指标。</div>}
          </div>
        </div>

        <div className="border border-[#d9e0db] bg-white p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3"><div><div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><UserRoundSearch className="h-4 w-4" />经理研究</div><h2 className="mt-2 text-2xl font-bold">近期研究覆盖较完整</h2></div><Link href="/managers" className="text-xs font-bold text-[#28745c]">更多</Link></div>
          <div className="mt-5 divide-y divide-[#e8ece9]">
            {data.featured_managers.length ? data.featured_managers.map((manager) => (
              <Link key={manager.id} href={`/managers/${encodeURIComponent(manager.id)}`} className="flex items-center gap-4 py-4 first:pt-0 last:pb-0">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#e8f0eb] text-sm font-bold text-[#28624e]">{manager.name?.slice(0, 1) || '经'}</span>
                <span className="min-w-0 flex-1"><strong className="block truncate text-sm">{manager.name || '姓名待补'}</strong><span className="mt-1 block truncate text-xs text-[#748079]">{manager.company || '基金公司待补'} · {(manager.category_labels || []).join(' / ') || '分类待补'}</span></span>
                <span className="text-right text-[11px] text-[#748079]"><strong className="block text-sm text-[#8a6b31]">{manager.memo_count || 0}</strong>份纪要</span>
              </Link>
            )) : <div className="py-10 text-center text-sm text-[#748079]">暂无经理研究摘要。</div>}
          </div>
        </div>
      </section>

      <section className="border border-[#d9e0db] bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><BookOpenText className="h-4 w-4" />调研纪要库</div><h2 className="mt-2 text-2xl font-bold">最近入库的基金经理纪要</h2></div>
          <Link href="/research" className="text-xs font-bold text-[#28745c]">打开调研库<ArrowRight className="ml-1 inline h-3.5 w-3.5" /></Link>
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {data.latest_research_memos.length ? data.latest_research_memos.map((memo) => {
            const labels = [...(memo.classifications || []), ...(memo.style_labels || []), ...(memo.tags || [])].slice(0, 4)
            return (
              <Link key={memo.id} href={memo.href} className="group border border-[#e0e5e1] p-5 hover:border-[#8eb09f]">
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-[#78847d]"><span>{memo.manager_name || '经理待确认'}</span><span>·</span><span>{formatMemoDate(memo)}</span><span>·</span><span>{memo.source || '本地纪要'}</span></div>
                <h3 className="mt-3 line-clamp-2 font-bold leading-6 text-[#25332c] group-hover:text-[#28745c]">{memo.title || '无标题纪要'}</h3>
                {memo.summary ? <p className="mt-2 line-clamp-2 text-xs leading-6 text-[#6d7972]">{memo.summary}</p> : null}
                {labels.length ? <div className="mt-4 flex flex-wrap gap-2">{labels.map((label) => <span key={label} className="bg-[#f0f3f0] px-2 py-1 text-[10px] text-[#5f6d65]">{label}</span>)}</div> : null}
              </Link>
            )
          }) : <div className="lg:col-span-2 border border-dashed border-[#cbd3cd] px-5 py-12 text-center text-sm text-[#748079]">调研纪要库尚无资料。</div>}
        </div>
      </section>

      <section className="flex flex-col gap-5 border border-[#d7ded9] bg-[#eef3ef] p-6 sm:flex-row sm:items-center sm:justify-between">
        <div><div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><Bot className="h-4 w-4" />按需分析</div><h2 className="mt-2 text-xl font-bold">选定基金后，再让 AI 综合评价</h2><p className="mt-2 text-xs leading-6 text-[#68756e]">AI 会读取分类内评价、业绩归因和调研纪要；输出范围止于基金研究评价。</p></div>
        <Link href="/analysis" className="inline-flex h-11 shrink-0 items-center justify-center gap-2 bg-[#173f35] px-5 text-sm font-bold text-white">运行一次分析<ArrowRight className="h-4 w-4" /></Link>
      </section>
    </div>
  )
}
