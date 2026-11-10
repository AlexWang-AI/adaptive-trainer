import {
  chatModel,
  reasonerModel,
  streamChat,
  type ChatMessage,
} from '@/lib/deepseek'
import { MAIN_SYSTEM_PROMPT } from '@/lib/prompts'
import {
  conversationMessages,
  getDB,
  mutate,
  newId,
  now,
  reloadDB,
} from '@/lib/store'
import type { PromptPreview } from '@/lib/prompt-types'
import type { Conversation, Message } from '@/lib/types'

export const runtime = 'nodejs'
export const maxDuration = 300

type Body = {
  conversationId?: string
  message?: string
  deepThink?: boolean
  systemPrompt?: string
  promptVersionId?: string
  promptVersionLabel?: string
  promptPreview?: PromptPreview
  kind?: 'stage-prompt' | 'chat'
}

export async function POST(request: Request) {
  let body: Body
  try {
    body = await request.json()
  } catch {
    return Response.json({ error: '无效请求体' }, { status: 400 })
  }

  const text = body.message?.trim()
  if (!text) return Response.json({ error: '消息不能为空' }, { status: 400 })

  let db = await getDB()
  const requestedConversationId = body.conversationId
  let conversation = db.conversations.find(
    (item) => item.id === requestedConversationId,
  )
  if (!conversation && requestedConversationId) {
    db = await reloadDB()
    conversation = db.conversations.find(
      (item) => item.id === requestedConversationId,
    )
  }
  if (!conversation) {
    // 必须沿用调用方给的 ID，否则分会话 ID 会漂移，后续分支就会“会话不存在”
    const conversationId = requestedConversationId || newId()
    const created: Conversation = {
      id: conversationId,
      title: text.slice(0, 30),
      createdAt: now(),
      updatedAt: now(),
    }
    await mutate((data) => {
      if (!data.conversations.some((item) => item.id === conversationId)) {
        data.conversations.push(created)
      }
    })
    conversation = created
  }

  const conversationId = conversation.id
  const userMessage: Message = {
    id: newId(),
    conversationId,
    role: 'user',
    content: text,
    kind: body.kind,
    createdAt: now(),
  }
  const assistantId = newId()

  await mutate((data) => {
    const target = data.conversations.find((item) => item.id === conversationId)
    if (target) {
      target.updatedAt = now()
      if (target.title === '新对话') target.title = text.slice(0, 30)
    }
    data.messages.push(userMessage)
  })

  const history = conversationMessages(db, conversationId)
    .slice(-20)
    .map((message) => ({
      role: message.role,
      content: message.content.slice(0, 12_000),
    }))
  const system = body.systemPrompt?.trim() || MAIN_SYSTEM_PROMPT
  const messages: ChatMessage[] = [
    { role: 'system', content: system },
    ...history,
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

      send({ type: 'meta', userMessageId: userMessage.id, assistantMessageId: assistantId })

      try {
        for await (const delta of streamChat({
          messages,
          model,
          signal: request.signal,
          temperature: 0.25,
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
        const finalMessage: Message = {
          id: assistantId,
          conversationId,
          role: 'assistant',
          content: content || '（模型没有返回内容，请重试）',
          reasoning: reasoning || undefined,
          model,
          error: failed || undefined,
          seconds,
          promptVersionId: body.promptVersionId,
          promptVersionLabel: body.promptVersionLabel,
          promptPreview: body.promptPreview,
          createdAt: now(),
        }
        await mutate((data) => {
          data.messages.push(finalMessage)
          const target = data.conversations.find((item) => item.id === conversationId)
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
