'use client'

import { useEffect, useState } from 'react'
import { Activity, Check, Code2, Copy, FolderCode, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type AgentSource = { label: string; path: string; code?: string }
type AgentSpec = {
  id: string
  name: string
  role: string
  folder: string
  structure: { key: string; value: string }[]
  sources: AgentSource[]
}
type RuntimeSpec = { name: string; kind: string; folder: string }

const FALLBACK_AGENTS: AgentSpec[] = [
  {
    id: 'teaching',
    name: 'Teaching Agent',
    role: '问答 / 教学',
    folder: 'backend/prompts.py',
    structure: [
      { key: '输入', value: '主题 + 学段 + 已有基础 + 教学历史 + 学生这一轮的话' },
      { key: '输出', value: 'teaching_content（300–600 字）+ thinking（reasoning 流）' },
      { key: '模型', value: 'DeepSeek V4 Flash，streaming + thinking' },
      { key: '约束', value: '单微考点 / 300–600 字 / 无目录 / 结尾具体邀请' },
      { key: '上下文', value: '只读 teaching_history；不读题目和判题结果' },
    ],
    sources: [{ label: 'prompts.py', path: 'backend/prompts.py' }],
  },
  {
    id: 'quiz',
    name: 'Quiz Agent',
    role: '动态出题',
    folder: 'backend/quiz_node.py',
    structure: [
      { key: '输入', value: '当前教学正文 + 学生这一轮的话 + 学段/基础' },
      { key: '输出', value: 'QuizQuestion：题干 / 4 选项 / 答案 / 解析 / 考点' },
      { key: '模型', value: 'DeepSeek V4 Flash，JSON mode，thinking disabled' },
      { key: '约束', value: '只出一道；只测刚讲的一层；source_quote 必须来自教学正文' },
      { key: '上下文', value: 'history=[]，只读自己的题卡上下文' },
    ],
    sources: [{ label: 'quiz_node.py', path: 'backend/quiz_node.py' }],
  },
]

const FALLBACK_RUNTIME: RuntimeSpec[] = [
  { name: 'Judge Node', kind: 'deterministic', folder: 'backend/api.py' },
  { name: 'LangGraph Orchestrator', kind: 'runtime', folder: 'backend/api.py' },
]

function AgentModal({
  agent,
  runtime,
  onClose,
}: {
  agent: AgentSpec
  runtime: RuntimeSpec[]
  onClose: () => void
}) {
  const [tab, setTab] = useState<'structure' | 'source'>('structure')
  const [sourceIndex, setSourceIndex] = useState(0)
  const [copied, setCopied] = useState(false)
  const source = agent.sources[sourceIndex] ?? agent.sources[0]
  const code = source?.code ?? '（先启动 backend 8008，刷新右侧 Agent 面板后即可查看源码。）'

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch {
      // clipboard can be unavailable in embedded contexts
    }
  }

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/35 p-4 backdrop-blur-[5px] dark:bg-black/55"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${agent.name} 结构与源码`}
        className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border/70 bg-card shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[9px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
              Agent Detail
            </p>
            <h2 className="mt-0.5 font-serif text-[20px] font-semibold tracking-tight">{agent.name}</h2>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {agent.role} · <span className="font-mono">{agent.folder}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="关闭"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="flex items-center gap-1 border-b border-border/55 px-4 pt-2">
          {[
            { id: 'structure' as const, label: '结构' },
            { id: 'source' as const, label: '源码' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={cn(
                'rounded-t-lg px-3 py-2 text-[11.5px] font-medium transition-colors',
                tab === item.id
                  ? 'bg-muted/55 text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {item.label}
            </button>
          ))}
          <span className="ml-auto pb-2 font-mono text-[9px] text-muted-foreground">
            {agent.sources.length} file{agent.sources.length > 1 ? 's' : ''}
          </span>
        </div>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">
          {tab === 'structure' ? (
            <div className="space-y-3">
              <div className="overflow-hidden rounded-xl border border-border/60">
                {agent.structure.map((row, index) => (
                  <div
                    key={row.key}
                    className={cn(
                      'grid grid-cols-[92px_minmax(0,1fr)] gap-3 px-3.5 py-2.5 text-[12px]',
                      index > 0 && 'border-t border-border/45',
                    )}
                  >
                    <span className="font-medium text-muted-foreground">{row.key}</span>
                    <span className="leading-6 text-foreground/85">{row.value}</span>
                  </div>
                ))}
              </div>
              <div className="rounded-xl border border-dashed border-border/60 bg-muted/20 px-3.5 py-3">
                <div className="text-[9px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
                  Runtime neighbors
                </div>
                <div className="mt-2 space-y-1.5">
                  {runtime.map((item) => (
                    <div key={item.name} className="flex items-center gap-2 text-[10.5px] text-muted-foreground">
                      <span className="size-1.5 rounded-full bg-sage/80" />
                      <span className="text-foreground/75">{item.name}</span>
                      <span className="rounded border border-border/55 px-1.5 py-0.5 font-mono text-[8.5px]">
                        {item.kind}
                      </span>
                      <span className="font-mono text-[9px]">{item.folder}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[9.5px] leading-5 text-muted-foreground/80">
                  Judge 是确定性判题函数，LangGraph 是状态机运行时；它们不是 LLM Agent。
                </p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {agent.sources.map((item, index) => (
                  <button
                    key={item.path}
                    type="button"
                    onClick={() => setSourceIndex(index)}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 font-mono text-[9.5px] transition-colors',
                      index === sourceIndex
                        ? 'border-primary/35 bg-primary/8 text-primary'
                        : 'border-border/60 bg-card/50 text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <Code2 className="size-3" />
                    {item.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => void copy()}
                  className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-2.5 py-1.5 text-[9.5px] text-muted-foreground hover:text-foreground"
                >
                  {copied ? <Check className="size-3 text-sage" /> : <Copy className="size-3" />}
                  {copied ? '已复制' : '复制源码'}
                </button>
              </div>
              <pre className="scrollbar-thin max-h-[52vh] overflow-auto rounded-xl border border-border/60 bg-[#171512] p-4 font-mono text-[10.5px] leading-[1.7] text-[#e8e1d5]">
                <code>{code}</code>
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function AgentStatusPanel() {
  const [agents, setAgents] = useState<AgentSpec[]>(FALLBACK_AGENTS)
  const [runtime, setRuntime] = useState<RuntimeSpec[]>(FALLBACK_RUNTIME)
  const [selected, setSelected] = useState<AgentSpec | null>(null)
  const [live, setLive] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/api/agents', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(String(response.status))
        return response.json() as Promise<{ agents?: AgentSpec[]; runtime?: RuntimeSpec[] }>
      })
      .then((data) => {
        if (cancelled) return
        if (Array.isArray(data.agents) && data.agents.length) setAgents(data.agents)
        if (Array.isArray(data.runtime)) setRuntime(data.runtime)
        setLive(true)
      })
      .catch(() => {
        if (!cancelled) setLive(false)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <aside className="flex h-full min-h-0 flex-col bg-card/35">
      <header className="shrink-0 border-b border-border/60 px-4 py-4">
        <div className="flex items-center gap-2 text-[9.5px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
          <Activity className={cn('size-3.5', live ? 'text-sage' : 'text-muted-foreground')} />
          Agent Monitor
        </div>
        <div className="mt-1.5 flex items-baseline gap-2">
          <h2 className="font-serif text-[19px] font-semibold tracking-tight">Agent 状态</h2>
          <span className="rounded-full border border-sage/30 bg-sage/10 px-2 py-0.5 font-mono text-[9px] text-sage">
            {agents.length} AGENTS
          </span>
        </div>
        <p className="mt-1 text-[10.5px] leading-5 text-muted-foreground">
          {loading ? '正在读取 Agent 清单…' : live ? '正在工作 · 点任意 Agent 看结构与源码' : 'backend 未连接 · 当前为兜底清单'}
        </p>
      </header>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <div className="space-y-2">
          {agents.map((agent, index) => (
            <button
              key={agent.id}
              type="button"
              onClick={() => setSelected(agent)}
              className="w-full rounded-xl border border-border/55 bg-card/60 px-3 py-2.5 text-left transition-colors hover:border-primary/30 hover:bg-card/80"
            >
              <div className="flex items-center gap-2">
                <span className="relative flex size-2">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-sage/45" />
                  <span className="relative inline-flex size-2 rounded-full bg-sage" />
                </span>
                <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-foreground">
                  {agent.name}
                </span>
                <span className="font-mono text-[8.5px] text-muted-foreground/70">
                  0{index + 1}
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-1.5 pl-4 font-mono text-[9px] text-muted-foreground">
                <FolderCode className="size-3 shrink-0" />
                <span className="truncate">{agent.folder}</span>
              </div>
              <div className="mt-1 pl-4 text-[9.5px] text-muted-foreground/75">{agent.role}</div>
            </button>
          ))}
        </div>

        <div className="mt-4 rounded-xl border border-dashed border-border/55 bg-muted/15 px-3 py-2.5">
          <div className="text-[9px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
            Runtime
          </div>
          <div className="mt-1.5 space-y-1">
            {runtime.map((item) => (
              <div key={item.name} className="flex items-center gap-2 text-[9.5px] text-muted-foreground">
                <span className="size-1 rounded-full bg-muted-foreground/45" />
                <span className="truncate text-foreground/70">{item.name}</span>
                <span className="ml-auto font-mono text-[8px]">{item.kind}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[9px] leading-4 text-muted-foreground/75">
            判题是函数，LangGraph 是运行时，不计入 Agent 数。
          </p>
        </div>
      </div>

      <footer className="shrink-0 border-t border-border/55 px-4 py-3 text-[9.5px] leading-5 text-muted-foreground/80">
        backend / v2 · Prompt 与旧知识树已解耦
      </footer>

      {selected && (
        <AgentModal agent={selected} runtime={runtime} onClose={() => setSelected(null)} />
      )}
    </aside>
  )
}
