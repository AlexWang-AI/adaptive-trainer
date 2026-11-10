import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

type JudgeBody = {
  question: Record<string, unknown>
  answer: string
  allow_llm?: boolean
  kp_id?: string
  kp_name?: string
  student_id?: string
  answer_key?: string
  attempt_id?: string
  question_id?: string
}

/** 单题判分：走后端 SymPy 五层判定，本地毫秒级，不消耗 token。 */
export async function POST(request: Request) {
  let body: JudgeBody
  try {
    body = (await request.json()) as JudgeBody
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }
  if (!body?.question || typeof body.answer !== 'string') {
    return NextResponse.json({ error: '缺少 question 或 answer' }, { status: 400 })
  }

  try {
    const upstream = await fetch(`${AGENT_API_URL}/api/judge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: body.question,
        answer: body.answer,
        allow_llm: Boolean(body.allow_llm),
        kp_id: body.kp_id ?? '',
        kp_name: body.kp_name ?? '',
        student_id: body.student_id ?? 'local-user',
        answer_key: body.answer_key,
        attempt_id: body.attempt_id,
        question_id: body.question_id,
      }),
      cache: 'no-store',
    })
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: `判题服务未连接：${message}` }, { status: 502 })
  }
}
