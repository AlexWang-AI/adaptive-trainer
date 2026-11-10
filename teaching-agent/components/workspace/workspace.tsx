'use client'

import { useEffect, useState } from 'react'
import { Activity, BarChart3, Moon, Sigma, Sun } from 'lucide-react'
import { TeachingChat } from '@/components/teaching/teaching-chat'
import { AgentStatusPanel } from './agent-status-panel'
import { KnowledgeProvider, useKnowledge } from './knowledge-provider'
import { KnowledgeTreeSidebar } from './knowledge-tree-sidebar'
import { StudyReport } from './study-report'

function WorkspaceShell() {
  const [theme, setTheme] = useState<'dark' | 'light'>('light')
  const [reportOpen, setReportOpen] = useState(false)
  const { tree } = useKnowledge()

  useEffect(() => {
    setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light')
  }, [])

  const toggleTheme = () => {
    const root = document.documentElement
    const next = root.classList.contains('dark') ? 'light' : 'dark'
    root.classList.toggle('dark', next === 'dark')
    setTheme(next)
  }

  const progressed = tree ? `${tree.progress.mastered}/${tree.progress.total}` : '—'

  return (
    <div className="flex h-dvh min-h-0 flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/70 bg-background/85 px-4 backdrop-blur-xl">
        <span className="relative grid size-8 shrink-0 place-items-center rounded-[10px] border border-primary/25 bg-primary/10 text-primary">
          <Sigma className="size-4" strokeWidth={1.9} />
          <span className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-primary ring-2 ring-background" />
        </span>
        <div className="min-w-0 leading-none">
          <div className="truncate font-serif text-[15px] font-semibold tracking-tight">MathNeuron</div>
          <div className="mt-1 hidden text-[8.5px] tracking-[0.18em] text-muted-foreground uppercase sm:block">
            Adaptive Teaching Shell
          </div>
        </div>

        <div className="mx-3 hidden h-5 w-px bg-border/60 sm:block" />
        <div className="hidden min-w-0 items-center gap-2 sm:flex">
          <span className="rounded-full border border-primary/25 bg-primary/8 px-2.5 py-1 text-[10px] font-medium text-primary">
            讲练合一 · 三阶梯题卡
          </span>
          <span className="text-[10px] text-muted-foreground">讲课 → 3 题闯关 → 知识点通关 → 下一站</span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] text-emerald-700 md:inline-flex">
            <Activity className="size-3" />
            知识树 {progressed}
          </span>
          <button
            type="button"
            data-open-report="1"
            onClick={() => setReportOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-2.5 py-1.5 text-[11px] text-foreground/75 transition-colors hover:bg-accent"
          >
            <BarChart3 className="size-3.5" />
            学习报告
          </button>
          <button
            type="button"
            onClick={toggleTheme}
            className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label={theme === 'dark' ? '切换到明亮模式' : '切换到暗黑模式'}
            title={theme === 'dark' ? '切换到明亮模式' : '切换到暗黑模式'}
          >
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="hidden w-[268px] shrink-0 lg:block">
          <KnowledgeTreeSidebar />
        </div>

        <main className="min-w-0 flex-1 overflow-hidden">
          <TeachingChat />
        </main>

        <div className="hidden w-[360px] shrink-0 border-l border-border/70 xl:block">
          <AgentStatusPanel />
        </div>
      </div>

      <StudyReport open={reportOpen} onClose={() => setReportOpen(false)} />
    </div>
  )
}

export function Workspace() {
  return (
    <KnowledgeProvider>
      <WorkspaceShell />
    </KnowledgeProvider>
  )
}
