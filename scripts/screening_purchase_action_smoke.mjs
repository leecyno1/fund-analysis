import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))

function read(relativePath) {
  const fullPath = join(root, relativePath)
  if (!existsSync(fullPath)) {
    throw new Error(`Missing required file: ${relativePath}`)
  }
  return readFileSync(fullPath, 'utf8')
}

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) {
    throw new Error(`${label} missing text: ${expected}`)
  }
}

function assertNotIncludes(content, unexpected, label) {
  if (content.includes(unexpected)) {
    throw new Error(`${label} should not include stale text: ${unexpected}`)
  }
}

const screeningPage = read('app/(dashboard)/screening/page.tsx')

assertIncludes(screeningPage, 'screening-purchase-action-queue', 'screening purchase action queue')
assertIncludes(screeningPage, '筛选结果研究行动队列', 'screening purchase action queue title')
assertIncludes(screeningPage, '筛选只给出研究对象', 'screening purchase action queue scope')
assertIncludes(screeningPage, 'screeningPurchaseActionQueue', 'screening structured purchase action queue')
assertIncludes(screeningPage, 'screeningPurchaseQueueSummary', 'screening purchase action summary')
assertIncludes(screeningPage, "pickBrowserParam('purchasePlan'", 'screening initializes purchase-plan context from URL')
assertIncludes(screeningPage, 'setPlannedAmount(normalizePlannedAmountInput', 'screening hydrates planned amount context from browser URL')
assertIncludes(screeningPage, 'body: JSON.stringify({ ...screeningCriteria, purchasePlan, plannedAmount: currentPlannedAmount() })', 'screening execution sends purchase plan and planned amount into screening API')
assertIncludes(screeningPage, 'salesRulesHrefForCodes', 'screening central sales-rule href builder')
assertIncludes(screeningPage, 'new URLSearchParams({ purchasePlan, plannedAmount: String(currentPlannedAmount()) })', 'screening sales-rule href carries purchase plan and planned amount')
assertIncludes(screeningPage, 'salesRulesHrefForCodes([fund.windCode])', 'screening per-fund sales-rule href carries purchase plan')
assertIncludes(screeningPage, 'rankingsHref', 'screening ranking entry preserves purchase context')
assertIncludes(screeningPage, 'plannedAmount: String(currentPlannedAmount())', 'screening sales-rule gap scan uses planned amount context')
assertIncludes(screeningPage, "fetch('/api/evidence-coverage/review-events'", 'screening material evidence gap scan reads review queue')
assertIncludes(screeningPage, "event.event_type === 'sales_rule_evidence' && event.status !== 'resolved'", 'screening blocks active sales-rule review alerts')
assertIncludes(screeningPage, '复查队列未解决', 'screening active review alert missing item')
assertIncludes(screeningPage, "gateSource: 'local.alert_events.sales_rule_evidence'", 'screening active review alert gate source')
assertIncludes(screeningPage, 'reviewAlertBlocked', 'screening active review alert blocker flag')
assertIncludes(screeningPage, '复查队列补证', 'screening action queue review alert label')
assertIncludes(screeningPage, '开复查队列', 'screening routes review alert rows to review queue')
assertIncludes(screeningPage, '处理复查队列', 'screening summary routes active review alerts to review queue')
assertIncludes(screeningPage, '补规则', 'screening purchase action sales-rule action')
assertIncludes(screeningPage, '基金诊断', 'screening purchase action fund detail action')
assertIncludes(screeningPage, '加入横评', 'screening purchase action comparison action')
assertIncludes(screeningPage, '销售规则硬缺口或复查队列未清零前，不生成正式研究复核报告', 'screening hard gate guardrail includes review queue')
assertIncludes(screeningPage, '筛选留痕：第', 'screening pool evidence latest conclusion')
assertIncludes(screeningPage, 'screeningDecision', 'screening pool evidence stores decision')
assertIncludes(screeningPage, 'plannedAmountLabel', 'screening pool evidence stores planned amount label')
assertIncludes(screeningPage, 'plannedAmount: currentPlannedAmount()', 'screening pool save sends planned amount')
assertIncludes(screeningPage, 'criteriaSummary', 'screening pool evidence stores criteria summary')
assertIncludes(screeningPage, 'hardBoundary', 'screening pool evidence keeps hard boundary')
assertIncludes(screeningPage, 'latestConclusion: candidateEvidence.latestConclusion', 'screening pool save uses evidence conclusion')
assertNotIncludes(screeningPage, '进入观察池继续做研究复核一页纸、同类横向比较和销售规则人工复核。', 'screening removes generic pool conclusion')

console.log('OK screening page turns filter results into research action queue')
