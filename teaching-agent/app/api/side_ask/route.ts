import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/** 侧边提问：独立上下文，不写主会话历史。 */
export async function POST(request: Request) {
  let body: { ask?: string; question?: string; lesson?: string; history?: unknown[] }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }
  if (!body?.ask?.trim()) return NextResponse.json({ error: '缺少 ask' }, { status: 400 })

  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/side_ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ask: body.ask,
        question: body.question ?? '',
        lesson: body.lesson ?? '',
        history: body.history ?? [],
      }),
      cache: 'no-store',
    })
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: `侧问服务未连接：${message}` }, { status: 502 })
  }
}
