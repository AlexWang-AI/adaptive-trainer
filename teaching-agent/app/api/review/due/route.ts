import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/** 与 /api/review 等价的只读入口，路径对齐后端。 */
export async function GET() {
  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/review/due?limit=50`, { cache: 'no-store' })
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message, items: [], count: 0 }, { status: 502 })
  }
}
