'use client'

import { useState } from 'react'
import { ChevronDown, Lightbulb } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ThinkingBox({
  text,
  seconds,
  streaming,
}: {
  text: string
  seconds?: number
  streaming?: boolean
}) {
  const [open, setOpen] = useState(true)

  return (
    <div className="overflow-hidden rounded-xl border border-border/50 bg-muted/25">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-[10.5px] text-muted-foreground transition-colors hover:text-foreground"
      >
        <Lightbulb
          className={cn('size-3.5', streaming && 'animate-pulse text-primary')}
          aria-hidden="true"
        />
        <span>{streaming ? '正在深度思考…' : `已深度思考 ${seconds ?? 0} 秒`}</span>
        <ChevronDown
          className={cn(
            'ml-auto size-3.5 transition-transform duration-200',
            open && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>
      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-300 ease-out',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden">
          <div className="scrollbar-thin mx-3.5 mb-3 max-h-80 space-y-2 overflow-y-auto border-l-2 border-primary/20 pl-3 text-[11px] leading-[1.8] whitespace-pre-wrap text-muted-foreground">
            {text || '正在分析题目结构…'}
          </div>
        </div>
      </div>
    </div>
  )
}
