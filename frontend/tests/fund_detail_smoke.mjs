const url = process.env.FUND_DETAIL_URL || 'http://127.0.0.1:3003/funds/520680.SH'

const response = await fetch(url)

if (!response.ok) {
  console.error(`Expected ${url} to return 200, got ${response.status}`)
  process.exit(1)
}

console.log(`OK ${response.status} ${url}`)
