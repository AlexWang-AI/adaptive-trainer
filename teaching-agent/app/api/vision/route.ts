import { visionExtract } from '@/lib/deepseek'
import { VISION_PROMPT } from '@/lib/prompts'

export const runtime = 'nodejs'
export const maxDuration = 180

export async function POST(request: Request) {
  let body: { image?: string }
  try {
    body = await request.json()
  } catch {
    return Response.json({ error: '无效请求体' }, { status: 400 })
  }

  if (typeof body.image !== 'string' || !body.image.startsWith('data:image/')) {
    return Response.json({ error: '缺少有效的图片数据' }, { status: 400 })
  }

  try {
    const text = await visionExtract(body.image, VISION_PROMPT, request.signal)
    if (!text.trim()) {
      return Response.json({ error: '没有识别到内容，请重新圈选' }, { status: 502 })
    }
    return Response.json({ text: text.trim() })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return Response.json({ error: `识别失败：${message}` }, { status: 502 })
  }
}
