export type ContentPart =
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } }

export type ChatMessage = {
  role: 'system' | 'user' | 'assistant'
  content: string | ContentPart[]
}

export type StreamDelta = { type: 'reasoning' | 'content'; text: string }

const BASE_URL = process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com'

export function apiKey() {
  const key = process.env.DEEPSEEK_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN
  if (!key) throw new Error('未配置 DEEPSEEK_API_KEY')
  return key
}

export function chatModel() {
  return process.env.DEEPSEEK_CHAT_MODEL || 'deepseek-flash'
}

export function reasonerModel() {
  return process.env.DEEPSEEK_REASONER_MODEL || chatModel()
}

export function visionModel() {
  return process.env.DEEPSEEK_VISION_MODEL || chatModel()
}

async function request(body: Record<string, unknown>, signal?: AbortSignal) {
  const response = await fetch(`${BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey()}`,
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`DeepSeek ${response.status}: ${text.slice(0, 600)}`)
  }
  return response
}

export async function* streamChat(options: {
  messages: ChatMessage[]
  model?: string
  temperature?: number
  maxTokens?: number
  signal?: AbortSignal
}): AsyncGenerator<StreamDelta> {
  const response = await request(
    {
      model: options.model || chatModel(),
      messages: options.messages,
      stream: true,
      temperature: options.temperature ?? 0.25,
      max_tokens: options.maxTokens ?? 8192,
    },
    options.signal,
  )
  if (!response.body) throw new Error('DeepSeek 没有返回响应流')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const raw = trimmed.slice(5).trim()
      if (!raw || raw === '[DONE]') continue
      try {
        const json = JSON.parse(raw)
        const delta = json?.choices?.[0]?.delta
        if (!delta) continue
        const reasoning = delta.reasoning_content ?? delta.reasoning
        if (typeof reasoning === 'string' && reasoning) {
          yield { type: 'reasoning', text: reasoning }
        }
        if (typeof delta.content === 'string' && delta.content) {
          yield { type: 'content', text: delta.content }
        }
      } catch {
        // keepalive or malformed chunk
      }
    }
  }
}

export async function completeChat(options: {
  messages: ChatMessage[]
  model?: string
  maxTokens?: number
  temperature?: number
  signal?: AbortSignal
}): Promise<string> {
  const response = await request(
    {
      model: options.model || chatModel(),
      messages: options.messages,
      stream: false,
      temperature: options.temperature ?? 0,
      max_tokens: options.maxTokens ?? 2000,
    },
    options.signal ?? AbortSignal.timeout(180_000),
  )
  const json = await response.json()
  const message = json?.choices?.[0]?.message
  return String(message?.content || message?.reasoning_content || '')
}

export async function visionExtract(image: string, prompt: string, signal?: AbortSignal) {
  return completeChat({
    model: visionModel(),
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: prompt },
          { type: 'image_url', image_url: { url: image } },
        ],
      },
    ],
    maxTokens: 3000,
    signal,
  })
}
