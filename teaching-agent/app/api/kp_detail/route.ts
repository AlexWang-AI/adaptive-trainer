import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const AGENT_API_URL = process.env.AGENT_API_URL || 'http://127.0.0.1:8008'

/**
 * 单个知识点的教材细节：考纲 / 要点 / 结论 / 教材例题 / 题型 / 提速技巧 / 注入的教材依据全文。
 * 只读，不花 token。
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const kpId = url.searchParams.get('kp_id') || ''
  if (!kpId) return NextResponse.json({ error: '缺少 kp_id' }, { status: 400 })
  try {
    const upstream = await fetch(
      `${AGENT_API_URL}/api/kp_detail?kp_id=${encodeURIComponent(kpId)}`,
      { cache: 'no-store' },
    )
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return NextResponse.json({ error: message }, { status: 502 })
  }
}
