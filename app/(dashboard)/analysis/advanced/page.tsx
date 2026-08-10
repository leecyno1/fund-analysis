import AttributionWorkspace from './AttributionWorkspace'

function latestCompletedQuarter() {
  const now = new Date()
  const currentQuarter = Math.floor(now.getMonth() / 3) + 1
  return currentQuarter === 1 ? `${now.getFullYear() - 1}Q4` : `${now.getFullYear()}Q${currentQuarter - 1}`
}

export default async function PerformanceAttributionPage({
  searchParams,
}: {
  searchParams: Promise<{ fundCode?: string; benchmark?: string; quarter?: string }>
}) {
  const query = await searchParams
  return (
    <AttributionWorkspace
      initialFundCode={query.fundCode || '000051.OF'}
      initialBenchmark={query.benchmark || '000300.SH'}
      initialQuarter={query.quarter || latestCompletedQuarter()}
    />
  )
}
