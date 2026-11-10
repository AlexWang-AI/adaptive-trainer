'use client'

import {
  BrainCircuit,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Sigma,
  Sun,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type AppView = 'workspace' | 'network'

type TopNavProps = {
  theme: 'dark' | 'light'
  view: AppView
  pendingCount: number
  sidebarOpen: boolean
  onViewChange: (view: AppView) => void
  onToggleSidebar: () => void
  onToggleTheme: () => void
}

function Logo() {
  return (
    <span
      className="relative grid size-8 shrink-0 place-items-center rounded-[10px] border border-primary/25 bg-primary/10 text-primary"
      aria-hidden="true"
    >
      <Sigma className="size-4" strokeWidth={1.9} />
      <span className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-primary ring-2 ring-background" />
    </span>
  )
}

function ViewSwitch({
  view,
  pendingCount,
  onViewChange,
}: Pick<TopNavProps, 'view' | 'pendingCount' | 'onViewChange'>) {
  const options = [
    { id: 'workspace' as const, label: '章节工作台', icon: MessageSquare },
    { id: 'network' as const, label: '认知网络', icon: BrainCircuit },
  ]
  return (
    <div
      role="tablist"
      aria-label="视图切换"
      className="flex items-center rounded-xl border border-border/60 bg-muted/45 p-1"
    >
      {options.map(({ id, label, icon: Icon }) => {
        const active = view === id
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onViewChange(id)}
            className={cn(
              'relative flex h-8 items-center justify-center gap-1.5 rounded-lg px-3 text-[11.5px] font-medium transition-all duration-300',
              active
                ? 'bg-card text-foreground shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_7%,transparent)]'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon
              className={cn('size-3.5', active ? 'text-primary' : 'text-muted-foreground/80')}
              aria-hidden="true"
            />
            <span className="hidden sm:inline">{label}</span>
            {id === 'network' && (
              <span
                key={pendingCount}
                aria-label={`待复盘 ${pendingCount} 个`}
                className={cn(
                  'animate-in zoom-in-50 rounded-full px-1.5 py-px font-mono text-[9px] leading-4 tabular-nums duration-300',
                  active
                    ? 'bg-primary/12 text-primary'
                    : 'bg-muted-foreground/12 text-muted-foreground',
                )}
              >
                {pendingCount}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function TopNav({
  theme,
  view,
  pendingCount,
  sidebarOpen,
  onViewChange,
  onToggleSidebar,
  onToggleTheme,
}: TopNavProps) {
  return (
    <header
      className={cn(
        'relative z-20 grid h-14 shrink-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 border-b border-border/70 bg-background/85 px-4 backdrop-blur-xl transition-colors',
        view === 'network' && 'dark bg-background/92',
      )}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        {view === 'workspace' && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label={sidebarOpen ? '收起课程目录' : '展开课程目录'}
            aria-pressed={sidebarOpen}
            title={sidebarOpen ? '收起课程目录' : '展开课程目录'}
          >
            {sidebarOpen ? (
              <PanelLeftClose className="size-4" />
            ) : (
              <PanelLeftOpen className="size-4" />
            )}
          </button>
        )}
        <div className="flex min-w-0 items-center gap-2.5">
          <Logo />
          <div className="min-w-0 leading-none">
            <div className="truncate font-serif text-[15px] font-semibold tracking-tight">
              MathNeuron
            </div>
            <div className="mt-1 hidden text-[8.5px] tracking-[0.18em] text-muted-foreground uppercase lg:block">
              Mathematics Workbench
            </div>
          </div>
        </div>
        <span className="hidden items-center gap-1.5 rounded-full border border-border/60 bg-card/55 px-2.5 py-1 text-[10px] text-muted-foreground xl:inline-flex">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-sage/60" />
            <span className="relative inline-flex size-1.5 rounded-full bg-sage" />
          </span>
          DeepSeek V4.1 Flash
        </span>
      </div>

      <ViewSwitch view={view} pendingCount={pendingCount} onViewChange={onViewChange} />

      <div className="flex items-center justify-end gap-1">
        <button
          type="button"
          onClick={onToggleTheme}
          className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          aria-label={theme === 'dark' ? '切换到明亮模式' : '切换到暗黑模式'}
          title={theme === 'dark' ? '切换到明亮模式' : '切换到暗黑模式'}
        >
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </div>
    </header>
  )
}
