import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) throw new Error(`${label}: missing ${expected}`)
}

const page = read('app/(dashboard)/research/ResearchLibraryClient.tsx')
const backendMain = read('backend/main.py')

for (const expected of [
  '本地文件夹路径',
  '扫描更新',
  '上次扫描',
  '新增',
  '已更新',
  '未变化',
  '失败',
  '待确认',
  '确认',
  '拒绝',
  '来源原文',
]) {
  assertIncludes(page, expected, 'research library user flow')
}

for (const expected of [
  "fetch('/api/research-folders'",
  '/scan`, { method: \'POST\' }',
  "fetch('/api/research-folders/reviews'",
  "method: 'PATCH'",
]) {
  assertIncludes(page, expected, 'research library API wiring')
}

assertIncludes(backendMain, 'research_folders', 'backend registers local folder routes')

for (const route of [
  'app/api/research-folders/route.ts',
  'app/api/research-folders/[folderId]/scan/route.ts',
  'app/api/research-folders/reviews/route.ts',
  'app/api/research-folders/reviews/[reportId]/[proposalId]/route.ts',
]) {
  if (!fs.existsSync(path.join(root, route))) throw new Error(`missing Next.js API bridge: ${route}`)
}

if (/webkitdirectory|type="file"|\.doc\b/u.test(page)) {
  throw new Error('research library should use durable server-side folder indexing and must not advertise legacy .doc parsing')
}

console.log('OK research library exposes durable scan status and evidence review workflow')
