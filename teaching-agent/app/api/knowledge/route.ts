import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

export async function GET(request: Request) {
  const url = new URL(request.url)
  const studentId = url.searchParams.get('student_id') || 'local-user'
  try {
    const upstream = await fetch(
      `${AGENT_API_URL}/api/curriculum?student_id=${encodeURIComponent(studentId)}`,
      { cache: 'no-store' },
    )
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json(
      { error: `知识树服务未连接：${message}`, chapters: [], progress: { total: 0, mastered: 0, ratio: 0 } },
      { status: 502 },
    )
  }
}

export async function POST(request: Request) {
  let body: { kp_id?: string; student_id?: string; score?: number }
  try {
    body = (await request.json()) as typeof body
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }
  if (!body.kp_id) {
    return NextResponse.json({ error: '缺少 kp_id' }, { status: 400 })
  }
  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/mastery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kp_id: body.kp_id,
        student_id: body.student_id ?? 'local-user',
        score: body.score ?? null,
      }),
      cache: 'no-store',
    })
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: `标记通关失败：${message}` }, { status: 502 })
  }
}
