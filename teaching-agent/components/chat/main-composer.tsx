'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Atom, Highlighter, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

type MainComposerProps = {
  onSend: (text: string) => void
  onStop: () => void
  streaming: boolean
  penMode: boolean
  onPenModeChange: (value: boolean) => void
  deepThink: boolean
  onDeepThinkChange: (value: boolean) => void
  hasRun: boolean
  penDisabled?: boolean
  seed?: { text: string; nonce: number } | null
  showDeepThink?: boolean
}

export function MainComposer({
  onSend,
  onStop,
  streaming,
  penMode,
  onPenModeChange,
  deepThink,
  onDeepThinkChange,
  hasRun,
  penDisabled,
  seed,
  showDeepThink = true,
}: MainComposerProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resize = () => {
    const element = textareaRef.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`
  }

  useEffect(() => {
    resize()
  }, [value])

  useEffect(() => {
    if (!seed) return
    setValue((current) => {
      const base = current.trim()
      return base ? `${base}\n\n${seed.text}` : seed.text
    })
    requestAnimationFrame(() => {
      const element = textareaRef.current
      if (!element) return
      element.focus()
      element.setSelectionRange(element.value.length, element.value.length)
    })
  }, [seed])

  const submit = () => {
    if (streaming) return
    const text = value.trim()
    if (!text) return
    onSend(text)
    setValue('')
  }

  return (
    <div className="shrink-0 px-5 pb-5 pt-2">
      <div className="mx-auto w-full max-w-[760px]">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
          className="warm-shadow-sm rounded-[20px] border border-border/70 bg-card/90 p-2 transition-colors focus-within:border-primary/40"
        >
          <label htmlFor="main-input" className="sr-only">
            继续追问
          </label>
          <textarea
            id="main-input"
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || event.shiftKey) return
              if (event.nativeEvent.isComposing || event.keyCode === 229) return
              event.preventDefault()
              submit()
            }}
            placeholder={
              penMode
                ? '在解答上拖动圈选不懂的内容……'
                : hasRun
                  ? '在本阶段内继续追问或补充反馈……'
                  : '输入补充要求，或点击运行本阶段……'
            }
            className="scrollbar-thin max-h-40 min-h-[26px] w-full resize-none bg-transparent px-2.5 pt-1.5 pb-1 text-[14.5px] leading-6 text-foreground outline-none placeholder:text-muted-foreground/85"
          />

          <div className="mt-1 flex items-center gap-1 px-0.5">
            <button
              type="button"
              onClick={() => onPenModeChange(!penMode)}
              disabled={penDisabled}
              aria-pressed={penMode}
              aria-label="荧光画笔模式"
              title={penDisabled ? '运行本阶段后才能圈选' : '荧光画笔模式：拖动圈选不懂的内容'}
              className={cn(
                'inline-flex h-7 shrink-0 items-center gap-1.5 rounded-lg px-2 text-[11px] font-medium transition-colors disabled:opacity-30',
                penMode
                  ? 'bg-highlight-strong text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              <Highlighter className="size-3.5" />
              圈选
            </button>
            {showDeepThink && (
              <button
                type="button"
                onClick={() => onDeepThinkChange(!deepThink)}
                aria-pressed={deepThink}
                className={cn(
                  'inline-flex h-7 shrink-0 items-center gap-1.5 rounded-lg px-2 text-[11px] font-medium transition-colors',
                  deepThink
                    ? 'bg-highlight text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )}
              >
                <Atom className="size-3.5" aria-hidden="true" />
                深度思考
              </button>
            )}
            <span className="ml-auto hidden text-[9.5px] text-muted-foreground/75 sm:inline">
              Enter 发送 · Shift+Enter 换行
            </span>
            {streaming ? (
              <button
                type="button"
                onClick={onStop}
                aria-label="停止生成"
                className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl border border-border/70 bg-muted/70 text-foreground transition-colors hover:bg-accent"
              >
                <Square className="size-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!value.trim()}
                aria-label="发送"
                className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-35"
              >
                <ArrowUp className="size-4" />
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
