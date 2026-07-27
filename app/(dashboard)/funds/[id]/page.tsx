import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'
import { normalizeFundReports } from '@/lib/fund-report-normalizer'
import { buyEvidenceTool } from '@/lib/research-platform/tools'
import { fetchActiveSalesRuleEvidenceAlertForCode } from '@/lib/sales-rule-review-alerts'
import { getMergedSalesRule } from '@/lib/sales-rules'
import FundDetailClient from './FundDetailClient'

const PEER_PERCENTILE_PAGE_TIMEOUT_MS = 5000

export default async function FundDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const { id } = await params
  const query = await searchParams
  let initialFund = null

  const queryValue = (value: string | string[] | undefined) => Array.isArray(value) ? value[0] : value
  const pick = <T extends string>(value: string | string[] | undefined, validValues: readonly T[], fallback: T) => {
    const raw = queryValue(value)
    return validValues.includes(raw as T) ? raw as T : fallback
  }
  const positiveText = (value: string | string[] | undefined, fallback: string) => {
    const raw = queryValue(value)
    if (!raw) return fallback
    const parsed = Number(raw)
    return Number.isFinite(parsed) && parsed > 0 ? raw : fallback
  }
  const initialPurchasePlan = pick(query.purchasePlan, ['lump_sum', 'sip'] as const, 'sip')
  const plannedAmountFallback = positiveText(query.plannedAmount, initialPurchasePlan === 'lump_sum' ? '10000' : '1000')
  const initialInvestorContext = {
    profile: pick(query.profile, ['conservative', 'balanced', 'aggressive'] as const, 'balanced'),
    horizon: pick(query.horizon, ['lt1y', '1to3y', 'gt3y'] as const, '1to3y'),
    purchasePlan: initialPurchasePlan,
    months: positiveText(query.months, '12'),
    lumpSumAmount: positiveText(query.lumpSumAmount, initialPurchasePlan === 'lump_sum' ? plannedAmountFallback : '10000'),
    monthlyAmount: positiveText(query.monthlyAmount, initialPurchasePlan === 'sip' ? plannedAmountFallback : '1000'),
  }
  const rawReturnTo = queryValue(query.returnTo)
  const initialReturnTo = rawReturnTo?.startsWith('/') && !rawReturnTo.startsWith('//') ? rawReturnTo : '/funds'

  try {
    const response = await fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(id)}`, {
      cache: 'no-store',
    })
    const payload = await response.json()

    if (response.ok) {
      const fund = toCamelFund(payload.fund ? payload.fund : payload)
      const fundWithReports = {
        ...fund,
        aiReports: normalizeFundReports(fund.aiReports),
      }
      let salesRule = null
      let activeSalesRuleEvidenceAlert = null
      if (fundWithReports.windCode) {
        try {
          salesRule = await getMergedSalesRule(fundWithReports.windCode)
        } catch (salesRuleError) {
          console.warn('预取销售规则失败:', salesRuleError)
        }
        try {
          activeSalesRuleEvidenceAlert = await fetchActiveSalesRuleEvidenceAlertForCode(fundWithReports.windCode)
        } catch (alertError) {
          console.warn('预取销售规则复查事件失败:', alertError)
        }
      }
      let peerPercentiles = null
      if (fundWithReports.windCode) {
        try {
          const peerResponse = await fetch(
            `${backendApiBaseUrl}/api/funds/${encodeURIComponent(fundWithReports.windCode)}/peer-percentiles?window=1y`,
            { cache: 'no-store', signal: AbortSignal.timeout(PEER_PERCENTILE_PAGE_TIMEOUT_MS) },
          )
          if (peerResponse.ok) {
            peerPercentiles = await peerResponse.json()
          }
        } catch (peerError) {
          console.warn('预取同类分位失败:', peerError)
        }
      }
      initialFund = {
        ...fundWithReports,
        salesRule,
        activeSalesRuleEvidenceAlert,
        peerPercentiles,
        buyEvidence: buyEvidenceTool.run({
          fund: {
            ...fundWithReports,
            salesRule,
          },
          purchasePlan: initialInvestorContext.purchasePlan,
          plannedAmount: initialInvestorContext.purchasePlan === 'lump_sum'
            ? initialInvestorContext.lumpSumAmount
            : initialInvestorContext.monthlyAmount,
        }).data,
      }
    }
  } catch (error) {
    console.error('预取基金详情失败:', error)
  }

  return <FundDetailClient fundId={id} initialFund={initialFund} initialInvestorContext={initialInvestorContext} initialReturnTo={initialReturnTo} />
}
