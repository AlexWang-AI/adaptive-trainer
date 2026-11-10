import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/** 再练一组：同知识点只出 3 道题，不重讲。 */
export async function POST(request: Request) {
  let body: { kp_id?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }
  if (!body?.kp_id) return NextResponse.json({ error: '缺少 kp_id' }, { status: 400 })
  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/practice_more`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kp_id: body.kp_id }),
      cache: 'no-store',
    })
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message }, { status: 502 })
  }
}
