import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

async function proxy(path: string, init?: RequestInit) {
  const upstream = await fetch(`${AGENT_API_URL}${path}`, { cache: 'no-store', ...init })
  const data = await upstream.json()
  return NextResponse.json(data, { status: upstream.status })
}

export async function GET() {
  try {
    return await proxy('/api/analytics?student_id=local-user')
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message, overall: 0, chapters: [], heatmap: [], history: [] }, { status: 502 })
  }
}
