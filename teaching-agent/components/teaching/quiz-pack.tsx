'use client'

import { useCallback, useMemo, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronRight, Loader2, Mic, MicOff, RotateCcw, Sparkles, Stethoscope, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { postJSON } from '@/lib/client-api'
import { MarkdownMessage } from '@/components/math/markdown'
import {
  DIFFICULTY_LABEL,
  DIFFICULTY_TONE,
  type JudgeResult,
  type QuizQuestion,
} from '@/lib/quiz-types'

type Props = {
  questions: QuizQuestion[]
  kpId?: string | null
  kpName?: string
  onMastered: () => void
  onProgress?: (correct: number, total: number) => void
}

type AnswerState = {
  value: string
  result: JudgeResult | null
  pending: boolean
}

const EMPTY: AnswerState = { value: '', result: null, pending: false }

/**
 * 三阶梯题卡：基础母题 → 技巧进阶 → 考研真题。
 *
 * 答对才解锁下一关；答错展示陷阱归因并允许重试。
 * 判定走后端 /api/judge（SymPy 五层），不消耗 token，所以可以随便点。
 */
export function QuizPack({ questions, kpId, kpName, onMastered, onProgress }: Props) {
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, AnswerState>>({})
  const [solved, setSolved] = useState<Record<number, boolean>>({})
  const [mastered, setMastered] = useState(false)
  const [shake, setShake] = useState(false)
  const [fillValue, setFillValue] = useState('')
  const celebrated = useRef(false)
  // 思路诊断（旁路 LLM，不写主对话）
  const [diagOpen, setDiagOpen] = useState(false)
  const [diagText, setDiagText] = useState('')
  const [diagBusy, setDiagBusy] = useState(false)
  const [diagResult, setDiagResult] = useState<null | {
    steps: { step: string; ok: boolean; issue: string }[]
    first_break: string
    misconception: string
    fix: string
    severity: string
  }>(null)
  const [diagListening, setDiagListening] = useState(false)
  const diagRec = useRef<unknown>(null)

  useEffect(() => {
    setIndex(0)
    setAnswers({})
    setSolved({})
    setMastered(false)
    setFillValue('')
    celebrated.current = false
    // 仅开发环境暴露题卡，供 e2e 脚本自动作答（生产构建不会带这段）
    if (typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.location.search.includes('e2e=1'))) {
      ;(window as unknown as { __MN_QUIZ_PACK__?: QuizQuestion[] }).__MN_QUIZ_PACK__ = questions
    }
  }, [questions])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      ;(window as unknown as { __MN_QUIZ_INDEX__?: number }).__MN_QUIZ_INDEX__ = index
    }
  }, [index])

  const current = questions[index]
  const state = answers[index] ?? EMPTY

  const correctCount = useMemo(() => Object.values(solved).filter(Boolean).length, [solved])

  useEffect(() => {
    onProgress?.(correctCount, questions.length)
  }, [correctCount, questions.length, onProgress])

  const submit = useCallback(
    async (value: string) => {
      if (!current || !value.trim() || state.pending) return
      const letter = current.kind === 'choice' ? value.trim().charAt(0).toUpperCase() : ''
      const answerValue = current.kind === 'choice' ? letter : value.trim()
      setAnswers((prev) => ({ ...prev, [index]: { value: answerValue, result: null, pending: true } }))
      try {
        const result = await postJSON<JudgeResult>('/api/judge', {
          question: current,
          answer: answerValue,
          kp_id: kpId ?? '',
          kp_name: kpName ?? '',
          student_id: 'local-user',
        })
        setAnswers((prev) => ({ ...prev, [index]: { value: answerValue, result, pending: false } }))
        if (result.correct) {
          setSolved((prev) => ({ ...prev, [index]: true }))
          setFillValue('')
        } else {
          setShake(true)
          window.setTimeout(() => setShake(false), 420)
        }
      } catch (error) {
        setAnswers((prev) => ({
          ...prev,
          [index]: {
            value: answerValue,
            result: {
              correct: false,
              layer: 'error',
              reason: error instanceof Error ? error.message : String(error),
              correct_answer: current.answer,
              explanation: '',
              elapsed_ms: 0,
            },
            pending: false,
          },
        }))
      }
    },
    [current, index, state.pending],
  )

  const next = useCallback(() => {
    if (index + 1 < questions.length) {
      setIndex(index + 1)
      return
    }
    const allSolved = questions.every((_, i) => solved[i])
    if (allSolved && !celebrated.current) {
      celebrated.current = true
      setMastered(true)
      onMastered()
    }
  }, [index, onMastered, questions, solved])

  const toggleDiagVoice = useCallback(() => {
    const w = window as unknown as { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any }
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
    if (!Ctor) return
    if (diagListening) {
      try { (diagRec.current as { stop: () => void })?.stop() } catch {}
      setDiagListening(false)
      return
    }
    const rec = new Ctor()
    rec.lang = 'zh-CN'
    rec.interimResults = true
    rec.continuous = false
    rec.onresult = (event: any) => {
      let text = ''
      for (let i = 0; i < event.results.length; i += 1) text += event.results[i][0].transcript
      setDiagText(text)
    }
    rec.onend = () => setDiagListening(false)
    rec.onerror = () => setDiagListening(false)
    diagRec.current = rec
    setDiagListening(true)
    rec.start()
  }, [diagListening])

  const submitDiagnosis = useCallback(async () => {
    const reasoning = diagText.trim()
    if (!reasoning || diagBusy || !current) return
    setDiagBusy(true)
    try {
      const data = await postJSON<{
        steps: { step: string; ok: boolean; issue: string }[]
        first_break: string
        misconception: string
        fix: string
        severity: string
      }>('/api/diagnose', {
        kp_id: kpId ?? '',
        kp_name: kpName ?? '',
        question: current.stem,
        student_answer: state.value,
        reasoning,
      })
      setDiagResult(data)
    } catch (err) {
      setDiagResult({
        steps: [],
        first_break: err instanceof Error ? err.message : String(err),
        misconception: '',
        fix: '',
        severity: 'concept',
      })
    } finally {
      setDiagBusy(false)
    }
  }, [diagBusy, diagText, current, kpId, kpName, state.value])

  // 答对后自动推进：0.7s 展示解析 → 下一题；最后一题 → 通关
  useEffect(() => {
    if (!solved[index] || mastered) return
    const timer = window.setTimeout(() => next(), 700)
    return () => window.clearTimeout(timer)
  }, [solved, index, mastered, next])

  if (!current) return null

  const allSolved = questions.every((_, i) => solved[i])
  const tone = DIFFICULTY_TONE[current.difficulty] ?? DIFFICULTY_TONE.medium
  const result = state.result

  return (
    <div className="quiz-pack mt-4 overflow-hidden rounded-2xl border border-border/70 bg-card/70 shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-border/60 bg-muted/25 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="grid size-6 place-items-center rounded-md bg-primary/12 text-[11px] font-bold text-primary">
            {index + 1}
          </span>
          <span className="truncate text-[12px] font-medium text-foreground/85">
            {kpName ? `知识点 · ${kpName}` : '本轮题卡'}
          </span>
          {current.type_name && (
            // 题型标签：来自《张宇基础30讲》的题型层，让学生知道这题在练哪个题型
            <span
              title={`教材题型：${current.type_name}`}
              className="max-w-[260px] shrink-0 truncate rounded-full bg-primary/10 px-1.5 py-0.5 text-[9.5px] font-medium text-primary"
            >
              {current.type_name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {questions.map((q, i) => (
            <span
              key={i}
              title={DIFFICULTY_LABEL[q.difficulty]}
              className={cn(
                'h-1.5 w-6 rounded-full transition-colors',
                solved[i] ? 'bg-emerald-500' : i === index ? 'bg-primary/70' : 'bg-border',
              )}
            />
          ))}
          <span className={cn('ml-1 rounded-full border bg-gradient-to-b px-2 py-0.5 text-[10px] font-medium', tone)}>
            {DIFFICULTY_LABEL[current.difficulty]}
          </span>
        </div>
      </div>

      <div className={cn('px-4 py-4', shake && 'quiz-pack-shake')}>
        <div className="text-[15px] leading-[1.9]">
          <MarkdownMessage content={current.stem} />
        </div>

        {current.kind === 'choice' ? (
          <div className="mt-3 grid gap-2">
            {current.options.map((option, i) => {
              const letter = String.fromCharCode(65 + i)
              const chosen = state.value === letter
              const right = result?.correct && chosen
              const wrong = result && !result.correct && chosen
              return (
                <button
                  key={letter}
                  type="button"
                  data-quiz-option={letter}
                  disabled={Boolean(solved[index]) || state.pending}
                  onClick={() => void submit(letter)}
                  className={cn(
                    'group flex items-start gap-2.5 rounded-xl border px-3 py-2 text-left text-[13.5px] leading-6 transition-all',
                    'border-border/70 bg-background/60 hover:border-primary/45 hover:bg-primary/[0.04]',
                    chosen && !result && 'border-primary/60 bg-primary/[0.06]',
                    right && 'border-emerald-500/70 bg-emerald-500/[0.08] text-emerald-900',
                    wrong && 'border-rose-500/70 bg-rose-500/[0.08] text-rose-900',
                    solved[index] && !chosen && 'opacity-55',
                  )}
                >
                  <span
                    className={cn(
                      'mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border text-[11px] font-semibold',
                      right
                        ? 'border-emerald-500 bg-emerald-500 text-white'
                        : wrong
                          ? 'border-rose-500 bg-rose-500 text-white'
                          : 'border-border bg-muted/40 text-foreground/70',
                    )}
                  >
                    {right ? <Check className="size-3" /> : wrong ? <X className="size-3" /> : letter}
                  </span>
                  <span className="min-w-0 flex-1">
                    <MarkdownMessage content={option} />
                  </span>
                </button>
              )
            })}
          </div>
        ) : (
          <div className="mt-3 flex items-center gap-2">
            <input
              value={fillValue}
              data-quiz-input="1"
              onChange={(event) => setFillValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void submit(fillValue)
              }}
              disabled={Boolean(solved[index]) || state.pending}
              placeholder="填写答案，回车提交（支持 1/2、sqrt(2)、2x+1 这类写法）"
              className="min-w-0 flex-1 rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-[13.5px] outline-none focus:border-primary/60"
            />
            <button
              type="button"
              data-quiz-submit="1"
              onClick={() => void submit(fillValue)}
              disabled={!fillValue.trim() || Boolean(solved[index]) || state.pending}
              className="rounded-xl border border-primary/45 bg-primary/10 px-3 py-2 text-[12.5px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:opacity-40"
            >
              {state.pending ? <Loader2 className="size-4 animate-spin" /> : '提交'}
            </button>
          </div>
        )}

        {result && (
          <div
            className={cn(
              'mt-3 rounded-xl border px-3 py-2.5 text-[12.5px] leading-6',
              result.correct
                ? 'border-emerald-500/40 bg-emerald-500/[0.06] text-emerald-900'
                : 'border-rose-500/40 bg-rose-500/[0.06] text-rose-900',
            )}
          >
            <div className="flex items-center gap-1.5 font-medium">
              {result.correct ? <Check className="size-3.5" /> : <X className="size-3.5" />}
              {result.correct ? '答对了' : '再想想'}
              <span className="ml-1 rounded bg-black/[0.05] px-1.5 py-0.5 text-[10px] font-normal opacity-70">
                {result.layer}
              </span>
            </div>
            {result.correct ? (
              <p className="mt-1">{result.explanation || current.explanation}</p>
            ) : (
              <div className="mt-1 space-y-1">
                <p>
                  陷阱归因：
                  {current.why_this_question || '这一层最容易在适用条件上出错。'}
                </p>
                {result.reason && <p className="opacity-75">判定依据：{result.reason}</p>}
              </div>
            )}
          </div>
        )}

        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-[11px] text-muted-foreground">
            已通过 {correctCount}/{questions.length}
            {state.pending && ' · 判题中…'}
            {solved[index] && !mastered && (
              <span className="ml-1.5 text-emerald-700">
                {index + 1 < questions.length ? '自动进入下一题…' : '正在结算通关…'}
              </span>
            )}
          </span>
          {solved[index] && (
            <span data-quiz-next="1" className="hidden" aria-hidden />
          )}
          {!solved[index] && result && !result.correct && (
            <button
              type="button"
              onClick={() => {
                setAnswers((prev) => ({ ...prev, [index]: EMPTY }))
                setFillValue('')
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-border/70 px-3 py-1.5 text-[12px] text-muted-foreground transition-colors hover:bg-muted/40"
            >
              <RotateCcw className="size-3.5" />
              重新作答
            </button>
          )}
          <button
            type="button"
            data-quiz-diagnose="1"
            onClick={() => {
              setDiagOpen(true)
              setDiagResult(null)
            }}
            className="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-500/[0.07] px-3 py-1.5 text-[12px] text-amber-800 transition-colors hover:bg-amber-500/12"
          >
            <Stethoscope className="size-3.5" />
            说说我的思路
          </button>
        </div>
      </div>

      {diagOpen &&
        typeof document !== 'undefined' &&
        // 用 portal 挂到 body：题卡本身渲染在 .paper-canvas 这个滚动容器里，
        // 浮动按钮（z-30）在更外层，弹窗嵌在里面时 z-50 也压不过它，
        // 底部会露出半个悬浮球（P2-3 截图里能看到）。挂到 body 才是真正的模态层级。
        createPortal(
          <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 px-4 pb-6 sm:items-center sm:pb-0">
          {/* 红队 P2-3：诊断结果能有十几步，以前弹窗没有高度上限，内容一长就顶出屏幕、
              底部按钮够不着。现在面板最高 88vh，头尾固定，中间一段单独滚动。 */}
          <div className="flex max-h-[88vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl border border-border/70 bg-background shadow-2xl">
            <div className="flex shrink-0 items-center gap-2 border-b border-border/60 px-4 py-2.5">
              <Stethoscope className="size-4 text-amber-700" />
              <span className="text-[13px] font-medium">说说你的思路</span>
              <span className="text-[10.5px] text-muted-foreground">（讲一遍，我找断点）</span>
              <button
                type="button"
                onClick={() => setDiagOpen(false)}
                className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted/50"
              >
                <X className="size-3.5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3" data-diag-body="1">
              <p className="mb-2 text-[11.5px] leading-5 text-muted-foreground">
                不用写过程，直接讲：你先看什么、用了哪个条件、卡在哪。语音会转成文字，你确认后再提交。
              </p>
              <textarea
                value={diagText}
                onChange={(e) => setDiagText(e.target.value)}
                rows={4}
                data-diag-input="1"
                placeholder="比如：我先看到 0/0，就直接用了洛必达，没检查是不是满足三个条件…"
                className="w-full resize-none rounded-xl border border-border/70 bg-background px-3 py-2 text-[12.5px] leading-6 outline-none focus:border-primary/60"
              />
              <div className="mt-2 flex items-center gap-2">
                <button
                  type="button"
                  onClick={toggleDiagVoice}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[12px]',
                    diagListening
                      ? 'border-rose-400 bg-rose-50 text-rose-600'
                      : 'border-border/70 text-muted-foreground hover:bg-muted/40',
                  )}
                >
                  {diagListening ? <MicOff className="size-3.5" /> : <Mic className="size-3.5" />}
                  {diagListening ? '停止' : '语音输入'}
                </button>
                <button
                  type="button"
                  data-diag-submit="1"
                  onClick={() => void submitDiagnosis()}
                  disabled={diagBusy || !diagText.trim()}
                  className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-medium text-white disabled:opacity-40"
                >
                  {diagBusy ? <Loader2 className="size-3.5 animate-spin" /> : <Stethoscope className="size-3.5" />}
                  诊断
                </button>
                {diagResult && (
                  <span className="text-[11px] text-emerald-700">已记入错题本</span>
                )}
              </div>

              {diagResult && (
                <div className="mt-3 space-y-1.5 rounded-xl border border-border/60 bg-muted/25 p-3 text-[12px] leading-5">
                  {diagResult.steps.length > 0 && (
                    <ul className="space-y-0.5">
                      {diagResult.steps.map((step, i) => (
                        <li key={i} className={step.ok ? 'text-foreground/75' : 'text-rose-700'}>
                          {step.ok ? '✓' : '✗'} {step.step}
                          {step.issue ? ` — ${step.issue}` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                  {diagResult.first_break && (
                    <p className="text-rose-700">最早断点：{diagResult.first_break}</p>
                  )}
                  {diagResult.misconception && (
                    <p className="text-amber-800">认知偏差：{diagResult.misconception}</p>
                  )}
                  {diagResult.fix && <p className="text-emerald-700">下一步：{diagResult.fix}</p>}
                </div>
              )}
            </div>
          </div>
        </div>,
          document.body,
        )}

      {mastered && allSolved && (
        <div className="quiz-pass flex items-center gap-2 border-t border-emerald-500/30 bg-emerald-500/[0.08] px-4 py-3 text-[12.5px] font-medium text-emerald-800">
          <Sparkles className="size-4" />
          知识点通关！已写入知识树，左侧对应节点已打勾。
        </div>
      )}

      <style jsx>{`
        .quiz-pack-shake {
          animation: quiz-pack-shake 0.42s linear;
        }
        @keyframes quiz-pack-shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-6px); }
          50% { transform: translateX(5px); }
          75% { transform: translateX(-2px); }
        }
        .quiz-pass {
          animation: quiz-pass-in 0.5s cubic-bezier(0.2, 1.3, 0.4, 1);
        }
        @keyframes quiz-pass-in {
          from { opacity: 0; transform: translateY(6px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}
