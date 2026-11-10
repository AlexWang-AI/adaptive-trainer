import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

export async function GET(request: Request) {
  const url = new URL(request.url)
  const kpId = url.searchParams.get('kp_id') || ''
  if (!kpId) return NextResponse.json({ error: '缺少 kp_id' }, { status: 400 })
  try {
    const upstream = await fetch(
      `${AGENT_API_URL}/api/ledger?kp_id=${encodeURIComponent(kpId)}&student_id=local-user`,
      { cache: 'no-store' },
    )
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message }, { status: 502 })
  }
}
