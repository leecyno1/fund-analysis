import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import ts from 'typescript'

const root = process.cwd()

function read(path) {
  return readFileSync(join(root, path), 'utf8')
}

function json(path) {
  return JSON.parse(read(path))
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function assertIncludes(content, expected, label) {
  assert(content.includes(expected), `${label} missing: ${expected}`)
}

function loadTypeScriptModule(path) {
  const source = read(path)
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: path,
  }).outputText
  const loadedModule = { exports: {} }
  const execute = new Function('module', 'exports', 'require', compiled)
  execute(loadedModule, loadedModule.exports, () => {
    throw new Error(`Unexpected dependency while loading ${path}`)
  })
  return loadedModule.exports
}

const suite = json('desk/suite.json')
const dataService = json('desk/data-service.json')
const view = json('desk/views/fund-research-overview.view.json')
const bridgeSource = read('lib/newma-desk/bridge.ts')
const contextSource = read('lib/newma-desk/context.ts')
const moduleSource = read('app/(desk)/mod/fund-research/[workspace]/FundResearchDeskModule.tsx')
const cockpitSource = read('app/(desk)/mod/fund-research/[workspace]/FundResearchDailyCockpit.tsx')
const cockpitLoader = read('lib/fund-research/cockpit/load-daily-research-cockpit.ts')
const cockpitContract = read('lib/fund-research/contracts/daily-cockpit.ts')
const decisionContract = read('lib/fund-research/contracts/research-decision.ts')
const methodology = read('lib/fund-research/methodology/professional-methodology.ts')
const architecture = read('docs/architecture/professional-fund-research-module-v2.md')
const sources = read('docs/research-methodology/sources.md')
const globalCss = read('app/globals.css')

assert(suite.schemaVersion === '1.0', 'Suite schemaVersion must be 1.0')
assert(suite.id === 'professional-fund-research-suite', 'Suite ID must remain stable')
assert(suite.manifest.schemaVersion === '1.1', 'Compiled manifests must use Manifest 1.1')
assert(suite.manifest.compatibility.level === 3, 'All shared pages must declare Level 3')
assert(suite.manifest.compatibility.bridgeProtocol === '1.0', 'Bridge protocol must be 1.0')
assert(suite.manifest.compatibility.viewSpecVersion === '1.0', 'Level 3 must declare ViewSpec 1.0')
assert(suite.manifest.navigation.project.id === 'professional-fund-research', 'All pages need one stable project identity')
assert(suite.pages.length === 6, 'Professional fund research Suite must expose six pages')

const pageIds = suite.pages.map((page) => page.id)
const pageRoutes = suite.pages.map((page) => page.route)
assert(new Set(pageIds).size === pageIds.length, 'Suite page IDs must be unique')
assert(new Set(pageRoutes).size === pageRoutes.length, 'Suite page routes must be unique')
for (const route of pageRoutes) {
  assert(route.startsWith('/mod/fund-research/'), `Unsafe or unexpected Suite route: ${route}`)
}

const sharedPermissions = new Set(suite.manifest.permissions)
const sharedServices = new Set(suite.manifest.dataServices)
for (const [actionId, action] of Object.entries(suite.manifest.actions)) {
  assert(/^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$/.test(actionId), `Invalid Action ID: ${actionId}`)
  assert(sharedPermissions.has(action.permission), `${actionId} permission is not declared`)
  if (action.binding.type === 'data' && action.binding.service) {
    assert(sharedServices.has(action.binding.service), `${actionId} data service is not declared`)
    assert(dataService.capabilities[action.binding.capability || actionId], `${actionId} capability missing from data-service.json`)
  }
  if (action.binding.type === 'agent') {
    assert(action.execution === 'task', `${actionId} Agent action must use task execution`)
  }
}

for (const page of suite.pages) {
  const manifest = page.manifest || {}
  const permissions = new Set(manifest.permissions || suite.manifest.permissions)
  const storage = manifest.storage || suite.manifest.storage
  for (const action of Object.values(suite.manifest.actions)) {
    assert(permissions.has(action.permission), `${page.id} loses permission required by an inherited Action: ${action.permission}`)
  }
  if (storage?.mode === 'desk-managed') {
    assert(permissions.has('storage.read') && permissions.has('storage.write'), `${page.id} Desk storage permissions are incomplete`)
    const namespaceIds = storage.namespaces.map((namespace) => namespace.id)
    assert(new Set(namespaceIds).size === namespaceIds.length, `${page.id} storage namespaces must be unique`)
  }
}

assert(dataService.id === 'fund-research-data', 'Data service ID must match Suite declaration')
assert(dataService.healthPath === '/newma-desk/health', 'Data service health endpoint must be declared')
assert(!JSON.stringify(suite).match(/DATABASE_URL|api[_-]?key|secret|token/i), 'Suite must not expose credentials')
assert(!JSON.stringify(dataService).match(/DATABASE_URL|api[_-]?key|secret|token/i), 'Data service descriptor must not expose credentials')

assert(view.version === '1.0', 'View must use ViewSpec 1.0')
assert(view.blocks.some((block) => block.type === 'table'), 'ViewSpec must retain machine-readable tables')
assert(view.blocks.some((block) => block.type === 'actions'), 'ViewSpec must expose declared actions')

const bridge = loadTypeScriptModule('lib/newma-desk/bridge.ts')
const hello = bridge.buildHelloMessage('fund-research-overview')
assert(hello.type === 'vibedesk:hello', 'Bridge must start with vibedesk:hello')
assert(hello.capabilities.includes('context') && hello.capabilities.includes('theme'), 'Hello must advertise context and theme')

const init = {
  type: 'vibedesk:init',
  protocolVersion: '1.0',
  instanceId: 'instance-1',
  modId: 'fund-research-overview',
  user: { id: 'user-1' },
  workspace: { id: 'workspace-1' },
  environment: { theme: 'dark', locale: 'zh-CN', timezone: 'Asia/Shanghai' },
  gateways: {
    actions: 'http://127.0.0.1:8911/api/actions',
    agent: 'http://127.0.0.1:8911/api/agent',
    model: 'http://127.0.0.1:8911/api/model',
    data: 'http://127.0.0.1:8911/api/data',
  },
  grants: { permissions: ['research.read'], actions: ['fund.research.explain'] },
}
assert(bridge.isDeskInitMessage(init, 'fund-research-overview'), 'Bridge must validate a correct init message')
assert(!bridge.isDeskInitMessage({ ...init, modId: 'wrong-mod' }, 'fund-research-overview'), 'Bridge must reject a mismatched modId')
const ack = bridge.buildAckMessage(init)
assert(ack.type === 'vibedesk:ack' && ack.instanceId === init.instanceId, 'Bridge must acknowledge the negotiated instance')

const eventPayload = bridge.buildFundSelectionEventPayload({ symbol: ' 000001.of ', name: '示例基金', assetType: 'fund' })
assert(eventPayload.symbol === '000001.OF', 'Fund event symbol must be normalized')
assert(eventPayload.assetType === 'fund' && eventPayload.market === 'CN', 'Fund event must follow security.selected convention')

for (const phrase of [
  'message.source !== window.parent',
  'message.origin !== parentOrigin',
  'vibedesk:context-request',
  'vibedesk:action-request',
  'environment.locale',
  'environment.timezone',
]) assertIncludes(bridgeSource, phrase, 'bridge contract')

for (const phrase of [
  'buildFundResearchPageContext',
  'visibleBlocks',
  'selection:',
  'actions:',
  'methodologyVersion',
  'dailyCockpit',
]) assertIncludes(contextSource, phrase, 'Agent Context')

for (const phrase of [
  'data-vibe-page="1.0"',
  'data-vibe-block-id="professional-workflow"',
  '<table>',
  'security.selected',
  'publishContext',
]) assertIncludes(moduleSource, phrase, 'Level 3 module page')

for (const phrase of [
  'data-vibe-block-id="daily-research-cockpit"',
  'data-vibe-block-id="daily-research-queue"',
  'data-vibe-block-id="evidence-source-health"',
  'data-vibe-block-id="review-events"',
  '不使用合成总分',
]) assertIncludes(cockpitSource, phrase, 'daily research cockpit')

for (const phrase of [
  'getEvidenceCoverage',
  "getSalesRuleGaps('candidate'",
  "fetchBackend('/api/alerts')",
  "fetchBackend('/api/data-health/summary?stale_hours=72')",
  'Promise.allSettled',
]) assertIncludes(cockpitLoader, phrase, 'daily cockpit data aggregation')
assert(!/mock|demo|fixture/i.test(cockpitLoader), 'Daily cockpit loader must not fabricate operational data')
assert(!/overallScore|totalScore|weightedScore/.test(cockpitContract), 'Daily cockpit contract must not introduce a synthetic total score')

assertIncludes(globalCss, '@media (max-width: 540px)', '320px responsive stylesheet')
assertIncludes(globalCss, ':root[data-theme="dark"]', 'Desk theme stylesheet')

for (const stageId of [
  'universe-identity', 'evidence-quality', 'peer-benchmark', 'quantitative-evaluation',
  'holdings-style', 'qualitative-due-diligence', 'decision-governance', 'monitoring', 'methodology-audit',
]) assertIncludes(methodology, stageId, 'professional methodology stages')

for (const sourceId of [
  'fama-french-2010', 'carhart-1997', 'cremers-petajisto-2009', 'berk-van-binsbergen-2015',
  'sharpe-1992', 'cfa-manager-selection-2026', 'morningstar-medalist-2026', 'csrc-fund-evaluation-rules',
]) assertIncludes(methodology, sourceId, 'methodology sources')

assertIncludes(decisionContract, 'evaluateResearchReadiness', 'decision gate evaluator')
assert(!/overallScore|totalScore|weightedScore/.test(decisionContract), 'Professional decision contract must not contain a synthetic total score')
assertIncludes(architecture, 'Gates + Pillars + Confidence', 'canonical architecture')
assertIncludes(sources, 'Fama & French', 'research source document')
assertIncludes(sources, '中国证监会', 'regulatory source document')

console.log('OK professional fund research Suite passes Newma-Desk Level 3 contract smoke checks')
