import type { ResearchPipeline } from './SimpleFundDetailClient'

const statusDot: Record<ResearchPipeline['steps'][number]['status'], string> = {
  ready: 'bg-[#2f7a5b]',
  partial: 'bg-[#b8860b]',
  blocked: 'bg-[#b23a3a]',
}

const statusLabel: Record<ResearchPipeline['steps'][number]['status'], string> = {
  ready: '就绪',
  partial: '部分',
  blocked: '缺失',
}

function formatCapture(value: number | null) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function formatRate(value: number | null) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

export default function ResearchPipelinePanel({ pipeline }: { pipeline: ResearchPipeline }) {
  if (!pipeline || !Array.isArray(pipeline.steps) || pipeline.steps.length === 0) return null
  return (
    <section className="rounded-2xl border border-[#e3e0d5] bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#18231e]">研究流水线</h2>
          <p className="mt-1 text-xs text-[#68746e]">
            身份识别 → 业绩拆解 → 收益来源 → 持仓追踪 → 同类定位 → 异常点 → 结论。已就绪 {pipeline.readyCount}/{pipeline.total} 步。
          </p>
        </div>
        {pipeline.firstGap ? (
          <span className="rounded-full bg-[#f6f1e4] px-3 py-1 text-xs text-[#8d6a2f]">
            优先补：{pipeline.firstGap.label}{pipeline.firstGap.gap ? `（${pipeline.firstGap.gap}）` : ''}
          </span>
        ) : null}
      </div>
      <ol className="mt-5 space-y-1">
        {pipeline.steps.map((step) => (
          <li key={step.key} className="flex items-start gap-3 rounded-lg px-3 py-2.5 hover:bg-[#faf9f5]">
            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${statusDot[step.status]}`} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-sm font-semibold text-[#18231e]">
                  {step.order}. {step.label}
                </span>
                <span className="text-xs text-[#68746e]">{statusLabel[step.status]}</span>
                {step.capture ? (
                  <span className="text-xs text-[#173f35]">
                    上行捕获 {formatCapture(step.capture.up)} / 下行捕获 {formatCapture(step.capture.down)}
                  </span>
                ) : null}
                {step.regime ? (
                  <span className="text-xs text-[#315e4d]">
                    牛市胜率 {formatRate(step.regime.bullWinRate)} / 熊市胜率 {formatRate(step.regime.bearWinRate)}
                  </span>
                ) : null}
                {step.returnSource ? (
                  <span className="text-xs text-[#4a5560]">
                    收益来源：{step.returnSource.classificationLabel}
                    {step.returnSource.beta != null ? `（β ${step.returnSource.beta.toFixed(2)}）` : ''}
                    {step.returnSource.replicabilityLabel ? ` · ${step.returnSource.replicabilityLabel}` : ''}
                  </span>
                ) : null}
              </div>
              <p className="mt-0.5 text-xs leading-6 text-[#4a5560]">{step.summary}</p>
              {step.gap ? <p className="mt-0.5 text-xs leading-6 text-[#8d6a2f]">{step.gap}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
