'use client'

import { memo, useState } from 'react'
import { ArrowUp, GitBranch, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { PromptCapsule } from './prompt-capsule'
import { AnchorQuote, BranchEmpty, BranchMessageList } from './branch-content'
import type { BranchWithMessages } from '@/lib/types'

type BranchWorkbenchProps = {
  branches: BranchWithMessages[]
  activeId: string | null
  expanded: boolean
  streamingId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
  onUpdatePrompt: (id: string, prompt: string) => void
  onFollowUp: (id: string, text: string) => void
}

function BranchComposer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void
  disabled: boolean
}) {
  const [value, setValue] = useState('')

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const text = value.trim()
        if (!text || disabled) return
        onSend(text)
        setValue('')
      }}
      className="flex shrink-0 items-center gap-2 border-t border-border/60 px-4 py-3"
    >
      <label htmlFor="branch-input" className="sr-only">
        针对此分支继续追问
      </label>
      <div className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-border/60 bg-card/70 py-1.5 pr-1.5 pl-3 transition-colors focus-within:border-primary/40">
        <input
          id="branch-input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) {
              event.preventDefault()
            }
          }}
          placeholder={disabled ? '正在生成，稍后再追问……' : '针对此分支继续追问……'}
          disabled={disabled}
          className="h-7 min-w-0 flex-1 bg-transparent text-[11.5px] text-foreground outline-none placeholder:text-muted-foreground/85 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="发送分支追问"
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-35"
        >
          <ArrowUp className="size-3.5" />
        </button>
      </div>
    </form>
  )
}

function BranchWorkbenchComponent({
  branches,
  activeId,
  expanded,
  streamingId,
  onSelect,
  onCreate,
  onUpdatePrompt,
  onFollowUp,
}: BranchWorkbenchProps) {
  const active = branches.find((branch) => branch.id === activeId) ?? branches[0]
  const activeStreaming = Boolean(active && streamingId === active.id)

  if (branches.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
        <span className="grid size-12 place-items-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
          <GitBranch className="size-5" aria-hidden="true" />
        </span>
        <p className="font-serif text-[16px] font-semibold tracking-tight">还没有分支</p>
        <p className="max-w-[280px] text-[11.5px] leading-5 text-muted-foreground text-pretty">
          在主对话中开启荧光笔，拖动圈选想深挖的推导或公式，这里会自动开出独立分支。
        </p>
        <button
          type="button"
          onClick={onCreate}
          className="mt-1 inline-flex h-8 items-center gap-1.5 rounded-lg border border-border/60 px-3 text-[10.5px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          手动新建分支
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border/60 px-2">
        <div
          role="tablist"
          aria-label="分支"
          className="scrollbar-thin flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-1.5"
        >
          {branches.map((branch, index) => {
            const isActive = branch.id === active?.id
            return (
              <button
                key={branch.id}
                role="tab"
                type="button"
                aria-selected={isActive}
                onClick={() => onSelect(branch.id)}
                className={cn(
                  'flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-[10.5px] transition-colors',
                  isActive
                    ? 'bg-card text-foreground shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_6%,transparent)]'
                    : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                )}
              >
                <GitBranch
                  className={cn('size-3', isActive && 'text-primary')}
                  aria-hidden="true"
                />
                <span className="max-w-[108px] truncate">
                  {`分支 ${index + 1} · ${branch.title}`}
                </span>
                {streamingId === branch.id && (
                  <span
                    className="size-1.5 animate-pulse rounded-full bg-primary"
                    aria-hidden="true"
                  />
                )}
              </button>
            )
          })}
          <button
            type="button"
            onClick={onCreate}
            disabled={Boolean(streamingId)}
            className="flex h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40"
          >
            <Plus className="size-3.5" aria-hidden="true" />
            新建
          </button>
        </div>
      </div>

      {active && (
        <>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
            <div className={cn('mx-auto flex flex-col gap-5 px-5 py-5', expanded && 'max-w-3xl')}>
              <PromptCapsule
                key={active.id}
                prompt={active.prompt}
                busy={activeStreaming}
                onSave={(prompt) => onUpdatePrompt(active.id, prompt)}
              />
              {active.anchorText ? (
                <AnchorQuote text={active.anchorText} label={active.anchorLabel} />
              ) : null}
              {active.messages.length === 0 && !activeStreaming ? (
                <BranchEmpty />
              ) : (
                <BranchMessageList messages={active.messages} streaming={activeStreaming} />
              )}
            </div>
          </div>

          <BranchComposer
            onSend={(text) => onFollowUp(active.id, text)}
            disabled={Boolean(streamingId)}
          />
        </>
      )}
    </div>
  )
}

export const BranchWorkbench = memo(BranchWorkbenchComponent)
