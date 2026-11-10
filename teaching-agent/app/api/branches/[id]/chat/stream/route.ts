import {
  chatModel,
  reasonerModel,
  streamChat,
  type ChatMessage,
} from '@/lib/deepseek'
import { buildBranchPrompt } from '@/lib/prompts'
import {
  branchMessages,
  getDB,
  mutate,
  newId,
  now,
  reloadDB,
} from '@/lib/store'
import type { BranchMessage } from '@/lib/types'

export const runtime = 'nodejs'
export const maxDuration = 300

type Params = { params: Promise<{ id: string }> }
type Body = {
  message?: string
  deepThink?: boolean
  regenerate?: boolean
}

export async function POST(request: Request, { params }: Params) {
  const { id } = await params
  let body: Body = {}
  try {
    body = await request.json()
  } catch {
    // empty body is allowed for the first generation
  }

  let db = await getDB()
  let branch = db.branches.find((item) => item.id === id)
  if (!branch) {
    db = await reloadDB()
    branch = db.branches.find((item) => item.id === id)
  }
  if (!branch) return Response.json({ error: '分支不存在' }, { status: 404 })

  const existing = branchMessages(db, id)
  const isFirst = existing.length === 0
  const regenerate = Boolean(body.regenerate)
  const instruction = body.message?.trim() || branch.prompt
  if (!instruction) return Response.json({ error: '分支指令不能为空' }, { status: 400 })

  const shouldSetPrompt = regenerate || isFirst
  const promptForContext = shouldSetPrompt ? instruction : branch.prompt
  const userBranchMessage: BranchMessage | null =
    !regenerate && !isFirst
      ? {
          id: newId(),
          branchId: id,
          role: 'user',
          content: instruction,
          createdAt: now(),
        }
      : null

  const assistantId = newId()

  await mutate((data) => {
    const target = data.branches.find((item) => item.id === id)
    if (target) {
      target.updatedAt = now()
      if (shouldSetPrompt) target.prompt = instruction
      if (target.title === '新的疑问') {
        target.title = (target.anchorText || instruction).slice(0, 24) || '新的疑问'
      }
    }
    if (regenerate) {
      data.branchMessages = data.branchMessages.filter((message) => message.branchId !== id)
    }
    if (userBranchMessage) data.branchMessages.push(userBranchMessage)
  })

  // 圈选分支完全独立：不注入主对话的全局提示词/System Instruction/阶段提示词，
  // 也不注入主回答；只发送圈选内容 + 本分支提示词 + 分支自己的历史。
  const initialPrompt = buildBranchPrompt({
    anchor: branch.anchorText,
    instruction: promptForContext,
  })

  const history = branchMessages(db, id)
  const messages: ChatMessage[] = [
    { role: 'user', content: initialPrompt },
    ...history.map((message) => ({
      role: message.role,
      content: message.content.slice(0, 12_000),
    })),
  ]

  const model = body.deepThink ? reasonerModel() : chatModel()
  const startedAt = Date.now()
  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: unknown) => {
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
        } catch {
          // client already disconnected
        }
      }

      let content = ''
      let reasoning = ''
      let failed = false

      send({
        type: 'meta',
        userMessageId: userBranchMessage?.id,
        assistantMessageId: assistantId,
      })

      try {
        for await (const delta of streamChat({
          messages,
          model,
          signal: request.signal,
          temperature: 0.3,
          maxTokens: 8192,
        })) {
          if (delta.type === 'reasoning') {
            reasoning += delta.text
            send({ type: 'reasoning', text: delta.text })
          } else {
            content += delta.text
            send({ type: 'content', text: delta.text })
          }
        }
      } catch (error) {
        const name = (error as { name?: string }).name
        if (name !== 'AbortError') {
          failed = true
          const message = error instanceof Error ? error.message : String(error)
          send({ type: 'error', message })
          if (!content) content = `生成失败：${message}`
        }
      } finally {
        const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000))
        const finalMessage: BranchMessage = {
          id: assistantId,
          branchId: id,
          role: 'assistant',
          content: content || '（模型没有返回内容，请重试）',
          reasoning: reasoning || undefined,
          error: failed || undefined,
          seconds,
          createdAt: now(),
        }
        await mutate((data) => {
          data.branchMessages.push(finalMessage)
          const target = data.branches.find((item) => item.id === id)
          if (target) target.updatedAt = now()
        })
        send({ type: 'done', seconds })
        try {
          controller.close()
        } catch {
          // already closed
        }
      }
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}
