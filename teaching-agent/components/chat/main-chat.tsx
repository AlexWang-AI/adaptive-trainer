'use client'

import { memo, useEffect, useLayoutEffect, useRef } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  GitBranch,
  GraduationCap,
  Loader2,
  Play,
  Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { MarkdownMessage } from '@/components/math/markdown'
import { TeachingChat } from '@/components/teaching/teaching-chat'
import { PromptProvenance } from '@/components/prompt/prompt-provenance'
import { PenOverlay } from './pen-overlay'
import { ThinkingBox } from './thinking-box'
import { MainComposer } from './main-composer'
import type { Message } from '@/lib/types'
import type { PromptRun, WorkbenchPayload } from '@/lib/prompt-types'

const useIsomorphicLayoutEffect =
  typeof window === 'undefined' ? useEffect : useLayoutEffect

type MainChatProps = {
  payload: WorkbenchPayload | null
  activeRun: PromptRun | null
  messages: Message[]
  streaming: boolean
  penMode: boolean
  deepThink: boolean
  notice: string | null
  branchCount: number
  panelClosed: boolean
  composerSeed: { text: string; nonce: number } | null
  teachingMode: boolean
  onToggleTeachingMode: () => void
  onSend: (text: string) => void
  onStop: () => void
  onPenModeChange: (value: boolean) => void
  onDeepThinkChange: (value: boolean) => void
  onLasso: (image: string) => void
  onLassoError: (message: string) => void
  onSelectStage: (id: string) => void
  onOpenPrompt: () => void
  onOpenBranches: () => void
  onRunStage: () => void
}

function StagePromptCard({ content }: { content: string }) {
  return (
    <details className="group overflow-hidden rounded-2xl border border-border/60 bg-card/60">
      <summary className="flex cursor-pointer items-center gap-2.5 px-4 py-3 text-[11px] text-muted-foreground">
        <span className="grid size-6 shrink-0 place-items-center rounded-lg bg-primary/8 text-primary">
          <Sparkles className="size-3.5" aria-hidden="true" />
        </span>
        <span className="font-medium text-foreground/80">本阶段提示词已注入</span>
        <span className="rounded-full border border-border/60 px-1.5 py-0.5 font-mono text-[9px]">
          G · S · P
        </span>
        <span className="ml-auto hidden text-[9.5px] group-open:sm:inline">点击收起</span>
        <span className="ml-auto text-[9.5px] group-open:hidden">点击展开</span>
        <ChevronDown
          className="size-3.5 shrink-0 transition-transform duration-200 group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <pre className="scrollbar-thin max-h-80 overflow-y-auto border-t border-border/55 px-4 py-3 text-[11.5px] leading-[1.85] whitespace-pre-wrap text-foreground/65">
        {content}
      </pre>
    </details>
  )
}

const MessageItem = memo(function MessageItem({
  message,
  isLast,
  streaming,
}: {
  message: Message
  isLast: boolean
  streaming: boolean
}) {
  if (message.role === 'user') {
    if (message.kind === 'stage-prompt') {
      return <StagePromptCard content={message.content} />
    }
    return (
      <div className="flex justify-end">
        <div className="max-w-[84%] rounded-2xl rounded-tr-md border border-border/50 bg-muted/70 px-4 py-2.5">
          <MarkdownMessage content={message.content} className="text-[13.5px] leading-6" />
        </div>
      </div>
    )
  }

  const active = isLast && streaming
  const thinking = Boolean(message.reasoning) || active

  return (
    <article
      className={cn(
        'flex flex-col gap-3',
        message.error && 'rounded-2xl border border-destructive/35 bg-destructive/[0.04] p-3.5',
      )}
      aria-label="阶段生成结果"
    >
      {thinking && (
        <ThinkingBox
          text={message.reasoning ?? ''}
          seconds={message.seconds}
          streaming={active && !message.content}
        />
      )}
      {message.content ? (
        <MarkdownMessage content={message.content} />
      ) : active ? (
        <p className="flex items-center gap-2 text-[12px] text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          正在按当前提示词生成…
        </p>
      ) : null}
      {message.error && (
        <p className="flex items-center gap-1.5 text-[11.5px] text-destructive">
          <AlertTriangle className="size-3.5" aria-hidden="true" />
          本次生成失败，可以重新运行本阶段。
        </p>
      )}
      {active && message.content && (
        <span
          className="h-4 w-[3px] animate-pulse rounded-full bg-primary"
          aria-hidden="true"
        />
      )}
      <PromptProvenance message={message} />
    </article>
  )
})

function StageSteps({
  stages,
  activeId,
  onSelect,
}: {
  stages: WorkbenchPayload['stages']
  activeId: string
  onSelect: (id: string) => void
}) {
  return (
    <div
      className="hidden items-center gap-0.5 rounded-xl border border-border/55 bg-card/50 p-1 2xl:flex"
      aria-label="阶段导航"
    >
      {stages.map((stage, index) => {
        const active = stage.id === activeId
        return (
          <button
            key={stage.id}
            type="button"
            onClick={() => onSelect(stage.id)}
            aria-current={active ? 'step' : undefined}
            title={stage.name}
            className={cn(
              'flex h-6 items-center gap-1 rounded-lg px-1.5 text-[9.5px] transition-colors',
              active
                ? 'bg-highlight text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )}
          >
            <span className="font-mono text-[9px]">
              {String(index + 1).padStart(2, '0')}
            </span>
            <span className="max-w-[58px] truncate">{stage.name}</span>
          </button>
        )
      })}
    </div>
  )
}

export function MainChat({
  payload,
  activeRun,
  messages,
  streaming,
  penMode,
  deepThink,
  notice,
  branchCount,
  panelClosed,
  composerSeed,
  teachingMode,
  onToggleTeachingMode,
  onSend,
  onStop,
  onPenModeChange,
  onDeepThinkChange,
  onLasso,
  onLassoError,
  onSelectStage,
  onOpenPrompt,
  onOpenBranches,
  onRunStage,
}: MainChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottomRef = useRef(true)
  const lastScrollTopRef = useRef(0)
  const programmaticScrollRef = useRef(false)
  const stage = payload?.stages.find((item) => item.id === payload.activeStageId)
  const chapter = payload?.chapters.find((item) => item.id === payload.activeChapterId)
  const stageIndex = payload
    ? payload.stages.findIndex((item) => item.id === payload.activeStageId)
    : -1

  const scrollToBottom = (element: HTMLDivElement) => {
    programmaticScrollRef.current = true
    element.scrollTop = element.scrollHeight
    lastScrollTopRef.current = element.scrollTop
    requestAnimationFrame(() => {
      programmaticScrollRef.current = false
    })
  }

  useIsomorphicLayoutEffect(() => {
    const element = scrollRef.current
    if (!element || !stickToBottomRef.current) return
    scrollToBottom(element)
  }, [messages])

  useIsomorphicLayoutEffect(() => {
    stickToBottomRef.current = true
    const element = scrollRef.current
    if (element) scrollToBottom(element)
  }, [activeRun?.id])

  const handleScroll = () => {
    const element = scrollRef.current
    if (!element) return
    const top = element.scrollTop
    if (programmaticScrollRef.current) {
      lastScrollTopRef.current = top
      return
    }
    const previous = lastScrollTopRef.current
    const distanceToBottom = element.scrollHeight - top - element.clientHeight
    if (top < previous - 1) {
      // 任何向上位移都立即硬锁，哪怕只离底部几像素
      stickToBottomRef.current = false
    } else if (top > previous + 1 && distanceToBottom < 50) {
      // 只有重新向下滚回底部 50px 内才恢复跟随
      stickToBottomRef.current = true
    }
    lastScrollTopRef.current = top
  }

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (event.deltaY < 0) {
      // 滚轮一有向上动作就同步锁死，抢在流式渲染之前
      stickToBottomRef.current = false
    }
  }

  const handleSend = (text: string) => {
    stickToBottomRef.current = true
    onSend(text)
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onPenModeChange(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onPenModeChange])

  const busyNotice = Boolean(notice?.startsWith('正在'))
  const errorNotice = Boolean(
    notice && (notice.includes('失败') || notice.includes('不足') || notice.includes('错误')),
  )

  return (
    <section className="relative flex h-full min-w-0 flex-col" aria-label="章节学习工作台">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/60 bg-background/55 px-6 py-3">
        <div className="min-w-0">
          <p className="truncate text-[9.5px] font-medium tracking-[0.16em] text-muted-foreground uppercase">
            {teachingMode ? '自适应特训' : (chapter?.title ?? '正在加载章节…')}
          </p>
          <div className="mt-1 flex min-w-0 items-baseline gap-2">
            <h2 className="truncate font-serif text-[19px] font-semibold tracking-tight">
              {teachingMode ? 'B 教学模式' : stage ? stage.name : '提示词工作台'}
            </h2>
            {!teachingMode && stage && (
              <span className="shrink-0 font-mono text-[9px] text-muted-foreground">
                STAGE {stageIndex + 1}/{payload?.stages.length ?? 0}
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={onToggleTeachingMode}
            aria-pressed={teachingMode}
            title={teachingMode ? '返回章节工作台' : 'B教学模式（自适应特训）'}
            className={cn(
              'inline-flex h-7 items-center gap-1 rounded-lg border px-2 text-[10.5px] transition-colors',
              teachingMode
                ? 'border-primary/35 bg-primary/10 text-primary'
                : 'border-border/60 bg-card/60 text-muted-foreground hover:border-primary/30 hover:text-primary',
            )}
          >
            <GraduationCap className="size-3" aria-hidden="true" />
            {teachingMode ? '返回章节' : 'B教学'}
          </button>
          {panelClosed && (
            <button
              type="button"
              onClick={onOpenPrompt}
              className="inline-flex h-7 items-center gap-1 rounded-lg border border-border/60 bg-card/60 px-2 text-[10.5px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
            >
              <Sparkles className="size-3" aria-hidden="true" />
              提示词
            </button>
          )}
          {panelClosed && branchCount > 0 && (
            <button
              type="button"
              onClick={onOpenBranches}
              className="inline-flex h-7 items-center gap-1 rounded-lg border border-border/60 bg-card/60 px-2 text-[10.5px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
            >
              <GitBranch className="size-3" aria-hidden="true" />
              分支 {branchCount}
            </button>
          )}
          {!teachingMode && stage && payload && (
            <StageSteps
              stages={payload.stages}
              activeId={payload.activeStageId}
              onSelect={onSelectStage}
            />
          )}
          {!teachingMode && (
            <button
              type="button"
              onClick={onRunStage}
              disabled={streaming || !stage}
              className="inline-flex h-8 items-center gap-1.5 rounded-xl bg-primary px-3 text-[11.5px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {streaming ? (
                <Loader2 className="size-3 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="size-3" aria-hidden="true" />
              )}
              {activeRun ? '重新运行' : '运行本阶段'}
            </button>
          )}
        </div>
      </div>

      <div className={cn('relative min-h-0 flex-1', !teachingMode && 'hidden')}>
        <TeachingChat />
      </div>

      <div className={cn('relative min-h-0 flex-1', teachingMode && 'hidden')}>
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          onWheel={handleWheel}
          className="paper-canvas scrollbar-thin h-full overflow-y-auto [overflow-anchor:none]"
        >
          <div className="mx-auto flex max-w-[760px] flex-col gap-7 px-6 pt-7 pb-10">
            {messages.length === 0 ? (
              <div className="relative flex flex-col items-center pt-16 text-center">
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -top-10 right-0 font-serif text-[190px] leading-none text-primary/[0.055] select-none"
                >
                  ∫
                </span>
                <p className="relative text-[9.5px] font-medium tracking-[0.2em] text-muted-foreground uppercase">
                  {chapter?.title ?? '章节学习'}
                </p>
                <h1 className="relative mt-3 max-w-[560px] font-serif text-[30px] leading-[1.25] font-semibold tracking-tight text-balance">
                  {stage ? stage.name : '正在加载提示词工作台…'}
                </h1>
                <p className="relative mt-3 max-w-[470px] text-[13px] leading-[1.85] text-muted-foreground text-pretty">
                  右侧已经把 G / S / P / D 四层提示词准备好。你可以先修改，再运行本阶段；运行后，每一段回答都会显示它实际收到的完整提示词与坐标。
                </p>
                <div className="relative mt-6 flex flex-wrap justify-center gap-2">
                  <button
                    type="button"
                    onClick={onRunStage}
                    disabled={!stage || streaming}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-primary px-3.5 text-[12px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
                  >
                    <Play className="size-3.5" aria-hidden="true" />
                    运行本阶段
                  </button>
                  <button
                    type="button"
                    onClick={onOpenPrompt}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-border/60 bg-card/60 px-3.5 text-[12px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                  >
                    <Sparkles className="size-3.5" aria-hidden="true" />
                    打开提示词编排
                  </button>
                </div>
                <div className="relative mt-9 flex items-center gap-2 text-[8.5px] tracking-[0.16em] text-muted-foreground/70 uppercase">
                  <span className="h-px w-8 bg-border" />
                  G · S · P · D 已就绪
                  <span className="h-px w-8 bg-border" />
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <MessageItem
                  key={message.id}
                  message={message}
                  isLast={index === messages.length - 1}
                  streaming={streaming}
                />
              ))
            )}
          </div>
        </div>

        <PenOverlay
          active={penMode && Boolean(activeRun)}
          busy={streaming || busyNotice}
          onCapture={onLasso}
          onError={onLassoError}
          onWheel={(deltaY) => {
            scrollRef.current?.scrollBy({ top: deltaY })
          }}
        />
      </div>

      {!teachingMode && notice && (
        <div className="mx-auto w-full max-w-[760px] px-5 pb-1">
          <div
            className={cn(
              'flex items-start gap-2 rounded-xl border px-3 py-2 text-[10.5px] leading-4',
              errorNotice
                ? 'border-destructive/25 bg-destructive/[0.05] text-destructive'
                : 'border-primary/20 bg-primary/[0.05] text-primary',
            )}
          >
            {busyNotice ? (
              <Loader2 className="mt-px size-3.5 shrink-0 animate-spin" aria-hidden="true" />
            ) : errorNotice ? (
              <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            ) : (
              <Sparkles className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            )}
            <span className="text-pretty">{notice}</span>
          </div>
        </div>
      )}

      {!teachingMode && (
        <MainComposer
          onSend={handleSend}
          onStop={onStop}
          streaming={streaming}
          penMode={penMode}
          onPenModeChange={onPenModeChange}
          deepThink={deepThink}
          onDeepThinkChange={onDeepThinkChange}
          hasRun={Boolean(activeRun)}
          penDisabled={!activeRun}
          seed={composerSeed}
        />
      )}
    </section>
  )
}
