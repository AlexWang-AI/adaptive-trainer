'use client'

import { Loader2, Sparkles } from 'lucide-react'
import { MarkdownMessage } from '@/components/math/markdown'
import { ThinkingBox } from '@/components/chat/thinking-box'
import { cn } from '@/lib/utils'
import type { BranchMessage } from '@/lib/types'

export function AnchorQuote({ text, label }: { text: string; label?: string }) {
  return (
    <blockquote className="rounded-r-xl border-l-2 border-primary/45 bg-muted/30 px-4 py-3">
      <p className="mb-1 text-[9px] font-medium tracking-[0.12em] text-muted-foreground uppercase">
        {label || '原文圈选'}
      </p>
      <div className="scrollbar-thin max-h-44 overflow-y-auto">
        <MarkdownMessage content={text} className="text-[11.5px] leading-[1.8]" />
      </div>
    </blockquote>
  )
}

export function BranchMessageList({
  messages,
  streaming,
}: {
  messages: BranchMessage[]
  streaming: boolean
}) {
  if (messages.length === 0 && !streaming) return null

  return (
    <div className="flex flex-col gap-4">
      {messages.map((message, index) => {
        const isLast = index === messages.length - 1
        const active = streaming && isLast

        if (message.role === 'user') {
          return (
            <div key={message.id} className="flex justify-end">
              <div className="max-w-[92%] rounded-2xl rounded-tr-md border border-border/45 bg-muted/60 px-3 py-2">
                <MarkdownMessage content={message.content} className="text-[11.5px]" />
              </div>
            </div>
          )
        }

        return (
          <article
            key={message.id}
            className={cn(
              'flex flex-col gap-2.5',
              message.error && 'rounded-xl border border-destructive/35 p-2.5',
            )}
          >
            {(message.reasoning || active) && (
              <ThinkingBox
                text={message.reasoning ?? ''}
                seconds={message.seconds}
                streaming={active && !message.content}
              />
            )}
            {message.content ? (
              <MarkdownMessage
                content={message.content}
                className="text-[12.5px] leading-[1.85]"
              />
            ) : active ? (
              <p className="flex items-center gap-2 text-[10.5px] text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                正在拆解这一段…
              </p>
            ) : null}
            {active && message.content && (
              <span
                className="h-3.5 w-[3px] animate-pulse rounded-full bg-primary"
                aria-hidden="true"
              />
            )}
          </article>
        )
      })}
      {streaming && messages.length === 0 && (
        <div className="flex flex-col gap-2" aria-live="polite">
          <p className="text-[10.5px] text-muted-foreground">正在按指令生成分支拆解…</p>
          {[100, 92, 96, 70].map((width, index) => (
            <div
              key={index}
              className="h-3 animate-pulse rounded bg-muted/60"
              style={{ width: `${width}%` }}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function BranchEmpty() {
  return (
    <div className="flex flex-col items-center gap-2 py-14 text-center">
      <span className="grid size-10 place-items-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
        <Sparkles className="size-4" aria-hidden="true" />
      </span>
      <p className="font-serif text-[14px] font-semibold">分支已就绪</p>
      <p className="max-w-[260px] text-[11px] leading-5 text-muted-foreground text-pretty">
        在下方输入你想深挖的问题，或在主对话中重新圈选一段内容。
      </p>
    </div>
  )
}
