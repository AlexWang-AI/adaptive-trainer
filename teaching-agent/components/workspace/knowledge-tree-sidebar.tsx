'use client'

import { useCallback, useMemo, useState } from 'react'
import { BookOpen, Check, ChevronDown, ChevronRight, Circle, Loader2, RefreshCw, Target } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getJSON } from '@/lib/client-api'
import type { KpNode } from '@/lib/quiz-types'
import { useKnowledge } from './knowledge-provider'

/** 单个知识点的教材细节（按需加载，不进 /api/curriculum 的初始负载） */
type KpDetail = {
  id: string
  name: string
  textbook_ref?: string
  evidence?: string
  points: string[]
  conclusions: string[]
  examples: string[]
  types: { name: string; feature?: string; steps?: string[] }[]
  extras: { name: string; how?: string }[]
}

/**
 * 左侧知识树：讲 → 分支 → 知识点 → 教材要点（要点可单独开讲）。
 *
 * 数据来自后端 /api/curriculum（编译自 textbook/tree 的知识树），
 * 知识点展开时再拉 /api/kp_detail 取「要点 / 题型 / 例题」——**树有几层就显示几层**，
 * 不为了界面好看去合并节点（例如「七种未定式的计算」下面那 7 种未定式必须能点到）。
 */
export function KnowledgeTreeSidebar() {
  const { tree, loading, error, refresh, requestStart, activeKpId } = useKnowledge()
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const [detailOpen, setDetailOpen] = useState<Record<string, boolean>>({})
  const [details, setDetails] = useState<Record<string, KpDetail | null>>({})

  const toggleDetail = useCallback(
    async (kp: KpNode) => {
      const next = !detailOpen[kp.id]
      setDetailOpen((prev) => ({ ...prev, [kp.id]: next }))
      if (!next || details[kp.id]) return
      try {
        const data = await getJSON<KpDetail>(`/api/kp_detail?kp_id=${encodeURIComponent(kp.id)}`)
        setDetails((prev) => ({ ...prev, [kp.id]: data }))
      } catch {
        setDetails((prev) => ({ ...prev, [kp.id]: null }))
      }
    },
    [detailOpen, details],
  )

  const firstOpenChapter = useMemo(() => {
    const next = tree?.next_kp
    if (!next) return tree?.chapters[0]?.id ?? ''
    return next.chapter
  }, [tree])

  // 分支默认只展开「下一站」所在的那一支：232 个知识点全摊开会淹没视线
  const firstOpenBlock = useMemo(() => {
    const next = tree?.next_kp
    if (next?.block) return next.block
    return tree?.chapters[0]?.blocks?.[0]?.id ?? ''
  }, [tree])

  const isOpen = (id: string) => open[id] ?? id === firstOpenChapter
  const isBlockOpen = (id: string) => open[id] ?? id === firstOpenBlock

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-sidebar-border/60 bg-sidebar/35">
      <header className="shrink-0 border-b border-border/55 px-4 py-3.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[9px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
            Knowledge Tree
          </span>
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            title="刷新"
          >
            <RefreshCw className={cn('size-3', loading && 'animate-spin')} />
          </button>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary">
            <BookOpen className="size-3.5" />
          </span>
          <div className="min-w-0">
            <h2 className="font-serif text-[16px] font-semibold tracking-tight">知识树</h2>
            <p className="text-[9.5px] text-muted-foreground">
              {tree ? `${tree.progress.mastered} / ${tree.progress.total} 已通关` : '加载中…'}
            </p>
          </div>
        </div>

        <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-muted/60">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary/70 to-emerald-500 transition-all duration-500"
            style={{ width: `${Math.round((tree?.progress.ratio ?? 0) * 100)}%` }}
          />
        </div>
        {error && <p className="mt-2 text-[9.5px] text-rose-500">{error}</p>}
      </header>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2.5 py-2.5">
        {loading && !tree && (
          <div className="flex items-center gap-2 px-2 py-6 text-[11px] text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" /> 正在读取知识树…
          </div>
        )}

        <div className="space-y-1">
          {(tree?.chapters ?? []).map((chapter) => {
            const expanded = isOpen(chapter.id)
            const done = chapter.mastered_count === chapter.kps.length
            return (
              <div key={chapter.id}>
                <button
                  type="button"
                  onClick={() => setOpen((prev) => ({ ...prev, [chapter.id]: !expanded }))}
                  className="flex w-full items-center gap-1.5 rounded-md px-1.5 py-1.5 text-left transition-colors hover:bg-accent/60"
                >
                  {expanded ? (
                    <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
                  )}
                  <span
                    className={cn(
                      'min-w-0 flex-1 truncate text-[11px] font-medium',
                      done ? 'text-emerald-700' : 'text-foreground/80',
                    )}
                  >
                    {chapter.name}
                  </span>
                  <span className="shrink-0 text-[9.5px] text-muted-foreground">
                    {chapter.mastered_count}/{chapter.kps.length}
                  </span>
                </button>

                {expanded && (
                  <div className="mt-0.5 space-y-0.5 border-l border-border/55 pl-2.5">
                    {/* 第三级：讲 → 分支 → 知识点。分支来自教材 L1，带考频档（必考/高频/边缘）。
                        没有 blocks 的老响应仍然按平铺渲染，避免接口升级时白屏。 */}
                    {(chapter.blocks?.length ? chapter.blocks : [{ id: chapter.id, name: '', kps: chapter.kps }]).map(
                      (block) => {
                        const blockOpen = isBlockOpen(block.id)
                        const blockDone =
                          block.kps.length > 0 && block.kps.every((kp) => kp.mastered)
                        const renderKp = (kp: (typeof block.kps)[number]) => {
                          const isActive = activeKpId === kp.id
                          const openDetail = detailOpen[kp.id] ?? false
                          const detail = details[kp.id]
                          return (
                            <div key={kp.id}>
                              <div className="flex items-center gap-0.5">
                                <button
                                  type="button"
                                  onClick={() => void toggleDetail(kp)}
                                  title={openDetail ? '收起教材要点' : '展开教材要点（要点可单独开讲）'}
                                  className="shrink-0 rounded p-0.5 text-muted-foreground/60 transition-colors hover:bg-accent/60"
                                >
                                  {openDetail ? (
                                    <ChevronDown className="size-2.5" />
                                  ) : (
                                    <ChevronRight className="size-2.5" />
                                  )}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => requestStart(kp)}
                                  title={`${kp.name}｜考频 ${kp.exam_weight}/5${kp.mastered ? '｜已通关' : ''}`}
                                  className={cn(
                                    'group flex min-w-0 flex-1 items-center gap-1.5 rounded-md px-1 py-1 text-left transition-colors',
                                    isActive ? 'bg-primary/10 text-primary' : 'hover:bg-accent/60',
                                  )}
                                >
                                  {kp.mastered ? (
                                    <span className="grid size-3.5 shrink-0 place-items-center rounded-full bg-emerald-500 text-white">
                                      <Check className="size-2.5" />
                                    </span>
                                  ) : (
                                    <Circle className="size-3 shrink-0 text-muted-foreground/45" />
                                  )}
                                  <span
                                    className={cn(
                                      'min-w-0 flex-1 truncate text-[10.5px] leading-5',
                                      kp.mastered ? 'text-emerald-700/90' : 'text-muted-foreground/90',
                                    )}
                                  >
                                    {kp.name}
                                  </span>
                                  {!kp.mastered && kp.exam_weight >= 5 && (
                                    <span className="shrink-0 rounded bg-rose-500/10 px-1 text-[8.5px] font-medium text-rose-600">
                                      高频
                                    </span>
                                  )}
                                </button>
                              </div>

                              {/* 第四级：教材要点（原树 L3）。点某一条 = 只讲这一条 */}
                              {openDetail && (
                                <div className="mt-0.5 space-y-0.5 border-l border-border/50 pl-2">
                                  {detail === undefined && (
                                    <div className="px-1 py-0.5 text-[9px] text-muted-foreground/60">读取教材要点…</div>
                                  )}
                                  {detail === null && (
                                    <div className="px-1 py-0.5 text-[9px] text-rose-500/80">这个知识点的细节没读到</div>
                                  )}
                                  {detail &&
                                    (detail.points.length > 0 ? (
                                      detail.points.map((point, i) => (
                                        <button
                                          key={i}
                                          type="button"
                                          onClick={() => requestStart(kp, point)}
                                          title={`只讲这一条：${point}`}
                                          className="flex w-full items-start gap-1 rounded px-1 py-0.5 text-left text-[9.5px] leading-4 text-muted-foreground/90 transition-colors hover:bg-accent/60"
                                        >
                                          <span className="shrink-0 text-primary/50">·</span>
                                          <span className="min-w-0 flex-1 break-words">{point}</span>
                                        </button>
                                      ))
                                    ) : (
                                      <div className="px-1 py-0.5 text-[9px] text-muted-foreground/60">教材没有拆更细的要点</div>
                                    ))}
                                  {detail && detail.types.length > 0 && (
                                    <div className="px-1 pt-0.5 text-[9px] leading-4 text-muted-foreground/70">
                                      {detail.types.map((t, i) => (
                                        <div key={i} className="break-words">
                                          题型：{t.name}
                                          {t.steps && t.steps.length > 0 && (
                                            <span className="text-muted-foreground/60"> → {t.steps.join(' → ')}</span>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                  {detail && detail.extras.length > 0 && (
                                    <div className="px-1 text-[9px] leading-4 text-muted-foreground/60 break-words">
                                      提速：{detail.extras.map((e) => e.name).join('、')}
                                    </div>
                                  )}
                                  {detail && detail.examples.length > 0 && (
                                    <div className="px-1 text-[9px] leading-4 text-muted-foreground/60">
                                      教材例题：{detail.examples.join(' ')}
                                    </div>
                                  )}
                                  {detail && detail.evidence && (
                                    <div className="px-1 text-[9px] leading-4 text-muted-foreground/55 break-words">
                                      考纲依据：{detail.evidence}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        }

                        if (!block.name) {
                          return <div key={block.id}>{block.kps.map(renderKp)}</div>
                        }

                        return (
                          <div key={block.id}>
                            <button
                              type="button"
                              onClick={() => setOpen((prev) => ({ ...prev, [block.id]: !blockOpen }))}
                              title={block.name}
                              className="flex w-full items-center gap-1 rounded px-1 py-1 text-left transition-colors hover:bg-accent/50"
                            >
                              {blockOpen ? (
                                <ChevronDown className="size-2.5 shrink-0 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="size-2.5 shrink-0 text-muted-foreground" />
                              )}
                              <span
                                className={cn(
                                  'min-w-0 flex-1 truncate text-[10px] font-medium',
                                  blockDone ? 'text-emerald-700' : 'text-foreground/70',
                                )}
                              >
                                {block.name}
                              </span>
                              <span className="shrink-0 text-[8.5px] text-muted-foreground">
                                {block.tier_label}
                              </span>
                              <span className="shrink-0 text-[8.5px] text-muted-foreground">
                                {block.kps.filter((kp) => kp.mastered).length}/{block.kps.length}
                              </span>
                            </button>
                            {blockOpen && (
                              <div className="mt-0.5 space-y-0.5 border-l border-border/40 pl-2">
                                {block.kps.map(renderKp)}
                                {(block.conclusion_list?.length ?? 0) > 0 && (
                                  <div className="pt-0.5">
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setOpen((prev) => ({ ...prev, [`c:${block.id}`]: !prev[`c:${block.id}`] }))
                                      }
                                      className="flex w-full items-center gap-1 rounded px-1 py-0.5 text-left text-[9px] text-muted-foreground/70 transition-colors hover:bg-accent/60"
                                    >
                                      {open[`c:${block.id}`] ? (
                                        <ChevronDown className="size-2.5 shrink-0" />
                                      ) : (
                                        <ChevronRight className="size-2.5 shrink-0" />
                                      )}
                                      本分支结论（{block.conclusions ?? block.conclusion_list?.length}）
                                    </button>
                                    {open[`c:${block.id}`] && (
                                      <div className="space-y-0.5 border-l border-border/50 pl-2">
                                        {(block.conclusion_list ?? []).map((text, i) => (
                                          <div
                                            key={i}
                                            className="px-1 text-[9px] leading-4 text-muted-foreground/80 break-words"
                                          >
                                            {i + 1}. {text}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      },
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <footer className="shrink-0 border-t border-border/50 px-3 py-3">
        {tree?.next_kp ? (
          <button
            type="button"
            onClick={() => tree.next_kp && requestStart(tree.next_kp)}
            className="flex w-full items-center gap-2 rounded-lg border border-primary/35 bg-primary/[0.06] px-2.5 py-2 text-left transition-colors hover:bg-primary/10"
          >
            <Target className="size-3.5 shrink-0 text-primary" />
            <span className="min-w-0 flex-1">
              <span className="block text-[9px] tracking-wide text-muted-foreground uppercase">下一站</span>
              <span className="block truncate text-[11px] font-medium text-foreground/85">
                {tree.next_kp.name}
              </span>
            </span>
            <ChevronRight className="size-3.5 shrink-0 text-primary" />
          </button>
        ) : (
          <p className="px-1 text-[10px] text-muted-foreground">全部知识点已通关 🎉</p>
        )}
      </footer>
    </aside>
  )
}
