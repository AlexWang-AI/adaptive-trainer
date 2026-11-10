import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/**
 * 学习画像预览：这一讲会注入给模型的「跨会话记忆」。
 * 只读、不花 token，用来验收「按掌握度调整讲解」真的生效（P1-4）。
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const kpId = url.searchParams.get('kp_id') || ''
  const studentId = url.searchParams.get('student_id') || 'local-user'
  try {
    const upstream = await fetch(
      `${AGENT_API_URL}/api/learner_note?kp_id=${encodeURIComponent(kpId)}&student_id=${encodeURIComponent(studentId)}`,
      { cache: 'no-store' },
    )
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message }, { status: 502 })
  }
}
