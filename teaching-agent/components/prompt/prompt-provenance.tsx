'use client'

import { useState } from 'react'
import { ChevronDown, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Message } from '@/lib/types'
import { PromptPreview } from './prompt-preview'

export function PromptProvenance({ message }: { message: Message }) {
  const [open, setOpen] = useState(false)
  const preview = message.promptPreview
  if (!preview) return null
  const segments = [...preview.systemSegments, ...preview.userSegments]

  return (
    <details
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
      className="group overflow-hidden rounded-xl border border-border/50 bg-card/35"
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-1.5 px-3 py-2 text-[9.5px] text-muted-foreground">
        <Sparkles className="size-3 text-primary" aria-hidden="true" />
        <span className="font-medium text-foreground/75">
          本次提示词 · {message.promptVersionLabel || '草稿快照'}
        </span>
        {segments.map((segment) => (
          <span
            key={`${segment.key}-${segment.start}`}
            className="rounded border border-border/50 bg-background/55 px-1 py-px font-mono text-[8px]"
          >
            {segment.key}[{segment.start},{segment.end})
          </span>
        ))}
        <ChevronDown
          className={cn(
            'ml-auto size-3.5 transition-transform duration-200 group-open:rotate-180',
          )}
          aria-hidden="true"
        />
      </summary>
      {open && (
        <div className="border-t border-border/50 p-3">
          <PromptPreview preview={preview} compact />
        </div>
      )}
    </details>
  )
}
