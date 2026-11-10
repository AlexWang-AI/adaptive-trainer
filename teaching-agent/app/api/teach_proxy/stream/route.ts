import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

type StreamBody = {
  action?: 'turn' | 'answer'
  kp_id?: string | null
  student_id?: string
  topic?: string
  level?: string
  subject?: string
  prior_knowledge?: string
  misconceptions?: string
  student_message?: string
  focus?: string
  max_rounds?: number
  [key: string]: unknown
}

/**
 * 流式代理：把浏览器与 Python 后端的 SSE 原样对接。
 *
 * 不能用 NextResponse.json，那会把流读完再发；这里直接把 upstream.body 透传，
 * 保证「首字」在浏览器端按真实时间到达。
 */
export async function POST(request: Request) {
  let body: StreamBody
  try {
    body = (await request.json()) as StreamBody
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }

  if ((body.action ?? 'turn') !== 'turn') {
    return NextResponse.json({ error: 'v3 流式只支持 action=turn；判题走 /api/judge' }, { status: 400 })
  }

  const payload = {
    kp_id: body.kp_id ?? null,
    history: Array.isArray(body.history) ? body.history : [],
    student_message: body.student_message ?? '',
    student_id: body.student_id ?? 'local-user',
    topic: body.topic ?? null,
    level: body.level ?? '大学低年级',
    subject: body.subject ?? '数学一',
    prior_knowledge: body.prior_knowledge ?? '',
    misconceptions: body.misconceptions ?? '',
    focus: body.focus ?? '',
    max_rounds: body.max_rounds ?? 3,
  }

  try {
    const t0 = Date.now()
    const upstream = await fetch(`${AGENT_API_URL}/api/teach_stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
      cache: 'no-store',
    })
    console.error(`[teach_stream] upstream headers in ${Date.now() - t0}ms status=${upstream.status}`)

    if (!upstream.ok || !upstream.body) {
      const text = await upstream.text().catch(() => '')
      return NextResponse.json(
        { error: text.slice(0, 600) || `教学服务 ${upstream.status}` },
        { status: upstream.status || 502 },
      )
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json(
      { error: `教学服务未连接（${AGENT_API_URL}）：${message}。请先启动 api_server。` },
      { status: 502 },
    )
  }
}

/** 预热：页面挂载时打一下，让 dev 先编译好这个路由，避免用户第一次点击等 4~6 秒。 */
export async function GET() {
  return new Response('stream-route-ready', {
    status: 200,
    headers: { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' },
  })
}
