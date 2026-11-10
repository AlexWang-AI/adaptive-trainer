'use client'

import { GitBranch, Maximize2, Minimize2, Sparkles, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type SidePanelProps = {
  tab: 'prompt' | 'branches'
  onTabChange: (tab: 'prompt' | 'branches') => void
  expanded: boolean
  onClose: () => void
  onToggleExpand: () => void
  prompt: React.ReactNode
  branches: React.ReactNode
}

export function SidePanel({
  tab,
  onTabChange,
  expanded,
  onClose,
  onToggleExpand,
  prompt,
  branches,
}: SidePanelProps) {
  return (
    <aside
      className="paper-panel flex h-full flex-col border-l border-border/70"
      aria-label="调试面板"
    >
      <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border/60 px-3">
        <div
          role="tablist"
          aria-label="面板模式"
          className="flex items-center rounded-xl bg-muted/50 p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'prompt'}
            onClick={() => onTabChange('prompt')}
            className={cn(
              'flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[11.5px] font-medium transition-all duration-200',
              tab === 'prompt'
                ? 'bg-card text-foreground shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_7%,transparent)]'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Sparkles
              className={cn('size-3.5', tab === 'prompt' ? 'text-primary' : 'text-muted-foreground/80')}
              aria-hidden="true"
            />
            提示词编排
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'branches'}
            onClick={() => onTabChange('branches')}
            className={cn(
              'flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[11.5px] font-medium transition-all duration-200',
              tab === 'branches'
                ? 'bg-card text-foreground shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_7%,transparent)]'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <GitBranch
              className={cn(
                'size-3.5',
                tab === 'branches' ? 'text-primary' : 'text-muted-foreground/80',
              )}
              aria-hidden="true"
            />
            分支拆解
          </button>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <button
            type="button"
            onClick={onToggleExpand}
            aria-label={expanded ? '退出全屏' : '全屏展开'}
            title={expanded ? '退出全屏' : '全屏展开'}
            className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            {expanded ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭调试面板"
            title="关闭调试面板"
            className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <div className={cn('h-full', tab !== 'prompt' && 'hidden')}>{prompt}</div>
        <div className={cn('h-full', tab !== 'branches' && 'hidden')}>{branches}</div>
      </div>
    </aside>
  )
}
