import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/** 思路诊断：学生口述/文字描述自己的思路 → 定位最早出错的一步 → 落错题本。 */
export async function POST(request: Request) {
  let body: {
    kp_id?: string
    kp_name?: string
    question?: string
    student_answer?: string
    reasoning?: string
  }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }
  if (!body?.question || !body?.reasoning?.trim()) {
    return NextResponse.json({ error: '缺少 question 或 reasoning' }, { status: 400 })
  }

  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/diagnose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kp_id: body.kp_id ?? '',
        kp_name: body.kp_name ?? '',
        question: body.question,
        student_answer: body.student_answer ?? '',
        reasoning: body.reasoning,
      }),
      cache: 'no-store',
    })
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: `诊断服务未连接：${message}` }, { status: 502 })
  }
}
