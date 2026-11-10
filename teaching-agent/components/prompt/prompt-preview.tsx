'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PromptPreview as PromptPreviewType, PromptSegment } from '@/lib/prompt-types'

const segmentStyles: Record<PromptSegment['key'], string> = {
  G: 'border-layer-g/20 bg-layer-g/[0.035]',
  S: 'border-layer-s/20 bg-layer-s/[0.035]',
  P: 'border-layer-p/20 bg-layer-p/[0.035]',
  D: 'border-layer-d/20 bg-layer-d/[0.035]',
  U: 'border-primary/20 bg-primary/[0.035]',
}

const keyStyles: Record<PromptSegment['key'], string> = {
  G: 'bg-layer-g/12 text-layer-g',
  S: 'bg-layer-s/12 text-layer-s',
  P: 'bg-layer-p/12 text-layer-p',
  D: 'bg-layer-d/12 text-layer-d',
  U: 'bg-primary/12 text-primary',
}

function SegmentCard({
  segment,
  compact,
}: {
  segment: PromptSegment
  compact?: boolean
}) {
  return (
    <div className={cn('rounded-xl border px-3 py-2.5', segmentStyles[segment.key])}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5">
          <span
            className={cn(
              'grid size-5 shrink-0 place-items-center rounded-md font-mono text-[9.5px]',
              keyStyles[segment.key],
            )}
          >
            {segment.key}
          </span>
          <span className="truncate text-[10.5px] font-medium text-foreground/80">
            {segment.label}
          </span>
        </span>
        <span className="shrink-0 font-mono text-[8.5px] text-muted-foreground/85">
          [{segment.start}, {segment.end}) · {segment.end - segment.start} 字
        </span>
      </div>
      <div
        className={cn(
          'scrollbar-thin mt-1.5 overflow-y-auto whitespace-pre-wrap text-[11.5px] leading-[1.8] text-foreground/70',
          compact ? 'max-h-28' : 'max-h-40',
        )}
      >
        {segment.text}
      </div>
    </div>
  )
}

export function PromptPreview({
  preview,
  compact,
}: {
  preview: PromptPreviewType
  compact?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const systemSegments = preview.systemSegments
  const userSegments = preview.userSegments

  const copy = async () => {
    const text = `[SYSTEM]\n${preview.systemText}\n\n[USER]\n${preview.userText}`
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be unavailable in embedded browsers.
    }
  }

  if (systemSegments.length === 0 && userSegments.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 font-mono text-[9px] text-muted-foreground">
          <span className="rounded-md bg-muted px-1.5 py-0.5 text-foreground/80">SYSTEM</span>
          <span>{preview.systemText.length} 字</span>
          <span className="text-border">/</span>
          <span className="rounded-md bg-muted px-1.5 py-0.5 text-foreground/80">USER</span>
          <span>{preview.userText.length} 字</span>
          {preview.versionLabel && (
            <span className="truncate rounded-full border border-border/60 px-1.5 py-0.5 text-[8px]">
              {preview.versionLabel}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={copy}
          className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border/60 px-2 py-1 text-[10px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
        >
          {copied ? <Check className="size-3 text-sage" /> : <Copy className="size-3" />}
          {copied ? '已复制' : '复制'}
        </button>
      </div>

      {systemSegments.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-2 text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
            <span className="font-mono">System</span>
            <span className="h-px flex-1 bg-border/60" />
            <span className="font-mono">{systemSegments.length} 段</span>
          </div>
          <div className="space-y-1.5">
            {systemSegments.map((segment) => (
              <SegmentCard
                key={`${segment.key}-${segment.start}`}
                segment={segment}
                compact={compact}
              />
            ))}
          </div>
        </div>
      )}

      {userSegments.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-2 text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
            <span className="font-mono">User</span>
            <span className="h-px flex-1 bg-border/60" />
            <span className="font-mono">{userSegments.length} 段</span>
          </div>
          <div className="space-y-1.5">
            {userSegments.map((segment) => (
              <SegmentCard
                key={`${segment.key}-${segment.start}`}
                segment={segment}
                compact={compact}
              />
            ))}
          </div>
        </div>
      )}

      <details className="group rounded-xl border border-border/60 bg-muted/20">
        <summary className="cursor-pointer px-3 py-2 text-[10px] text-muted-foreground transition-colors hover:text-foreground">
          查看完整发送原文
        </summary>
        <div className="space-y-2 border-t border-border/55 p-3">
          <pre className="scrollbar-thin max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-background/60 p-2.5 text-[10.5px] leading-[1.8] text-foreground/70">
            {preview.systemText}
          </pre>
          <pre className="scrollbar-thin max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-background/60 p-2.5 text-[10.5px] leading-[1.8] text-foreground/70">
            {preview.userText}
          </pre>
        </div>
      </details>
    </div>
  )
}
