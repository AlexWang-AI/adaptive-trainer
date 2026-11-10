import { DEFAULT_BRANCH_PROMPT } from '@/lib/prompts'
import { mutate, newId, now } from '@/lib/store'
import type { Branch } from '@/lib/types'

export const runtime = 'nodejs'

type Body = {
  conversationId?: string
  title?: string
  prompt?: string
  anchorText?: string
  anchorLabel?: string
}

export async function POST(request: Request) {
  let body: Body
  try {
    body = await request.json()
  } catch {
    return Response.json({ error: '无效请求体' }, { status: 400 })
  }

  if (!body.conversationId) {
    return Response.json({ error: '缺少会话 ID' }, { status: 400 })
  }

  const anchorText = body.anchorText?.trim() ?? ''
  const branch: Branch = {
    id: newId(),
    conversationId: body.conversationId,
    title: body.title?.trim() || anchorText.slice(0, 24) || '新的疑问',
    prompt: body.prompt?.trim() || DEFAULT_BRANCH_PROMPT,
    anchorText,
    anchorLabel: body.anchorLabel?.trim() || (anchorText ? '圈选内容' : undefined),
    createdAt: now(),
    updatedAt: now(),
  }

  await mutate((data) => {
    data.branches.push(branch)
  })

  return Response.json({ ...branch, messages: [] })
}
