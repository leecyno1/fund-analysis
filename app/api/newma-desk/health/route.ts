import { NextResponse } from 'next/server'
import { PROFESSIONAL_METHODOLOGY_VERSION, professionalResearchStages } from '@/lib/fund-research'

export const dynamic = 'force-dynamic'

export function GET() {
  return NextResponse.json({
    ok: true,
    service: 'fund-research-data',
    methodologyVersion: PROFESSIONAL_METHODOLOGY_VERSION,
    stageCount: professionalResearchStages.length,
    bridgeProtocol: '1.0',
    viewSpecVersion: '1.0',
    asOf: new Date().toISOString(),
  })
}
