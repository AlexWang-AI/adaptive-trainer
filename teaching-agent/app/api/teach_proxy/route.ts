import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

type ProxyBody = {
  action?: 'turn' | 'answer'
  [key: string]: unknown
}

function stripOptionPrefix(option: string) {
  return String(option).replace(/^\s*[A-Da-d]\s*[.、,:：)）]\s*/, '').trim()
}

function normalizePayload(raw: Record<string, unknown>) {
  const teaching = (raw.teaching ?? null) as Record<string, unknown> | null
  const rawQuiz = (raw.quiz ?? null) as Record<string, unknown> | null
  const rawQuizCard = (raw.quiz_card ?? null) as Record<string, unknown> | null

  const options = Array.isArray(rawQuiz?.options)
    ? (rawQuiz.options as unknown[]).map((option, index) => `${String.fromCharCode(65 + index)}. ${stripOptionPrefix(String(option))}`)
    : Array.isArray(rawQuizCard?.options)
      ? (rawQuizCard.options as unknown[]).map((option) => String(option))
      : []

  const quiz_card = rawQuizCard
    ? {
        question: String(rawQuizCard.question ?? ''),
        options: Array.isArray(rawQuizCard.options) ? rawQuizCard.options.map(String) : [],
        answer: String(rawQuizCard.answer ?? ''),
      }
    : rawQuiz
      ? {
          question: String(rawQuiz.stem ?? ''),
          options,
          answer: String(rawQuiz.answer ?? ''),
        }
      : null

  return {
    session_id: String(raw.session_id ?? ''),
    status: String(raw.status ?? 'error'),
    round: Number(raw.round ?? 0),
    max_rounds: Number(raw.max_rounds ?? 5),
    teaching_content: String(raw.teaching_content ?? teaching?.reply_markdown ?? ''),
    thinking: String(raw.thinking ?? teaching?.order_rationale ?? ''),
    thinking_seconds: Number(raw.thinking_seconds ?? 0),
    quiz_card,
    judgement: raw.judgement ?? null,
    error: raw.error ?? null,
  }
}

export async function POST(request: Request) {
  let body: ProxyBody
  try {
    body = (await request.json()) as ProxyBody
  } catch {
    return NextResponse.json({ error: '无效请求体' }, { status: 400 })
  }

  const action = body.action
  if (action !== 'turn' && action !== 'answer') {
    return NextResponse.json(
      { error: 'action 必须是 turn 或 answer' },
      { status: 400 },
    )
  }

  const endpoint = action === 'turn' ? '/api/teach_turn' : '/api/teach_answer'
  const { action: _action, ...payload } = body

  try {
    const response = await fetch(`${AGENT_API_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      cache: 'no-store',
    })
    const text = await response.text()
    let raw: Record<string, unknown>
    try {
      raw = JSON.parse(text) as Record<string, unknown>
    } catch {
      return NextResponse.json(
        { error: text.slice(0, 800) || `sidecar ${response.status}` },
        { status: response.status },
      )
    }
    if (!response.ok) {
      return NextResponse.json(
        { error: raw.error ?? raw.detail ?? `sidecar ${response.status}` },
        { status: response.status },
      )
    }
    return NextResponse.json(normalizePayload(raw), { status: 200 })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json(
      { error: `教学 sidecar 未连接（${AGENT_API_URL}）：${message}。请先启动 FastAPI 8008。` },
      { status: 502 },
    )
  }
}
