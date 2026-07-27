const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:3003'

const checks = [
  '/',
  '/research',
  '/funds',
  '/funds/520680.SH',
  '/managers',
  '/barra',
  '/brinson',
  '/api/funds?page=1&page_size=2',
  '/api/research-reports?page=1',
  '/api/managers?page=1&page_size=2',
  '/api/barra/exposure/000001.OF',
  '/api/brinson/attribution/000001.OF?benchmark=000300',
]

for (const path of checks) {
  const url = new URL(path, baseUrl).toString()
  const response = await fetch(url)
  if (!response.ok) {
    console.error(`Expected ${url} to return 200, got ${response.status}`)
    process.exit(1)
  }
}

console.log(`OK ${checks.length} routes ${baseUrl}`)
