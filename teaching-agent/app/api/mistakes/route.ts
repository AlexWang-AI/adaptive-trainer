import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/** 错题本：按时间倒序返回思路诊断记录。 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const studentId = url.searchParams.get('student_id') || 'local-user'
  const limit = url.searchParams.get('limit') || '20'
  try {
    const upstream = await fetch(
      `${AGENT_API_URL}/api/mistakes?student_id=${encodeURIComponent(studentId)}&limit=${encodeURIComponent(limit)}`,
      { cache: 'no-store' },
    )
    const data = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: `错题本服务未连接：${message}`, items: [] }, { status: 502 })
  }
}
