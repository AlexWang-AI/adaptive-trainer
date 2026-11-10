'use client'

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  CheckCircle2,
  GraduationCap,
  MessageCircleQuestion,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { postJSON, streamPost, getJSON } from '@/lib/client-api'
import { MarkdownMessage, StreamingMarkdown } from '@/components/math/markdown'
import { MathText } from '@/components/math/math-text'
import { ThinkingBox } from '@/components/chat/thinking-box'
import { MainComposer } from '@/components/chat/main-composer'
import { PenOverlay } from '@/components/chat/pen-overlay'
import { LassoPromptDialog } from '@/components/chat/lasso-prompt-dialog'
import { QuizPack } from '@/components/teaching/quiz-pack'
import { AssistPanel } from '@/components/teaching/assist-panel'
import { useKnowledge } from '@/components/workspace/knowledge-provider'
import type { QuizQuestion } from '@/lib/quiz-types'

const useIsomorphicLayoutEffect =
  typeof window === 'undefined' ? useEffect : useLayoutEffect

type QuizCardData = {
  question: string
  options: string[]
  answer: string
}

type Judgement = {
  correct: boolean
  correct_answer: string
  feedback: string
  explanation: string
  tested_points: string[]
  difficulty: string
}

type TeachResponse = {
  session_id: string
  status: 'awaiting_answer' | 'done' | 'error'
  round: number
  max_rounds: number
  teaching_content: string
  thinking?: string
  thinking_seconds?: number
  quiz_card: QuizCardData | null
  judgement: Judgement | null
  error?: string | null
}

type TeachingMessage = {
  id: string
  role: 'teacher' | 'student' | 'system'
  content: string
  thinking?: string
  thinkingSeconds?: number
  reasoning?: string
  streaming?: boolean
  quiz?: QuizCardData
  quizPack?: QuizQuestion[]
  drill?: boolean
  kpId?: string | null
  kpName?: string
  selected?: string
  judgement?: Judgement
}

type TeachStreamEvent =
  | { type: 'meta'; session_id: string; round: number; max_rounds: number; kp_id?: string | null; kp_name?: string }
  | { type: 'reasoning'; text: string }
  | { type: 'content'; text: string }
  | { type: 'judgement'; judgement: Judgement }
  | { type: 'quiz'; quiz_card: QuizCardData }
  | { type: 'quiz_pack'; quiz_pack: QuizQuestion[]; kp_id?: string | null; kp_name?: string; ttft_ms?: number }
  | {
      type: 'done'
      status: 'awaiting_answer' | 'done' | 'error'
      round: number
      max_rounds: number
      session_id?: string
      ttft_ms?: number
      elapsed_ms?: number
      tokens?: number
      error?: string | null
    }
  | { type: 'error'; message: string }

type HistoryInput = { role: 'student' | 'teacher'; content: string }

const LEVELS = ['小学', '初中', '高中', '大学低年级', '成人零基础'] as const
const DEFAULT_TOPIC = '我想学考研数学一里的导数，先讲第一步怎么切入。'
const DEFAULT_LASSO_PROMPT =
  '把这段内容讲透：先说明它在原推导中的作用，再逐步拆解每一步的动机和依据，指出最容易错的地方，最后给出 3 道同类型考研例题及标准答案。'
const PRAISE = ['GOOD!', 'NICE!', 'GREAT!', 'PERFECT!', 'WELL DONE!']

let audioContext: AudioContext | null = null

function audio() {
  if (typeof window === 'undefined') return null
  if (audioContext) return audioContext
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Ctor) return null
  audioContext = new Ctor()
  return audioContext
}

function tone(freq: number, duration: number, type: OscillatorType = 'square', volume = 0.03, delay = 0) {
  const context = audio()
  if (!context) return
  if (context.state === 'suspended') void context.resume()
  const start = context.currentTime + delay
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = type
  oscillator.frequency.setValueAtTime(freq, start)
  gain.gain.setValueAtTime(volume, start)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration)
  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start(start)
  oscillator.stop(start + duration + 0.03)
}

const sfx = {
  click: () => tone(520, 0.04, 'square', 0.018),
  correct: () => {
    tone(660, 0.07, 'square', 0.028)
    tone(990, 0.1, 'square', 0.028, 0.07)
  },
  wrong: () => {
    tone(200, 0.14, 'sawtooth', 0.03)
    tone(130, 0.2, 'sawtooth', 0.026, 0.07)
  },
}

function newId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `t-${Date.now()}-${Math.random().toString(16).slice(2)}`
}


/** 流式渲染时裁掉尾巴上没闭合的公式/加粗/代码，避免闪出原始 $ 与星号。 */
function trimIncompleteMarkdown(text: string): string {
  let out = text
  // 未闭合的行内公式：从后往前数 $ 的个数
  const dollars = (out.match(/\$/g) || []).length
  if (dollars % 2 === 1) {
    const idx = out.lastIndexOf('$')
    if (idx > out.length - 400) out = out.slice(0, idx)
  }
  if ((out.match(/\*\*/g) || []).length % 2 === 1) {
    const idx = out.lastIndexOf('**')
    if (idx > out.length - 200) out = out.slice(0, idx)
  }
  if ((out.match(/`/g) || []).length % 2 === 1) {
    const idx = out.lastIndexOf('`')
    if (idx > out.length - 200) out = out.slice(0, idx)
  }
  return out
}

function PixelQuizCard({
  quiz,
  selected,
  judgement,
  busy,
  onAnswer,
  onAdvance,
}: {
  quiz: QuizCardData
  selected?: string
  judgement?: Judgement
  busy: boolean
  onAnswer: (answer: string) => void
  onAdvance?: () => void
}) {
  const [fillValue, setFillValue] = useState('')
  const [bubble, setBubble] = useState<string | null>(null)
  const [shake, setShake] = useState(false)
  const advanceRef = useRef(onAdvance)
  const answered = selected !== undefined && selected !== ''
  const isChoice = quiz.options.length >= 2
  const correctLetter = (judgement?.correct_answer ?? quiz.answer).trim().toUpperCase()

  useEffect(() => {
    advanceRef.current = onAdvance
  }, [onAdvance])

  useEffect(() => {
    if (!judgement) return
    if (judgement.correct) {
      setBubble(PRAISE[Math.floor(Math.random() * PRAISE.length)])
      sfx.correct()
      const timer = window.setTimeout(() => advanceRef.current?.(), 760)
      return () => window.clearTimeout(timer)
    }
    setBubble('NOT QUITE')
    setShake(true)
    sfx.wrong()
    const timer = window.setTimeout(() => setShake(false), 380)
    return () => window.clearTimeout(timer)
  }, [judgement])

  const choose = (letter: string) => {
    if (answered || busy) return
    sfx.click()
    onAnswer(letter)
  }

  const stateFor = (letter: string) => {
    if (!answered) return 'idle'
    if (letter === correctLetter) return 'right'
    if (letter === selected?.toUpperCase()) return 'wrong'
    return 'muted'
  }

  return (
    <div className={cn('quiz-pixel-card', shake && 'quiz-pixel-shake')}>
      <div className="quiz-pixel-head">
        <span className="quiz-pixel-chip">
          <Sparkles className="size-3" />
          CHECKPOINT
        </span>
        <span className="quiz-pixel-chip quiz-pixel-chip-soft">
          {isChoice ? '单选题' : '填空题'}
        </span>
        <span className="quiz-pixel-chip quiz-pixel-chip-soft">
          {judgement?.difficulty === 'hard' ? 'HARD' : judgement?.difficulty === 'medium' ? 'NORMAL' : 'EASY'}
        </span>
        <span className="ml-auto text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
          {answered ? 'ANSWERED' : 'WAITING'}
        </span>
      </div>

      <div className="quiz-pixel-question">
        <MarkdownMessage content={quiz.question} className="text-[16px] leading-[1.8]" />
      </div>

      {isChoice ? (
        <div className="quiz-pixel-options">
          {quiz.options.map((option, index) => {
            const letter = String.fromCharCode(65 + index)
            const state = stateFor(letter)
            return (
              <button
                key={`${letter}-${option}`}
                type="button"
                data-testid="quiz-option"
                data-answer={letter}
                disabled={answered || busy}
                onClick={() => choose(letter)}
                className={cn(
                  'quiz-pixel-option',
                  state === 'right' && 'quiz-pixel-option-right',
                  state === 'wrong' && 'quiz-pixel-option-wrong',
                  state === 'muted' && 'quiz-pixel-option-muted',
                )}
              >
                <span className="quiz-pixel-letter">{letter}</span>
                <span className="min-w-0 flex-1">
                  <MathText>{option.replace(/^\s*[A-Da-d]\s*[.、,:：)）]\s*/, '')}</MathText>
                </span>
                {state === 'right' && <CheckCircle2 className="size-4 shrink-0" />}
                {state === 'wrong' && <XCircle className="size-4 shrink-0" />}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <input
            value={fillValue}
            onChange={(event) => setFillValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && fillValue.trim() && !answered && !busy) {
                sfx.click()
                onAnswer(fillValue.trim())
              }
            }}
            disabled={answered || busy}
            placeholder="写下答案…"
            className="min-w-0 flex-1 rounded-md border-2 border-border/80 bg-background/80 px-3 py-2.5 font-mono text-[13px] outline-none focus:border-primary/60"
          />
          <button
            type="button"
            disabled={!fillValue.trim() || answered || busy}
            onClick={() => {
              sfx.click()
              onAnswer(fillValue.trim())
            }}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border-2 border-primary/40 bg-primary px-4 py-2.5 text-[12px] font-semibold text-primary-foreground disabled:opacity-40"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            提交
          </button>
        </div>
      )}

      {bubble && <span className="quiz-pixel-bubble">{bubble}</span>}

      {judgement && (
        <div
          aria-live="polite"
          className={cn(
            'quiz-pixel-explain',
            judgement.correct ? 'quiz-pixel-explain-right' : 'quiz-pixel-explain-wrong',
          )}
        >
          <div className="mb-1.5 flex flex-wrap items-center gap-2 font-semibold">
            {judgement.correct ? (
              <CheckCircle2 className="size-4" />
            ) : (
              <XCircle className="size-4" />
            )}
            <span>{judgement.correct ? '答对了' : '这题答错了'}</span>
            {!judgement.correct && (
              <span className="ml-auto text-[10.5px] font-normal text-muted-foreground">
                正确答案：<MathText>{judgement.correct_answer}</MathText>
              </span>
            )}
          </div>
          <MarkdownMessage content={judgement.feedback} className="text-[12.5px] leading-[1.8]" />
          {judgement.tested_points.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {judgement.tested_points.map((point) => (
                <span key={point} className="quiz-pixel-point">
                  {point}
                </span>
              ))}
            </div>
          )}
          {!judgement.correct && onAdvance && (
            <button
              type="button"
              onClick={() => {
                sfx.click()
                onAdvance()
              }}
              className="quiz-pixel-continue"
            >
              看懂了，继续 →
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function PixelStyles() {
  return (
    <style>{`
      .quiz-pixel-card {
        position: relative;
        margin-top: 18px;
        border: 2px solid color-mix(in oklch, var(--foreground) 72%, transparent);
        border-radius: 6px;
        background: color-mix(in oklch, var(--card) 92%, #fffdf8);
        box-shadow: 4px 4px 0 color-mix(in oklch, var(--foreground) 12%, transparent);
        padding: 14px 16px 16px;
      }
      .quiz-pixel-head {
        display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
        border-bottom: 1px dashed color-mix(in oklch, var(--border) 85%, transparent);
        padding-bottom: 8px; margin-bottom: 10px;
      }
      .quiz-pixel-chip {
        display: inline-flex; align-items: center; gap: 4px;
        border: 1px solid color-mix(in oklch, var(--primary) 45%, transparent);
        background: color-mix(in oklch, var(--primary) 10%, transparent);
        color: var(--primary); padding: 2px 7px; border-radius: 3px;
        font: 600 9px/1.4 ui-monospace, monospace; letter-spacing: .1em;
      }
      .quiz-pixel-chip-soft {
        border-color: color-mix(in oklch, var(--border) 90%, transparent);
        background: color-mix(in oklch, var(--muted) 45%, transparent);
        color: var(--muted-foreground);
      }
      .quiz-pixel-question { font-family: var(--font-serif, Georgia), serif; }
      .quiz-pixel-options { display: grid; gap: 8px; margin-top: 12px; }
      .quiz-pixel-option {
        display: flex; align-items: flex-start; gap: 10px; width: 100%;
        border: 2px solid color-mix(in oklch, var(--border) 90%, transparent);
        border-radius: 4px; background: color-mix(in oklch, var(--background) 72%, transparent);
        padding: 9px 11px; text-align: left; font-size: 13px; line-height: 1.7;
        transition: border-color .12s, background .12s, transform .12s;
      }
      .quiz-pixel-option:hover:not(:disabled) {
        border-color: color-mix(in oklch, var(--primary) 60%, transparent);
        background: color-mix(in oklch, var(--primary) 6%, transparent);
        transform: translateX(2px);
      }
      .quiz-pixel-option:disabled { cursor: default; }
      .quiz-pixel-letter {
        display: grid; place-items: center; width: 22px; height: 22px; flex: none;
        border: 1px solid color-mix(in oklch, var(--border) 95%, transparent);
        border-radius: 3px; background: color-mix(in oklch, var(--muted) 55%, transparent);
        font: 700 10px/1 ui-monospace, monospace; color: var(--muted-foreground);
      }
      .quiz-pixel-option-right {
        border-color: #2e7d4f !important; background: color-mix(in oklch, #2e7d4f 9%, var(--card)) !important;
        color: #245c3b;
      }
      .quiz-pixel-option-right .quiz-pixel-letter { border-color: #2e7d4f; background: #2e7d4f; color: #fff; }
      .quiz-pixel-option-wrong {
        border-color: #b03a2e !important; background: color-mix(in oklch, #b03a2e 8%, var(--card)) !important;
        color: #8c2f26;
      }
      .quiz-pixel-option-wrong .quiz-pixel-letter { border-color: #b03a2e; background: #b03a2e; color: #fff; }
      .quiz-pixel-option-muted { opacity: .58; }
      .quiz-pixel-bubble {
        position: absolute; right: 18px; top: -13px; z-index: 4;
        border: 2px solid #b03a2e; background: #fffdf8; color: #b03a2e;
        padding: 2px 8px; font: 700 10px/1.5 ui-monospace, monospace;
        letter-spacing: .08em; transform: rotate(-4deg);
        box-shadow: 2px 2px 0 color-mix(in oklch, #b03a2e 18%, transparent);
        animation: quiz-pop .32s cubic-bezier(.2,1.4,.4,1);
        pointer-events: none;
      }
      .quiz-pixel-explain {
        margin-top: 12px; border: 1px dashed color-mix(in oklch, var(--border) 90%, transparent);
        border-radius: 4px; padding: 10px 12px; font-size: 12.5px;
      }
      .quiz-pixel-explain-right { background: color-mix(in oklch, #2e7d4f 7%, transparent); border-color: color-mix(in oklch, #2e7d4f 40%, transparent); }
      .quiz-pixel-explain-wrong { background: color-mix(in oklch, #b03a2e 6%, transparent); border-color: color-mix(in oklch, #b03a2e 35%, transparent); }
      .quiz-pixel-point {
        border: 1px solid color-mix(in oklch, var(--border) 85%, transparent);
        background: color-mix(in oklch, var(--background) 65%, transparent);
        padding: 1px 6px; border-radius: 3px; font-size: 9.5px; color: var(--muted-foreground);
      }
      .quiz-pixel-continue {
        margin-top: 9px; border: 1px solid color-mix(in oklch, var(--primary) 45%, transparent);
        background: color-mix(in oklch, var(--primary) 8%, transparent);
        color: var(--primary); padding: 3px 9px; border-radius: 3px;
        font: 600 10px/1.5 ui-monospace, monospace; letter-spacing: .06em; cursor: pointer;
      }
      .quiz-pixel-continue:hover { background: color-mix(in oklch, var(--primary) 14%, transparent); }
      .quiz-pixel-shake { animation: quiz-shake .34s linear; }
      @keyframes quiz-pop { 0% { opacity: 0; transform: scale(.5) rotate(-8deg); } 100% { opacity: 1; transform: scale(1) rotate(-4deg); } }
      @keyframes quiz-shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-5px)} 50%{transform:translateX(4px)} 75%{transform:translateX(-2px)} }
    `}</style>
  )
}

export function TeachingChat() {
  const [started, setStarted] = useState(false)
  const [draft, setDraft] = useState(DEFAULT_TOPIC)
  const [level, setLevel] = useState<(typeof LEVELS)[number]>('大学低年级')
  const [prior, setPrior] = useState('会函数图像和斜率，但只会背公式')
  const [messages, setMessages] = useState<TeachingMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [phase, setPhase] = useState<'idle' | 'loading' | 'awaiting' | 'done' | 'error'>('idle')
  const [round, setRound] = useState(0)
  const [maxRounds, setMaxRounds] = useState(5)
  const [activeQuizId, setActiveQuizId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [penMode, setPenMode] = useState(false)
  const [lassoOpen, setLassoOpen] = useState(false)
  const [lassoLoading, setLassoLoading] = useState(false)
  const [lassoError, setLassoError] = useState<string | null>(null)
  const [lassoAnchor, setLassoAnchor] = useState('')
  const [lassoPrompt, setLassoPrompt] = useState(DEFAULT_LASSO_PROMPT)
  const { pendingStart, clearPendingStart, markMastered, setActiveKpId, tree } = useKnowledge()
  const [roundKp, setRoundKp] = useState<{ id: string; name: string } | null>(null)
  const [masteredKp, setMasteredKp] = useState<{ id: string; name: string } | null>(null)
  const [autoAdvanceIn, setAutoAdvanceIn] = useState(0)
  const autoAdvanceCancelled = useRef(false)
  const [assistOpen, setAssistOpen] = useState(false)
  const [ledger, setLedger] = useState<null | {
    kp_name: string
    attempts: number
    correct: number
    mastery: { score: number; explain: string }
    first_break: string
    misconception: string
    next_review: { stage: number; in_days: number } | null
  }>(null)
  const [practiceBusy, setPracticeBusy] = useState(false)
  const [following, setFollowing] = useState(true)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const stickToBottomRef = useRef(true)
  const lastScrollTopRef = useRef(0)
  // 上一次「我们自己滚到」的位置；handleScroll 用它区分程序滚动和用户滚动
  const programmaticTopRef = useRef<number | null>(null)
  const typingRef = useRef<{
    id: string | null
    queue: string
    timer: number | null
    quiz: QuizCardData | null
    done: TeachStreamEvent | null
    startedAt: number
    teacherId: string
    raf: number | null
    flush: number | null
  }>({
    id: null,
    queue: '',
    timer: null,
    quiz: null,
    done: null,
    startedAt: 0,
    teacherId: '',
    raf: null,
    flush: null,
  })

  // 诊断计数（仅 dev / ?e2e=1）：P2-9 的口径是「一次渲染最多一次跟随」，
  // 所以既要数跟随调用，也要数渲染次数 —— 单看 chunk 数会被打字机的追赶节奏干扰。
  if (typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.location.search.includes('e2e=1'))) {
    const w = window as unknown as { __MN_COMMIT__?: number }
    w.__MN_COMMIT__ = (w.__MN_COMMIT__ ?? 0) + 1
  }

  const scrollToBottom = (element: HTMLDivElement) => {
    // 记下「我们自己滚到哪」，handleScroll 靠它认出这次滚动是程序动的。
    // 以前用一个 rAF 复位标志位，但滚动事件是在 rAF 之后才派发的，
    // 标志早被复位 → handleScroll 又读一次 scrollHeight，白多一次强制布局（红队 P2-9）
    if (typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.location.search.includes('e2e=1'))) {
      const w = window as unknown as { __MN_FOLLOW__?: number }
      w.__MN_FOLLOW__ = (w.__MN_FOLLOW__ ?? 0) + 1
    }
    element.scrollTop = element.scrollHeight
    programmaticTopRef.current = element.scrollTop
    lastScrollTopRef.current = element.scrollTop
  }

  const handleScroll = () => {
    const element = scrollRef.current
    if (!element) return
    const top = element.scrollTop
    const programmatic = programmaticTopRef.current
    if (programmatic !== null && Math.abs(top - programmatic) <= 1) {
      // 是刚才我们自己滚的，位置没被别人动过：一次布局都不用读
      lastScrollTopRef.current = top
      return
    }
    programmaticTopRef.current = null
    const previous = lastScrollTopRef.current
    if (top < previous - 1) {
      // 向上看：立即锁死，流式内容不再把你往下扒
      stickToBottomRef.current = false
      setFollowing(false)
    } else if (element.scrollHeight - top - element.clientHeight < 48) {
      // 回到底部 48px 内才恢复跟随
      stickToBottomRef.current = true
      setFollowing(true)
    }
    lastScrollTopRef.current = top
  }

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (event.deltaY < 0) {
      // 滚轮一有向上动作就同步锁死，抢在流式渲染之前；
      // 同时把 following 打开成 false，才会出现「回到底部」按钮
      stickToBottomRef.current = false
      setFollowing(false)
    }
  }

  // 用户主动要回底部（点「回到底部」/ 加练按钮）：无条件滚，并把跟随打开
  const advanceToBottom = useCallback(() => {
    stickToBottomRef.current = true
    const element = scrollRef.current
    if (element) scrollToBottom(element)
  }, [])

  // 内部顺带滚动（题卡到达、答题进度变化）：只在「用户本来就在底部」时才滚。
  // 以前这些地方直接调 advanceToBottom，讲义一结束就把正在往上读的人硬拽到底部
  // —— 上滑测试把视口压到 640 高之后才暴露出来（P2-9 连带发现）
  const softFollow = useCallback(() => {
    if (!stickToBottomRef.current) return
    const element = scrollRef.current
    if (element) scrollToBottom(element)
  }, [])

  const finalizeDone = useCallback(
    (event: TeachStreamEvent, teacherId: string, startedAt: number) => {
      if (event.type !== 'done') return
      if (typeof event.round === 'number') setRound(event.round)
      if (typeof event.max_rounds === 'number') setMaxRounds(event.max_rounds)
      if (teacherId) {
        setMessages((previous) =>
          previous.map((message) =>
            message.id === teacherId
              ? {
                  ...message,
                  streaming: false,
                  thinkingSeconds: Math.max(1, Math.round((Date.now() - startedAt) / 1000)),
                }
              : message,
          ),
        )
      }
      if (event.status === 'done') {
        setActiveQuizId(null)
        setMessages((previous) => [
          ...previous,
          {
            id: newId(),
            role: 'system',
            content: `已完成 ${event.round + 1} 轮自适应训练。你可以重新开始，或换一个知识模块。`,
          },
        ])
        setPhase('done')
      } else {
        setPhase('awaiting')
      }
    },
    [],
  )

  const finishTyping = useCallback(() => {
    const typing = typingRef.current
    if (typing.timer !== null) {
      window.clearInterval(typing.timer)
      typing.timer = null
    }
    if (typing.raf !== null) {
      window.cancelAnimationFrame(typing.raf)
      typing.raf = null
    }
    if (typing.flush !== null) {
      window.clearTimeout(typing.flush)
      typing.flush = null
    }
    if (!typing.id) return
    const id = typing.id
    const quiz = typing.quiz
    const done = typing.done
    typing.quiz = null
    typing.done = null
    if (quiz) {
      setMessages((previous) =>
        previous.map((message) =>
          message.id === id ? { ...message, quiz, streaming: false } : message,
        ),
      )
      setActiveQuizId(id)
    }
    if (done) {
      finalizeDone(done, id, typing.startedAt)
    } else if (!quiz) {
      setMessages((previous) =>
        previous.map((message) =>
          message.id === id ? { ...message, streaming: false } : message,
        ),
      )
    }
  }, [finalizeDone])

  // 把队列里剩下的字一次性倒出来，然后立即收尾。
  // 为什么必须有：收尾以前只发生在 queueDone/queueQuiz 那一瞬间队列恰好为空的时候
  // （红队 P1-7）。只要 done 到达时队列里还有一个字，就再也没人调用 finishTyping，
  // 气泡永远停在「老师正在写…」。另外 rAF 在后台标签页会被暂停，这里同时当保底。
  const flushTyping = useCallback(() => {
    const typing = typingRef.current
    if (typing.flush !== null) {
      window.clearTimeout(typing.flush)
      typing.flush = null
    }
    if (typing.raf !== null) {
      window.cancelAnimationFrame(typing.raf)
      typing.raf = null
    }
    if (!typing.id) return
    const id = typing.id
    const rest = typing.queue
    typing.queue = ''
    if (rest) {
      setMessages((previous) =>
        previous.map((message) =>
          message.id === id ? { ...message, content: message.content + rest, streaming: true } : message,
        ),
      )
    }
    if (typing.done || typing.quiz) finishTyping()
  }, [finishTyping])

  // 流结束后挂一个保底：正常情况打字机在 1.5s 内自己排空并收尾，
  // 这里只是兜住「rAF 被挂起 / 极端长文本 / 中途异常」几种死法。
  const armFlushWatchdog = useCallback(
    (wait = 1500) => {
      const typing = typingRef.current
      // 已经收尾（done/quiz 都被取走）就不用挂了，免得留一个空转的定时器
      if (!typing.id || (!typing.done && !typing.quiz)) return
      if (typing.flush !== null) window.clearTimeout(typing.flush)
      typing.flush = window.setTimeout(() => {
        typing.flush = null
        flushTyping()
      }, wait)
    },
    [flushTyping],
  )

  const drainTyping = useCallback(() => {
    const typing = typingRef.current
    typing.raf = null
    if (!typing.id) return

    // 每帧按队列长度自适应吞吐：追赶时一次多吐，接近追平时小口吐，保证观感连续
    const budget = Math.max(4, Math.min(48, Math.ceil(typing.queue.length / 16)))
    let take = Math.min(budget, typing.queue.length)
    const head = typing.queue.slice(0, take)
    const dollars = (head.match(/\$/g) || []).length
    if (dollars % 2 === 1) {
      const idx = head.lastIndexOf('$')
      if (idx > 0) take = idx
    }
    const chunk = typing.queue.slice(0, take)
    if (chunk) {
      typing.queue = typing.queue.slice(take)
      setMessages((previous) =>
        previous.map((message) =>
          message.id === typing.id
            ? { ...message, content: message.content + chunk, streaming: true }
            : message,
        ),
      )
      // 注意：这里**不**滚动。跟随底部统一由下面 messages 的 layout effect 负责。
      // 以前这里也滚一次，于是每帧两次「读 scrollHeight + 写 scrollTop」= 强制布局两遍，
      // 帧预算白烧（红队 P2-9，实测 1.82 次布局 / chunk）。
    }
    if (typing.queue) {
      typing.raf = window.requestAnimationFrame(drainTyping)
    } else {
      typing.raf = null
      // 队列吐完时：只有已经收到终止事件（quiz/done）才收尾。
      // 还在流式传输中就不能收尾——那只是「这一批吐完了」，提前收尾会让气泡
      // 闪回思考态、并让 StreamingMarkdown 卸载重挂（整篇 markdown 重解析）。
      // 反之，终止事件已到却没人收尾，就是 P1-7 那个「永远在写」的死锁。
      if (typing.done || typing.quiz) finishTyping()
    }
  }, [finishTyping])

  const enqueueContent = useCallback(
    (id: string, text: string) => {
      if (!text) return
      const typing = typingRef.current
      if (typing.id !== id) {
        if (typing.timer !== null) window.clearInterval(typing.timer)
        typing.id = id
        typing.queue = ''
        typing.timer = null
        typing.quiz = null
        typing.done = null
        typing.startedAt = Date.now()
        typing.teacherId = id
      }
      typing.queue += text
      if (typing.raf === null && typing.timer === null) {
        typing.raf = window.requestAnimationFrame(drainTyping)
      }
    },
    [drainTyping],
  )

  const queueQuiz = useCallback(
    (id: string, quiz: QuizCardData) => {
      const typing = typingRef.current
      if (typing.id !== id) {
        typing.id = id
        typing.startedAt = Date.now()
      }
      typing.quiz = quiz
      if (typing.timer === null && !typing.queue) finishTyping()
    },
    [finishTyping],
  )

  const queueDone = useCallback(
    (id: string, event: TeachStreamEvent, startedAt: number) => {
      const typing = typingRef.current
      if (typing.id !== id) {
        typing.id = id
        typing.startedAt = startedAt
      }
      typing.done = event
      if (typing.timer === null && !typing.queue) finishTyping()
    },
    [finishTyping],
  )

  useEffect(
    () => () => {
      const typing = typingRef.current
      if (typing.timer !== null) window.clearInterval(typing.timer)
      if (typing.raf !== null) window.cancelAnimationFrame(typing.raf)
      if (typing.flush !== null) window.clearTimeout(typing.flush)
    },
    [],
  )

  useIsomorphicLayoutEffect(() => {
    stickToBottomRef.current = true
    const element = scrollRef.current
    if (element) scrollToBottom(element)
  }, [started])

  useIsomorphicLayoutEffect(() => {
    // 跟随底部的唯一入口：每帧最多读一次 scrollHeight（读它就是一次强制布局）。
    // 用户自己翻上去时直接 return，一次布局也不做（红队 P2-9）。
    if (!stickToBottomRef.current) return
    const element = scrollRef.current
    if (element) scrollToBottom(element)
  }, [messages])

  const reset = useCallback(() => {
    setStarted(false)
    setMessages([])
    setSessionId(null)
    setPhase('idle')
    setRound(0)
    setMaxRounds(5)
    setActiveQuizId(null)
    setError(null)
  }, [])

  const start = useCallback(
    async (options?: {
      topic?: string
      studentMessage?: string
      history?: HistoryInput[]
      append?: boolean
      kp?: { id: string; name: string }
      /** 知识点内部的子项（左侧树展开后点的那一条）：讲义与题目只围绕它 */
      focus?: string
    }) => {
      const kp = options?.kp ?? null
      const topic = (options?.topic ?? (kp ? kp.name : draft)).trim()
      const focus = (options?.focus ?? '').trim()
      const append = options?.append ?? false
      const studentMessage = options?.studentMessage ?? ''
      if (!topic || phase === 'loading') return
      setStarted(true)
      setPhase('loading')
      setError(null)
      setSessionId(null)
      setMasteredKp(null)
      if (kp) {
        setRoundKp({ id: kp.id, name: kp.name })
        setActiveKpId(kp.id)
      } else {
        setRoundKp(null)
      }
      if (!append) {
        setMessages([])
        setRound(0)
      }
      setActiveQuizId(null)

      const teacherId = newId()
      if (typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.location.search.includes('e2e=1'))) {
        const w = window as unknown as { __MN_STREAM_START__?: number; __MN_TTFT__?: number }
        w.__MN_STREAM_START__ = Date.now()
        w.__MN_TTFT__ = undefined
      }
      const base: TeachingMessage[] = []
      if (append) {
        if (studentMessage) {
          base.push({ id: newId(), role: 'student', content: studentMessage })
        }
      } else {
        base.push({ id: newId(), role: 'student', content: focus ? `${topic}｜${focus}` : topic })
      }
      base.push({ id: teacherId, role: 'teacher', content: '', reasoning: '', streaming: true })
      if (append) setMessages((previous) => [...previous, ...base])
      else setMessages(base)

      let doneSeen = false
      let hadError = false
      const startedAt = Date.now()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamPost(
          '/api/teach_proxy/stream',
          {
            action: 'turn',
            kp_id: kp?.id ?? null,
            student_id: 'local-user',
            topic,
            level,
            subject: '数学一',
            prior_knowledge: prior,
            misconceptions: '以为导数就是背公式，不会模式识别',
            focus,
            student_message: studentMessage,
            history: options?.history ?? [],
            max_rounds: 3,
          },
          controller.signal,
        (rawEvent) => {
          const event = rawEvent as unknown as TeachStreamEvent
          if (event.type === 'meta') {
            setSessionId(event.session_id)
            if (typeof event.round === 'number') setRound(event.round)
            if (typeof event.max_rounds === 'number') setMaxRounds(event.max_rounds)
            return
          }
          if (event.type === 'reasoning') {
            setMessages((previous) =>
              previous.map((message) =>
                message.id === teacherId
                  ? {
                      ...message,
                      reasoning: (message.reasoning ?? '') + event.text,
                      streaming: true,
                    }
                  : message,
              ),
            )
            return
          }
          if ((event as { type: string }).type === 'reset') {
            const typing = typingRef.current
            typing.queue = ''
            typing.id = teacherId
            typing.startedAt = startedAt
            if (typing.timer !== null) {
              window.clearInterval(typing.timer)
              typing.timer = null
            }
            setMessages((previous) =>
              previous.map((message) =>
                message.id === teacherId ? { ...message, content: '' } : message,
              ),
            )
            return
          }
          if (event.type === 'content') {
            if (typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.location.search.includes('e2e=1'))) {
              const w = window as unknown as { __MN_STREAM_START__?: number; __MN_TTFT__?: number }
              if (!w.__MN_TTFT__ && w.__MN_STREAM_START__) {
                w.__MN_TTFT__ = Date.now() - w.__MN_STREAM_START__
              }
            }
            enqueueContent(teacherId, event.text)
            return
          }
          if (event.type === 'quiz') {
            queueQuiz(teacherId, event.quiz_card)
            return
          }
          if (event.type === 'quiz_pack') {
            // 题卡到达时打字机可能还在吐字：这时不要把 streaming 拧成 false，
            // 否则 StreamingMarkdown / MarkdownMessage 会来回换组件，整篇重解析闪一下。
            const typingNow = typingRef.current
            const stillTyping =
              typingNow.id === teacherId && (typingNow.queue.length > 0 || typingNow.raf !== null)
            setMessages((previous) =>
              previous.map((message) =>
                message.id === teacherId
                  ? {
                      ...message,
                      quizPack: event.quiz_pack,
                      kpId: event.kp_id ?? kp?.id ?? null,
                      kpName: event.kp_name ?? kp?.name,
                      streaming: stillTyping ? message.streaming : false,
                    }
                  : message,
              ),
            )
            setActiveQuizId(teacherId)
            softFollow()
            return
          }
          if (event.type === 'done') {
            doneSeen = true
            queueDone(teacherId, event, startedAt)
            return
          }
          if (event.type === 'error') {
            hadError = true
            setPhase('error')
            setError(event.message)
          }
        },
      )
      if (!doneSeen && !hadError) {
        setPhase('error')
        setError('流式连接提前结束，没有收到完成事件。')
      }
      // done 已到：给打字机 1.5s 自己排空；排不空（后台标签页 rAF 被挂起、
      // 极端长文本）就强制倒出来收尾，绝不让气泡卡在「老师正在写…」。
      if (doneSeen) armFlushWatchdog()
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setPhase('error')
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (abortRef.current === controller) abortRef.current = null
      }
    },
    [draft, level, phase, prior, armFlushWatchdog],
  )

  // 侧边栏点知识点 → 自动拉起这一轮教学
  useEffect(() => {
    if (!pendingStart) return
    clearPendingStart()
    void start({
      kp: { id: pendingStart.kp.id, name: pendingStart.kp.name },
      focus: pendingStart.focus,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingStart])

  const handlePackMastered = useCallback(
    async (kpId: string | null | undefined, kpName?: string) => {
      const id = kpId || roundKp?.id
      const name = kpName || roundKp?.name || '当前知识点'
      if (!id) return
      await markMastered(id, 100)
      setMasteredKp({ id, name })
      try {
        setLedger(await getJSON<{
          kp_name: string
          attempts: number
          correct: number
          mastery: { score: number; explain: string }
          first_break: string
          misconception: string
          next_review: { stage: number; in_days: number } | null
        }>(`/api/ledger?kp_id=${encodeURIComponent(id)}`))
      } catch {
        setLedger(null)
      }
      setMessages((previous) => [
        ...previous,
        {
          id: newId(),
          role: 'system',
          content: `「${name}」三道题全部通过，已写入知识树（左侧打勾）。可以进入下一个知识点，或换一个模块。`,
        },
      ])
      advanceToBottom()
    },
    [advanceToBottom, markMastered, roundKp],
  )

  // 通关后 3 秒自动开下一站（只倒计时一次，可取消）
  useEffect(() => {
    if (!masteredKp || !tree?.next_kp) {
      setAutoAdvanceIn(0)
      return
    }
    setAutoAdvanceIn(3)
    autoAdvanceCancelled.current = false
    const nextKp = { id: tree.next_kp.id, name: tree.next_kp.name }
    const timer = window.setTimeout(() => {
      if (autoAdvanceCancelled.current) return
      setMasteredKp(null)
      setAutoAdvanceIn(0)
      void start({ kp: nextKp })
    }, 3000)
    const tick = window.setInterval(() => setAutoAdvanceIn((v) => (v > 0 ? v - 1 : 0)), 1000)
    return () => {
      window.clearTimeout(timer)
      window.clearInterval(tick)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [masteredKp, tree?.next_kp?.id])

  // 再练一组：同知识点只出题不重讲（约 4~10 秒，比重新讲一遍快得多）
  const practiceMore = useCallback(async () => {
    const kpId = masteredKp?.id ?? roundKp?.id
    const kpName = masteredKp?.name ?? roundKp?.name ?? ''
    if (!kpId || practiceBusy) return
    setPracticeBusy(true)
    try {
      const data = await postJSON<{ questions: QuizQuestion[] }>('/api/practice_more', { kp_id: kpId })
      if (Array.isArray(data.questions) && data.questions.length) {
        const id = newId()
        setMessages((previous) => [
          ...previous,
          {
            id,
            role: 'teacher',
            content: '',
            quizPack: data.questions,
            kpId,
            kpName: `${kpName} · 加练`,
            drill: true,
            streaming: false,
          },
        ])
        setActiveQuizId(id)
        setMasteredKp(null)
        setLedger(null)
        setAutoAdvanceIn(0)
        advanceToBottom()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPracticeBusy(false)
    }
  }, [advanceToBottom, masteredKp, practiceBusy, roundKp])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    setPhase('idle')
  }, [])

  const ask = useCallback(
    (text: string) => {
      const message = text.trim()
      if (!message || phase === 'loading') return
      if (!started) {
        void start({ topic: message })
        return
      }
      const history = messages
        .filter(
          (item) =>
            (item.role === 'student' || item.role === 'teacher') && item.content.trim(),
        )
        .map((item) => ({
          role: item.role as 'student' | 'teacher',
          content: item.content,
        }))
      void start({
        topic: draft.trim() || DEFAULT_TOPIC,
        studentMessage: message,
        history,
        append: true,
      })
    },
    [draft, messages, phase, start, started],
  )

  const handleLasso = useCallback(async (image: string) => {
    setLassoOpen(true)
    setLassoLoading(true)
    setLassoError(null)
    setLassoAnchor('')
    try {
      const data = await postJSON<{ text: string }>('/api/vision', { image })
      setLassoAnchor(data.text || '')
    } catch (err) {
      setLassoError(err instanceof Error ? err.message : String(err))
    } finally {
      setLassoLoading(false)
    }
  }, [])

  const generateLasso = useCallback(() => {
    if (!lassoAnchor.trim() || !lassoPrompt.trim()) return
    const message = `【圈选内容】
${lassoAnchor}

【我的要求】
${lassoPrompt}`
    setLassoOpen(false)
    setPenMode(false)
    void ask(message)
  }, [ask, lassoAnchor, lassoPrompt])

  const answer = useCallback(
    async (value: string) => {
      if (!sessionId || !activeQuizId || phase !== 'awaiting') return
      const quizId = activeQuizId
      setPhase('loading')
      setError(null)
      setMessages((previous) =>
        previous.map((message) =>
          message.id === quizId ? { ...message, selected: value } : message,
        ),
      )

      let teacherId: string | null = null
      let doneSeen = false
      let hadError = false
      const startedAt = Date.now()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamPost(
          '/api/teach_proxy/stream',
          { action: 'answer', session_id: sessionId, answer: value },
          controller.signal,
          (rawEvent) => {
            const event = rawEvent as unknown as TeachStreamEvent
            if (event.type === 'meta') {
              setSessionId(event.session_id)
              return
            }
            if (event.type === 'judgement') {
              setMessages((previous) =>
                previous.map((message) =>
                  message.id === quizId
                    ? { ...message, selected: value, judgement: event.judgement, streaming: false }
                    : message,
                ),
              )
                return
            }
            if (event.type === 'reasoning' || event.type === 'content') {
              if (!teacherId) {
                teacherId = newId()
                const currentTeacherId = teacherId
                setMessages((previous) => [
                  ...previous,
                  {
                    id: currentTeacherId,
                    role: 'teacher',
                    content: '',
                    reasoning: '',
                    streaming: true,
                  },
                ])
              }
              const currentTeacherId = teacherId
              if (event.type === 'reasoning') {
                setMessages((previous) =>
                  previous.map((message) =>
                    message.id === currentTeacherId
                      ? {
                          ...message,
                          reasoning: (message.reasoning ?? '') + event.text,
                          streaming: true,
                        }
                      : message,
                  ),
                )
              } else {
                enqueueContent(currentTeacherId, event.text)
              }
              return
            }
            if (event.type === 'quiz') {
              if (teacherId) queueQuiz(teacherId, event.quiz_card)
              return
            }
            if (event.type === 'done') {
              doneSeen = true
              if (teacherId) {
                queueDone(teacherId, event, startedAt)
              } else {
                finalizeDone(event, '', startedAt)
              }
              return
            }
            if (event.type === 'error') {
              hadError = true
              setPhase('error')
              setError(event.message)
            }
          },
        )
        if (!doneSeen && !hadError) {
          setPhase('error')
          setError('流式连接提前结束，没有收到完成事件。')
        }
        if (doneSeen) armFlushWatchdog()
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setPhase('error')
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (abortRef.current === controller) abortRef.current = null
      }
    },
    [activeQuizId, phase, sessionId, armFlushWatchdog],
  )

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          onWheel={handleWheel}
          className="paper-canvas scrollbar-thin h-full overflow-y-auto [overflow-anchor:none]"
        >
      <PixelStyles />
      <div className="mx-auto flex w-full max-w-[760px] flex-col gap-7 px-6 pt-7 pb-10">
        {!started ? (
          <section className="rounded-xl border border-border/65 bg-card/55 p-5">
            <div className="mb-3 flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
                <GraduationCap className="size-4" />
              </span>
              <div>
                <h2 className="font-serif text-[18px] font-semibold tracking-tight">从一句话开始</h2>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  告诉老师你想学什么；老师先讲第一层，再出一张题卡。
                </p>
              </div>
            </div>

            <label className="mb-1.5 block text-[10.5px] font-medium text-muted-foreground" htmlFor="teach-topic-v2">
              想学什么
            </label>
            <textarea
              id="teach-topic-v2"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={3}
              className="w-full resize-none rounded-lg border border-border/70 bg-background/70 px-3 py-2.5 text-[13px] leading-6 outline-none transition-colors focus:border-primary/55"
            />
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <select
                value={level}
                onChange={(event) => setLevel(event.target.value as (typeof LEVELS)[number])}
                className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-[12px] outline-none focus:border-primary/55"
              >
                {LEVELS.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
              <input
                value={prior}
                onChange={(event) => setPrior(event.target.value)}
                placeholder="已有基础"
                className="rounded-lg border border-border/70 bg-background/70 px-3 py-2 text-[12px] outline-none focus:border-primary/55"
              />
            </div>
            <button
              type="button"
              onClick={() => void start()}
              disabled={!draft.trim() || phase === 'loading'}
              className="mt-3 inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-[11.5px] font-medium text-primary-foreground disabled:opacity-40"
            >
              {phase === 'loading' ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
              开始上课
            </button>
          </section>
        ) : (
          <div className="flex flex-col gap-7">
            <div className="flex items-center justify-between border-b border-border/50 pb-2 text-[10px] text-muted-foreground">
              <span>第 <b className="font-mono text-foreground">{Math.min(round + 1, maxRounds)}</b> / {maxRounds} 轮</span>
              <span>
                {phase === 'awaiting'
                  ? '等待作答'
                  : phase === 'loading'
                    ? '老师正在写…'
                    : phase === 'done'
                      ? '已完成'
                      : ''}
              </span>
              <button
                type="button"
                onClick={reset}
                className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
              >
                <RefreshCw className="size-3" /> 重新开始
              </button>
            </div>

            {messages.map((message) => {
              if (message.role === 'student') {
                return (
                  <div key={message.id} className="flex justify-end">
                    <div className="max-w-[84%] rounded-2xl rounded-tr-md border border-border/50 bg-muted/70 px-4 py-2.5">
                      <MarkdownMessage content={message.content} className="text-[13.5px] leading-6" />
                    </div>
                  </div>
                )
              }
              if (message.role === 'system') {
                return (
                  <div key={message.id} className="rounded-xl border border-primary/20 bg-primary/[0.06] px-4 py-3 text-[12px] text-foreground/75">
                    {message.content}
                  </div>
                )
              }
              return (
                <article key={message.id} className="flex flex-col gap-3">
                  <div className="flex items-center gap-2 text-[9.5px] font-medium tracking-[0.16em] text-primary uppercase">
                    <span className="grid size-5 place-items-center rounded-md bg-primary/10">
                      <GraduationCap className="size-3" />
                    </span>
                    老师
                  </div>
                  {(message.reasoning || message.streaming) && (
                    <ThinkingBox
                      text={message.reasoning ?? ''}
                      seconds={message.thinkingSeconds ?? 1}
                      streaming={message.streaming}
                    />
                  )}
                  <div>
                    {message.streaming ? (
                      <StreamingMarkdown content={trimIncompleteMarkdown(message.content)} />
                    ) : (
                      <MarkdownMessage content={message.content} />
                    )}
                    {message.streaming && message.content && (
                      <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse rounded-full bg-primary align-middle" />
                    )}
                  </div>
                  {message.quiz && (
                    <PixelQuizCard
                      quiz={message.quiz}
                      selected={message.selected}
                      judgement={message.judgement}
                      busy={phase === 'loading'}
                      onAnswer={(value) => void answer(value)}
                      onAdvance={advanceToBottom}
                    />
                  )}
                  {message.quizPack && message.quizPack.length > 0 && (
                    <QuizPack
                      questions={message.quizPack}
                      kpId={message.kpId ?? roundKp?.id ?? null}
                      kpName={message.kpName ?? roundKp?.name}
                      onMastered={() => {
                        if (message.drill) {
                          setMessages((previous) => [
                            ...previous,
                            { id: newId(), role: 'system', content: '加练完成。要换知识点就从左侧选一个，或点「进入下一站」。' },
                          ])
                          return
                        }
                        void handlePackMastered(message.kpId, message.kpName)
                      }}
                      onProgress={softFollow}
                    />
                  )}
                </article>
              )
            })}

            {phase === 'loading' && !messages.some((message) => message.streaming) && (
              <div className="flex items-center gap-2 rounded-lg border border-border/55 bg-card/50 px-3 py-2.5 text-[11px] text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin text-primary" />
                老师正在组织这一层…
              </div>
            )}

            {phase === 'error' && error && (
              <div className="rounded-lg border border-destructive/35 bg-destructive/[0.05] px-3 py-2.5 text-[11.5px] leading-5 text-destructive">
                <div className="mb-1 font-semibold">生成失败</div>
                <div className="whitespace-pre-wrap">{error}</div>
                <button type="button" onClick={reset} className="mt-2 rounded border border-destructive/30 px-2 py-1 text-[10px]">
                  重新开始
                </button>
              </div>
            )}

            {ledger && (
              <div className="rounded-xl border border-border/70 bg-card/60 px-4 py-3">
                <div className="flex items-center gap-2 text-[12px] font-medium text-foreground/85">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  本次账本 · {ledger.kp_name}
                </div>
                <table className="mt-2 w-full text-[11.5px]">
                  <tbody>
                    <tr><td className="py-0.5 align-top text-muted-foreground">累计作答</td><td className="text-right align-top tabular-nums">{ledger.attempts} 题，对 {ledger.correct} 题</td></tr>
                    <tr><td className="py-0.5 text-muted-foreground">掌握度</td><td className="text-right tabular-nums">{Math.round(ledger.mastery.score * 100)}%</td></tr>
                    {ledger.first_break && (
                      <tr><td className="py-0.5 align-top text-muted-foreground">最早断点</td><td className="break-words text-right align-top text-rose-700">{ledger.first_break}</td></tr>
                    )}
                    {ledger.misconception && (
                      <tr><td className="py-0.5 align-top text-muted-foreground">认知偏差</td><td className="break-words text-right align-top text-amber-800">{ledger.misconception}</td></tr>
                    )}
                    <tr><td className="py-0.5 text-muted-foreground">下次复习</td><td className="text-right">{ledger.next_review ? `${ledger.next_review.in_days} 天后` : '已排入明天'}</td></tr>
                  </tbody>
                </table>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    data-practice-more="1"
                    onClick={() => void practiceMore()}
                    disabled={practiceBusy}
                    className="inline-flex items-center gap-1 rounded-lg border border-primary/40 bg-primary/[0.07] px-2.5 py-1.5 text-[11.5px] text-primary disabled:opacity-50"
                  >
                    {practiceBusy ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
                    {practiceBusy ? '出题中…' : '再练一组'}
                  </button>
                  <span className="text-[10.5px] text-muted-foreground">同知识点只出题，不重讲</span>
                </div>
              </div>
            )}

            {masteredKp && tree?.next_kp && (
              <div className="flex flex-col gap-2 rounded-xl border border-emerald-500/35 bg-emerald-500/[0.07] px-4 py-3.5">
                <div className="flex items-center gap-2 text-[12.5px] font-medium text-emerald-800">
                  <CheckCircle2 className="size-4" />
                  「{masteredKp.name}」通关，下一站：{tree.next_kp.name}
                  {autoAdvanceIn > 0 && (
                    <span className="rounded-full bg-emerald-600/10 px-2 py-0.5 text-[11px] text-emerald-700">
                      {autoAdvanceIn} 秒后自动开始
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setMasteredKp(null)
                      setAutoAdvanceIn(0)
                      void start({ kp: { id: tree.next_kp!.id, name: tree.next_kp!.name } })
                    }}
                    className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-emerald-600/40 bg-emerald-600 px-3 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-emerald-700"
                  >
                    马上进入
                    <CheckCircle2 className="size-3.5" />
                  </button>
                  {autoAdvanceIn > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        autoAdvanceCancelled.current = true
                        setAutoAdvanceIn(0)
                      }}
                      className="rounded-lg border border-border/70 px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-muted/40"
                    >
                      先别切
                    </button>
                  )}
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
        </div>
        </div>
        <PenOverlay
          active={penMode && started}
          busy={phase === 'loading'}
          onCapture={(image) => void handleLasso(image)}
          onError={(message) => {
            setLassoError(message)
            setLassoOpen(true)
          }}
          onWheel={(deltaY) => scrollRef.current?.scrollBy({ top: deltaY })}
        />
      </div>

      {started && !following && (
        <button
          type="button"
          data-jump-bottom="1"
          onClick={() => {
            stickToBottomRef.current = true
            setFollowing(true)
            if (scrollRef.current) scrollToBottom(scrollRef.current)
          }}
          className="fixed bottom-32 left-1/2 z-30 -translate-x-1/2 sm:bottom-28 rounded-full border border-border/70 bg-background/95 px-3.5 py-1.5 text-[12px] text-foreground shadow-md backdrop-blur"
        >
          回到底部 ↓
        </button>
      )}

      {started && !assistOpen && (
        <button
          type="button"
          data-assist-open="1"
          onClick={() => setAssistOpen(true)}
          className="fixed right-4 bottom-32 z-30 sm:bottom-28 sm:right-5 inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary px-3.5 py-2 text-[12px] font-medium text-white shadow-lg transition-transform hover:-translate-y-0.5"
        >
          <MessageCircleQuestion className="size-4" />
          问老师 · 错题本
        </button>
      )}

      <AssistPanel
        open={assistOpen}
        onClose={() => setAssistOpen(false)}
        kpId={roundKp?.id ?? null}
        kpName={roundKp?.name}
        lesson={[...messages].reverse().find((m) => m.role === 'teacher' && m.content)?.content ?? ''}
        question={activeQuizId ? (messages.find((m) => m.id === activeQuizId)?.quizPack?.[0]?.stem ?? '') : ''}
      />

      {started && (
        <MainComposer
          onSend={(text) => void ask(text)}
          onStop={stop}
          streaming={phase === 'loading'}
          penMode={penMode}
          onPenModeChange={setPenMode}
          deepThink
          onDeepThinkChange={() => {}}
          hasRun={started}
          penDisabled={!started}
          showDeepThink={false}
        />
      )}

      <LassoPromptDialog
        open={lassoOpen}
        loading={lassoLoading}
        error={lassoError}
        anchorText={lassoAnchor}
        prompt={lassoPrompt}
        onAnchorChange={setLassoAnchor}
        onPromptChange={setLassoPrompt}
        onCancel={() => {
          setLassoOpen(false)
          setPenMode(false)
        }}
        onGenerate={generateLasso}
      />
    </div>
  )
}
