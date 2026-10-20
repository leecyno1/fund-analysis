const baseUrl = process.env.APP_BASE_URL || process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:3000'

async function requireResponse(path, timeoutMs = 120000) {
  const response = await fetch(`${baseUrl}${path}`, { signal: AbortSignal.timeout(timeoutMs) })
  const text = await response.text()
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${text.slice(0, 300)}`)
  return text
}

const page = await requireResponse('/funds/000309.OF')
if (!page.includes('归因结论（多季 Brinson）')) throw new Error('fund detail page missing attribution conclusion panel')

const payload = JSON.parse(await requireResponse('/api/funds/000309.OF/attribution-conclusion?quarters=2'))
if (!['available', 'insufficient'].includes(payload.status)) {
  throw new Error(`unexpected attribution conclusion status: ${JSON.stringify(payload).slice(0, 300)}`)
}
if (payload.status === 'available') {
  for (const key of ['dominant_source_label', 'conclusion', 'alpha_replicability_label']) {
    if (!payload[key]) throw new Error(`attribution conclusion missing: ${key}`)
  }
  if (!Array.isArray(payload.quarters) || payload.quarters.length < 2) {
    throw new Error(`attribution conclusion quarters missing: ${JSON.stringify(payload.quarters)}`)
  }
  if (!(Number(payload.quarters_used) >= 2)) throw new Error('attribution conclusion quarters_used < 2')
}

console.log(`attribution conclusion smoke passed: status=${payload.status}, quarters=${payload.quarters_used ?? 0}`)
