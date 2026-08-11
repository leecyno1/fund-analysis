import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import {
  fundResearchWorkspaceById,
  isFundResearchWorkspace,
  type FundSelection,
} from '@/lib/newma-desk/context'
import FundResearchDeskModule from './FundResearchDeskModule'

export const dynamic = 'force-dynamic'

export async function generateMetadata({
  params,
}: {
  params: Promise<{ workspace: string }>
}): Promise<Metadata> {
  const { workspace } = await params
  if (!isFundResearchWorkspace(workspace)) return { title: '基金研究模组' }
  const config = fundResearchWorkspaceById(workspace)
  return {
    title: `${config.title} · 基金研究模组`,
    description: config.purpose,
  }
}

function firstParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value
}

export default async function FundResearchWorkspacePage({
  params,
  searchParams,
}: {
  params: Promise<{ workspace: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const [{ workspace }, query] = await Promise.all([params, searchParams])
  if (!isFundResearchWorkspace(workspace)) notFound()

  const symbol = firstParam(query.symbol)?.trim().toUpperCase().slice(0, 24)
  const assetType = firstParam(query.assetType) === 'etf' ? 'etf' : 'fund'
  const initialSelection: FundSelection | null = symbol
    ? {
      symbol,
      name: firstParam(query.name)?.trim().slice(0, 80),
      assetType,
    }
    : null
  return (
    <FundResearchDeskModule
      key={`${workspace}:${symbol ?? 'none'}:${assetType}`}
      workspace={fundResearchWorkspaceById(workspace)}
      initialSelection={initialSelection}
    />
  )
}
