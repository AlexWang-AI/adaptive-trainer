export type StreamEvent =
  | { type: 'meta'; userMessageId?: string; assistantMessageId: string }
  | { type: 'reasoning'; text: string }
  | { type: 'content'; text: string }
  | { type: 'error'; message: string }
  | { type: 'done'; seconds?: number }

export async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

export async function getJSON<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

export async function streamPost(
  url: string,
  body: unknown,
  signal: AbortSignal | undefined,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `请求失败（${response.status}）`)
  }
  if (!response.body) throw new Error('服务端没有返回响应流')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.split('\n').find((item) => item.startsWith('data:'))
      if (!line) continue
      const raw = line.slice(5).trim()
      if (!raw || raw === '[DONE]') continue
      try {
        onEvent(JSON.parse(raw) as StreamEvent)
      } catch {
        // ignore malformed keepalive
      }
    }
  }
}
