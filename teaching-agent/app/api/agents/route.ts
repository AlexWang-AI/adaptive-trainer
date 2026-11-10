import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

export async function GET() {
  try {
    const response = await fetch(`${AGENT_API_URL}/api/agents`, { cache: 'no-store' })
    const text = await response.text()
    if (!response.ok) {
      return NextResponse.json(
        { error: text.slice(0, 800) || `sidecar ${response.status}` },
        { status: response.status },
      )
    }
    return new NextResponse(text, {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json(
      { error: `Agent 状态接口未连接（${AGENT_API_URL}）：${message}` },
      { status: 502 },
    )
  }
}
