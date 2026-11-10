import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

export async function GET() {
  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/review/due?limit=20`, { cache: 'no-store' })
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message, items: [], count: 0 }, { status: 502 })
  }
}

export async function POST(request: Request) {
  let body: { kp_id?: string; correct?: boolean }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }
  if (!body?.kp_id) return NextResponse.json({ error: '缺少 kp_id' }, { status: 400 })
  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/review/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kp_id: body.kp_id, correct: Boolean(body.correct) }),
      cache: 'no-store',
    })
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message }, { status: 502 })
  }
}
