'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { BookOpen, Loader2, MessageCircleQuestion, Mic, MicOff, Send, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getJSON, postJSON } from '@/lib/client-api'
import { MarkdownMessage } from '@/components/math/markdown'

type ChatTurn = { role: 'student' | 'assistant'; content: string }

type MistakeItem = {
  id: number
  kp_name?: string
  question: string
  reasoning?: string
  created_at: number
  diagnosis?: {
    first_break?: string
    misconception?: string
    fix?: string
    severity?: string
    steps?: { step: string; ok: boolean; issue: string }[]
  }
}

type Props = {
  open: boolean
  onClose: () => void
  kpId?: string | null
  kpName?: string
  lesson: string
  question: string
}

/**
 * 侧边助教：两个 tab。
 *  问老师 —— 独立上下文的一问一答，不写主对话；
 *  错题本 —— 每次「说说我的思路」诊断后的记录，按时间倒序。
 */
export function AssistPanel({ open, onClose, kpId, kpName, lesson, question }: Props) {
  const [tab, setTab] = useState<'ask' | 'book'>('ask')
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [listening, setListening] = useState(false)
  const [mistakes, setMistakes] = useState<MistakeItem[]>([])
  const [bookBusy, setBookBusy] = useState(false)
  const recognizer = useRef<unknown>(null)

  const loadMistakes = useCallback(async () => {
    setBookBusy(true)
    try {
      const data = await getJSON<{ items: MistakeItem[] }>('/api/mistakes?limit=20')
      setMistakes(data.items ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBookBusy(false)
    }
  }, [])

  useEffect(() => {
    if (open && tab === 'book') void loadMistakes()
  }, [open, tab, loadMistakes])

  const ask = useCallback(async () => {
    const text = draft.trim()
    if (!text || busy) return
    setBusy(true)
    setError(null)
    setDraft('')
    const nextTurns: ChatTurn[] = [...turns, { role: 'student', content: text }]
    setTurns(nextTurns)
    try {
      const data = await postJSON<{ answer: string; misconception?: string }>('/api/side_ask', {
        ask: text,
        question,
        lesson: lesson.slice(0, 1200),
        history: nextTurns.slice(-6),
      })
      const extra = data.misconception ? `\n\n> 注意：${data.misconception}` : ''
      setTurns((prev) => [...prev, { role: 'assistant', content: (data.answer || '') + extra }])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }, [busy, draft, lesson, question, turns])

  const toggleVoice = useCallback(() => {
    const w = window as unknown as { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any }
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
    if (!Ctor) {
      setError('当前浏览器不支持语音识别，请用 Edge / Chrome')
      return
    }
    if (listening) {
      try {
        ;(recognizer.current as { stop: () => void })?.stop()
      } catch {}
      setListening(false)
      return
    }
    const rec = new Ctor()
    rec.lang = 'zh-CN'
    rec.interimResults = true
    rec.continuous = false
    rec.onresult = (event: any) => {
      let text = ''
      for (let i = 0; i < event.results.length; i += 1) text += event.results[i][0].transcript
      setDraft(text)
    }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recognizer.current = rec
    setListening(true)
    rec.start()
  }, [listening])

  if (!open) return null

  return (
    <div className="fixed right-3 bottom-4 z-40 flex h-[70vh] w-[min(92vw,380px)] flex-col overflow-hidden rounded-2xl border border-border/70 bg-background shadow-2xl">
      <header className="flex items-center gap-2 border-b border-border/60 px-3 py-2">
        <div className="flex rounded-lg bg-muted/50 p-0.5 text-[11.5px]">
          <button
            type="button"
            onClick={() => setTab('ask')}
            className={cn('rounded-md px-2.5 py-1', tab === 'ask' ? 'bg-background shadow-sm' : 'text-muted-foreground')}
          >
            问老师
          </button>
          <button
            type="button"
            onClick={() => setTab('book')}
            className={cn('rounded-md px-2.5 py-1', tab === 'book' ? 'bg-background shadow-sm' : 'text-muted-foreground')}
          >
            错题本
          </button>
        </div>
        <span className="min-w-0 flex-1 truncate text-[10.5px] text-muted-foreground">
          {kpName ? `· ${kpName}` : ''}（独立上下文，不影响主对话）
        </span>
        <button type="button" onClick={onClose} className="rounded p-1 text-muted-foreground hover:bg-muted/50">
          <X className="size-3.5" />
        </button>
      </header>

      {tab === 'ask' ? (
        <>
          <div className="scrollbar-thin min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
            {turns.length === 0 && (
              <p className="rounded-lg border border-dashed border-border/70 px-3 py-2 text-[11.5px] leading-5 text-muted-foreground">
                这一步没听懂？直接问。我只带「这道题 + 讲义片段」，不会打断主课，也不会污染主会话上下文。
              </p>
            )}
            {turns.map((turn, index) => (
              <div
                key={index}
                className={cn(
                  'max-w-[92%] rounded-xl px-3 py-2 text-[12.5px] leading-6',
                  turn.role === 'student'
                    ? 'ml-auto bg-primary/10 text-foreground'
                    : 'bg-muted/40 text-foreground/90',
                )}
              >
                <MarkdownMessage content={turn.content} />
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> 助教在想…
              </div>
            )}
            {error && <p className="text-[11px] text-rose-600">{error}</p>}
          </div>
          <div className="border-t border-border/60 px-2.5 py-2">
            <div className="flex items-end gap-1.5">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void ask()
                  }
                }}
                rows={2}
                placeholder="问：这一步为什么能直接求导？"
                className="min-h-[38px] flex-1 resize-none rounded-lg border border-border/70 bg-background px-2 py-1.5 text-[12.5px] outline-none focus:border-primary/60"
              />
              <button
                type="button"
                onClick={toggleVoice}
                className={cn(
                  'grid size-8 place-items-center rounded-lg border',
                  listening ? 'border-rose-400 bg-rose-50 text-rose-600' : 'border-border/70 text-muted-foreground',
                )}
                title="语音输入"
              >
                {listening ? <MicOff className="size-3.5" /> : <Mic className="size-3.5" />}
              </button>
              <button
                type="button"
                onClick={() => void ask()}
                disabled={!draft.trim() || busy}
                className="grid size-8 place-items-center rounded-lg bg-primary text-white disabled:opacity-40"
              >
                <Send className="size-3.5" />
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="scrollbar-thin min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">共 {mistakes.length} 条思路诊断</span>
            <button type="button" onClick={() => void loadMistakes()} className="text-[11px] text-primary">
              刷新
            </button>
          </div>
          {bookBusy && <p className="text-[11.5px] text-muted-foreground">加载中…</p>}
          {!bookBusy && mistakes.length === 0 && (
            <p className="rounded-lg border border-dashed border-border/70 px-3 py-2 text-[11.5px] text-muted-foreground">
              还没有记录。答题时点「说说我的思路」，讲一遍你的推理，我就会把断点记在这里。
            </p>
          )}
          {mistakes.map((item) => (
            <div key={item.id} className="rounded-xl border border-border/60 bg-card/60 p-2.5">
              <div className="flex items-center gap-1.5 text-[10.5px] text-muted-foreground">
                <BookOpen className="size-3" />
                {item.kp_name || '未标注知识点'} · {new Date(item.created_at * 1000).toLocaleString('zh-CN')}
              </div>
              <p className="mt-1 line-clamp-2 text-[12px] leading-5">{item.question}</p>
              {item.diagnosis?.first_break && (
                <p className="mt-1 text-[11.5px] text-rose-700">断点：{item.diagnosis.first_break}</p>
              )}
              {item.diagnosis?.fix && (
                <p className="mt-0.5 text-[11.5px] text-emerald-700">纠正：{item.diagnosis.fix}</p>
              )}
            </div>
          ))}
        </div>
      )}

      <footer className="border-t border-border/60 px-3 py-1.5 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <MessageCircleQuestion className="size-3" />
          侧问与错题本都是旁路调用，主链路只负责讲课与判题
        </span>
      </footer>
    </div>
  )
}
