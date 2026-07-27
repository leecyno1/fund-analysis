import { randomUUID } from 'crypto'
import { NextResponse } from 'next/server'
import postgres from 'postgres'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const sql = postgres(process.env.DATABASE_URL || '', { max: 1 })

type ScreeningTemplateRow = {
  id: string
  name: string
  description: string | null
  criteria: unknown
  created_by: string | null
  is_public: boolean
  created_at: string
  updated_at: string
}

function toTemplate(row: ScreeningTemplateRow) {
  return {
    id: row.id,
    name: row.name,
    description: row.description,
    criteria: row.criteria,
    createdBy: row.created_by,
    isPublic: row.is_public,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export async function GET() {
  try {
    const rows = await sql<ScreeningTemplateRow[]>`
      SELECT
        id,
        name,
        description,
        criteria,
        created_by,
        is_public,
        created_at::text,
        updated_at::text
      FROM screening_criteria
      ORDER BY created_at DESC
      LIMIT 100
    `

    return NextResponse.json({ data: rows.map(toTemplate), source: 'local.postgres.screening_criteria' })
  } catch (error) {
    console.error('获取筛选模板失败:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '获取筛选模板失败' },
      { status: 500 },
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({})) as {
      name?: unknown
      description?: unknown
      criteria?: unknown
    }
    const name = typeof body.name === 'string' ? body.name.trim() : ''
    const description = typeof body.description === 'string' ? body.description.trim() : null
    const criteria = body.criteria && typeof body.criteria === 'object' ? body.criteria : null

    if (!name || !criteria) {
      return NextResponse.json(
        { error: '请提供模板名称和筛选条件' },
        { status: 400 },
      )
    }

    const rows = await sql<ScreeningTemplateRow[]>`
      INSERT INTO screening_criteria (
        id,
        name,
        description,
        criteria,
        created_at,
        updated_at
      ) VALUES (
        ${randomUUID()},
        ${name},
        ${description},
        CAST(${JSON.stringify(criteria)} AS jsonb),
        NOW(),
        NOW()
      )
      RETURNING
        id,
        name,
        description,
        criteria,
        created_by,
        is_public,
        created_at::text,
        updated_at::text
    `

    return NextResponse.json(toTemplate(rows[0]), { status: 201 })
  } catch (error) {
    console.error('创建筛选模板失败:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '创建筛选模板失败' },
      { status: 500 },
    )
  }
}
