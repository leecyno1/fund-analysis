import { existsSync, readFileSync } from 'node:fs'
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

function assertNotIncludes(content, unexpected, label) {
  if (content.includes(unexpected)) throw new Error(`${label} should not include stale manager copy: ${unexpected}`)
}

const managerList = read('app/(dashboard)/managers/page.tsx')
const managerDetail = read('app/(dashboard)/managers/[id]/page.tsx')
const reportsPage = read('app/(dashboard)/reports/page.tsx')

for (const expected of [
  '经理列表研究复核雷达',
  '经理研究补证优先队列',
  '经理入口短名单分',
  '经理评价只负责缩小研究对象',
  '材料核验完整度',
  '研究方式假设',
]) {
  assertIncludes(managerList, expected, `manager page uses research term ${expected}`)
}

for (const expected of [
  '研究复核场景',
  '经理入口研究评级',
  '经理研究证据卡',
  '名下基金研究队列',
  '研究方式假设',
]) {
  assertIncludes(managerDetail, expected, `manager detail uses research term ${expected}`)
}

for (const expected of [
  '研究复核',
  '研究总闸门',
  '研究补证队列',
  '研究复核报告',
  '研究方式假设',
]) {
  assertIncludes(reportsPage, expected, `reports page uses research term ${expected}`)
}

for (const staleCopy of [
  '买前',
  '买入',
  '购买',
  '交易',
  '投资者',
  '可买',
  '可购买候选',
  '购买候选',
  '正式购买',
  '一次性买入',
]) {
  assertNotIncludes(managerList, staleCopy, 'manager research semantics')
  assertNotIncludes(managerDetail, staleCopy, 'manager detail research semantics')
  assertNotIncludes(reportsPage, staleCopy, 'reports research semantics')
}

console.log('OK manager and report pages use canonical research semantics without legacy buy language')
