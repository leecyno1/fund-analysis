'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ArrowRight, CheckCircle2, CircleAlert, GitCompareArrows, LoaderCircle, Tags } from 'lucide-react'
import type { CamelFund } from '@/lib/backend-api'
import {
  drawdownMetric,
  formatAsset,
  formatPercent,
  managerName,
  peerGroup,
  professionalFundScore,
  professionalScorePercentile,
  recommendationEvidence,
  returnMetric,
  styleLabel,
  type SimpleFund,
} from '@/lib/simple-fund-view'

type Props = {
  initialFunds: CamelFund[]
  initialCategories: string[]
  universeTotal: number
  initialError: string
}

export default function RecommendationClient({ initialFunds, initialCategories, universeTotal, initialError }: Props) {
  const universe = initialFunds as SimpleFund[]
  const categories = useMemo(() => initialCategories.length
    ? initialCategories
    : Array.from(new Set(universe.map((fund) => peerGroup(fund)).filter((value) => value !== '类别待确认'))),
  [initialCategories, universe])
  const [category, setCategory] = useState('')
  const [style, setStyle] = useState('')
  const [categoryFunds, setCategoryFunds] = useState<SimpleFund[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [peerUniverseCount, setPeerUniverseCount] = useState(0)
  const [evidenceEligibleCount, setEvidenceEligibleCount] = useState(0)
  const [availableStyles, setAvailableStyles] = useState<string[]>([])
  const recommendations = categoryFunds

  async function loadCandidates(nextCategory: string, nextStyle = '') {
    setCategoryFunds([])
    setPeerUniverseCount(0)
    setEvidenceEligibleCount(0)
    setLoadError('')
    if (!nextCategory) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ category: nextCategory })
      if (nextStyle) params.set('style', nextStyle)
      const response = await fetch(`/api/recommendations?${params}`, {
        cache: 'no-store',
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || '同类基金评价暂时不可用')
      setCategoryFunds(Array.isArray(payload.data) ? payload.data : [])
      setPeerUniverseCount(Number(payload.peerUniverseCount || 0))
      setEvidenceEligibleCount(Number(payload.evidenceEligibleCount || 0))
      setAvailableStyles(Array.isArray(payload.availableStyles) ? payload.availableStyles : [])
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : '同类基金评价暂时不可用')
    } finally {
      setLoading(false)
    }
  }

  function chooseCategory(nextCategory: string) {
    setCategory(nextCategory)
    setStyle('')
    setAvailableStyles([])
    void loadCandidates(nextCategory)
  }

  const compareHref = `/compare?${new URLSearchParams({
    codes: recommendations.slice(0, 6).map((fund) => fund.windCode).join(','),
  }).toString()}`

  return (
    <div className="space-y-7">
      <section className="grid gap-7 border-b border-[#dce1dc] pb-8 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 text-xs font-bold uppercase text-[#28745c]"><Tags className="h-4 w-4" />标签推荐</div>
          <h1 className="mt-3 text-3xl font-bold leading-tight text-[#18231e] sm:text-4xl">先选基金类别，再看同类候选</h1>
          <p className="mt-3 text-sm leading-7 text-[#65716b] sm:text-base">系统检查完整同类组，只保留分类和关键证据齐全的基金，再按该类别自己的评价方法给出最多十只候选。</p>
        </div>
        <div className="border-l-4 border-[#d7b46a] bg-[#fff9eb] px-4 py-3 text-xs leading-6 text-[#755722]">
          候选组用于缩小研究范围，不跨类比较，不代表收益承诺或买卖建议。
        </div>
      </section>

      {initialError ? <div className="border border-[#e5c98f] bg-[#fff8e8] px-5 py-4 text-sm text-[#78551c]">{initialError}</div> : null}
      {loadError ? <div className="border border-[#e5c98f] bg-[#fff8e8] px-5 py-4 text-sm text-[#78551c]">{loadError}</div> : null}

      <section className="grid gap-5 border border-[#dbe1dc] bg-white p-5 md:grid-cols-2">
        <label className="block">
          <span className="text-sm font-bold">1. 基金类别</span>
          <span className="mt-1 block text-xs text-[#7a8580]">必选，不同类别不放入同一个排序池</span>
          <select value={category} onChange={(event) => void chooseCategory(event.target.value)} className="mt-3 h-11 w-full rounded-md border border-[#cfd6d0] bg-white px-3 text-sm outline-none focus:border-[#28745c]">
            <option value="">请选择一个基金类别</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-bold">2. 风格标签</span>
          <span className="mt-1 block text-xs text-[#7a8580]">可选，兼容中英文风格标签</span>
          <select value={style} disabled={!category || loading} onChange={(event) => {
            const nextStyle = event.target.value
            setStyle(nextStyle)
            void loadCandidates(category, nextStyle)
          }} className="mt-3 h-11 w-full rounded-md border border-[#cfd6d0] bg-white px-3 text-sm outline-none focus:border-[#28745c] disabled:bg-[#f1f3f0] disabled:text-[#9aa39e]">
            <option value="">不限风格</option>
            {availableStyles.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-4 pb-4">
          <div>
            <h2 className="text-xl font-bold">候选基金 <span className="text-[#28745c]">{recommendations.length}</span> / 10</h2>
            <p className="mt-1 text-xs text-[#79847e]">
              {category ? `完整同类组 ${peerUniverseCount} 只，${evidenceEligibleCount} 只通过关键证据门槛。` : `基金数据库共 ${universeTotal.toLocaleString('zh-CN')} 只，选择类别后开始评价。`}
            </p>
          </div>
          {recommendations.length >= 2 ? (
            <Link href={compareHref} className="inline-flex h-10 items-center gap-2 rounded-md border border-[#9ab3a8] px-4 text-sm font-bold text-[#285d4b] hover:bg-[#edf4f0]">
              <GitCompareArrows className="h-4 w-4" />比较前 {Math.min(6, recommendations.length)} 只
            </Link>
          ) : null}
        </div>

        {loading ? (
          <div className="flex min-h-52 items-center justify-center gap-3 border border-dashed border-[#cbd3cd] bg-white text-sm text-[#66726c]">
            <LoaderCircle className="h-5 w-5 animate-spin text-[#28745c]" />正在读取同类专业评价
          </div>
        ) : !category ? (
          <div className="flex min-h-52 flex-col items-center justify-center border border-dashed border-[#cbd3cd] bg-white px-6 text-center">
            <Tags className="h-6 w-6 text-[#28745c]" />
            <strong className="mt-3 text-sm">先选择一个基金类别</strong>
            <span className="mt-2 text-xs leading-6 text-[#78837d]">系统不会在股票、债券、货币和指数基金之间进行横向排名。</span>
          </div>
        ) : recommendations.length === 0 ? (
          <div className="flex min-h-52 flex-col items-center justify-center border border-dashed border-[#cbd3cd] bg-white px-6 text-center">
            <CircleAlert className="h-6 w-6 text-[#9a7a3a]" />
            <strong className="mt-3 text-sm">当前类别没有可用的专业评价结果</strong>
            <span className="mt-2 text-xs leading-6 text-[#78837d]">可取消风格限制，或先补齐基金分类、基准、净值和同类样本数据。</span>
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {recommendations.map((fund, index) => {
              const annualReturn = returnMetric(fund)
              const drawdown = drawdownMetric(fund)
              const score = professionalFundScore(fund)
              const percentile = professionalScorePercentile(fund)
              const evidence = recommendationEvidence(fund)
              return (
                <article key={fund.windCode} className="grid grid-cols-[2.6rem_minmax(0,1fr)] gap-4 border border-[#dbe1dc] bg-white p-5 transition hover:border-[#90ad9f]">
                  <div className="grid h-10 w-10 place-items-center rounded-md bg-[#edf2ee] text-sm font-black text-[#32614f]">{String(index + 1).padStart(2, '0')}</div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <Link href={`/funds/${encodeURIComponent(fund.windCode)}`} className="font-bold text-[#1b2923] hover:text-[#28745c]">{fund.name || fund.windCode}</Link>
                        <p className="mt-1 text-xs text-[#7a8580]">{fund.windCode} · {managerName(fund)}</p>
                      </div>
                      <div className="text-right">
                        <span className="block text-[11px] text-[#7a8580]">同类专业评分</span>
                        <strong className="mt-1 block text-xl text-[#24664f]">{score?.toFixed(1) || '—'}</strong>
                        {percentile != null ? <span className="mt-1 block text-[11px] text-[#7a8580]">同类分位 {percentile.toFixed(0)}</span> : null}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-sm bg-[#e9f0ec] px-2 py-1 text-[#315e4d]">{peerGroup(fund)}</span>
                      <span className="rounded-sm bg-[#f0eee8] px-2 py-1 text-[#685f49]">{styleLabel(fund)}</span>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-3 border-y border-[#edf0ed] py-3 text-xs">
                      <div><span className="block text-[#7a8580]">近 1 年</span><strong className="mt-1 block">{formatPercent(annualReturn)}</strong></div>
                      <div><span className="block text-[#7a8580]">最大回撤</span><strong className="mt-1 block">{formatPercent(drawdown)}</strong></div>
                      <div><span className="block text-[#7a8580]">基金规模</span><strong className="mt-1 block">{formatAsset(fund.totalAsset)}</strong></div>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs leading-5 text-[#66726c]">
                      <div className="flex gap-2">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#2d7b5e]" />
                        <span><strong className="text-[#345e4e]">入选依据：</strong>{evidence.reasons.join('；')}</span>
                      </div>
                      <div className="flex gap-2">
                        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[#a07837]" />
                        <span><strong className="text-[#775e32]">主要风险：</strong>{evidence.risks.join(' ')}</span>
                      </div>
                    </div>
                    <p className="mt-3 text-[11px] text-[#89928d]">数据截至 {evidence.dataAsOf || fund.navDate || '待补'} · 仅在“{category}”同类组内评价</p>
                    <Link href={`/funds/${encodeURIComponent(fund.windCode)}`} className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-[#28745c]">查看基金与风险 <ArrowRight className="h-3.5 w-3.5" /></Link>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
