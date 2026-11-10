'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowUpRight,
  Check,
  ChevronRight,
  Copy,
  LibraryBig,
  PanelLeftClose,
  Plus,
  Search,
  SearchX,
  Waypoints,
  X,
} from 'lucide-react'
import { MathText } from '@/components/math/math-text'
import { cn } from '@/lib/utils'
import {
  buildKnowledgeSections,
  flattenKnowledgeNodes,
  type KnowledgeNode,
  type KnowledgeSection,
} from '@/lib/knowledge-tree'
import type { PromptChapter, PromptStage, StageProgress } from '@/lib/prompt-types'

type Selection = {
  chapterId: string
  chapterTitle: string
  sectionTitle: string
  node: KnowledgeNode
}

type KnowledgeSidebarProps = {
  chapters: PromptChapter[]
  stages: PromptStage[]
  activeChapterId: string
  activeStageId: string
  stageProgress: StageProgress[]
  onSelectChapter: (id: string) => void
  onSelectStage: (chapterId: string, stageId: string) => void
  onCreateChapter: () => void
  onPrefill: (text: string) => void
  onCollapse: () => void
}

type SearchResult =
  | { kind: 'chapter'; chapter: PromptChapter }
  | { kind: 'stage'; chapter: PromptChapter; stage: PromptStage; index: number }
  | { kind: 'section'; chapter: PromptChapter; section: KnowledgeSection }
  | {
      kind: 'point'
      chapter: PromptChapter
      section: KnowledgeSection
      node: KnowledgeNode
    }

function matches(value: string, query: string) {
  return value.toLowerCase().includes(query)
}

function filterNodes(nodes: KnowledgeNode[], query: string): KnowledgeNode[] {
  return nodes.flatMap((node) => {
    const children = filterNodes(node.children, query)
    if (matches(node.label, query)) return [{ ...node, children: node.children }]
    if (children.length > 0) return [{ ...node, children }]
    return []
  })
}

function stageState(
  progress: StageProgress[] | undefined,
  chapterId: string,
  stageId: string,
) {
  return progress?.find(
    (item) => item.chapterId === chapterId && item.stageId === stageId,
  )
}

function promptForNode(node: KnowledgeNode) {
  const label = node.label.replace(/\$/g, '').replace(/\s+/g, ' ').trim()
  return `请围绕「${label}」展开讲解：先说明它解决什么问题，再给出模式识别信号、解题步骤和一个真实出题例子。`
}

export function KnowledgeSidebar({
  chapters,
  stages,
  activeChapterId,
  activeStageId,
  stageProgress,
  onSelectChapter,
  onSelectStage,
  onCreateChapter,
  onPrefill,
  onCollapse,
}: KnowledgeSidebarProps) {
  const [query, setQuery] = useState('')
  const [openChapters, setOpenChapters] = useState<Record<string, boolean>>({
    [activeChapterId]: true,
  })
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({})
  const [selection, setSelection] = useState<Selection | null>(null)
  const [copied, setCopied] = useState(false)
  const initializedChapter = useRef('')
  const copiedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const sectionMap = useMemo(() => {
    const map = new Map<string, KnowledgeSection[]>()
    chapters.forEach((chapter) => {
      map.set(chapter.id, buildKnowledgeSections(chapter.skeleton))
    })
    return map
  }, [chapters])

  useEffect(() => {
    if (initializedChapter.current === activeChapterId) return
    initializedChapter.current = activeChapterId
    setOpenChapters((previous) => ({ ...previous, [activeChapterId]: true }))
    setSelection(null)
    const sections = sectionMap.get(activeChapterId) ?? []
    const primary =
      sections.find((section) => /基础|结构|知识/.test(section.title)) ?? sections[0]
    if (primary) {
      setOpenSections((previous) => ({
        ...previous,
        [`${activeChapterId}:${primary.id}`]: true,
      }))
    }
  }, [activeChapterId, sectionMap])

  useEffect(
    () => () => {
      if (copiedTimer.current) clearTimeout(copiedTimer.current)
    },
    [],
  )

  const normalizedQuery = query.trim().toLowerCase()

  const searchResults = useMemo(() => {
    if (!normalizedQuery) return []
    const results: SearchResult[] = []
    chapters.forEach((chapter) => {
      const chapterHit = matches(chapter.title, normalizedQuery)
      if (chapterHit) results.push({ kind: 'chapter', chapter })

      stages.forEach((stage, index) => {
        if (chapterHit || matches(stage.name, normalizedQuery)) {
          results.push({ kind: 'stage', chapter, stage, index })
        }
      })

      const sections = sectionMap.get(chapter.id) ?? []
      sections.forEach((section) => {
        if (chapterHit || matches(section.title, normalizedQuery)) {
          results.push({ kind: 'section', chapter, section })
          return
        }
        const nodes = filterNodes(section.nodes, normalizedQuery)
        flattenKnowledgeNodes(nodes).forEach((node) => {
          results.push({ kind: 'point', chapter, section, node })
        })
      })
    })
    return results.slice(0, 40)
  }, [chapters, normalizedQuery, sectionMap, stages])

  const copySelection = async () => {
    if (!selection) return
    try {
      await navigator.clipboard.writeText(selection.node.raw)
      setCopied(true)
      if (copiedTimer.current) clearTimeout(copiedTimer.current)
      copiedTimer.current = setTimeout(() => setCopied(false), 1400)
    } catch {
      // Clipboard may be unavailable in some embeddings.
    }
  }

  const selectNode = (chapter: PromptChapter, section: KnowledgeSection, node: KnowledgeNode) => {
    setSelection({
      chapterId: chapter.id,
      chapterTitle: chapter.title,
      sectionTitle: section.title,
      node,
    })
    setCopied(false)
    setQuery('')
    setOpenChapters((previous) => ({ ...previous, [chapter.id]: true }))
    setOpenSections((previous) => ({
      ...previous,
      [`${chapter.id}:${section.id}`]: true,
    }))
  }

  const clearSelection = () => {
    setSelection(null)
    setCopied(false)
  }

  return (
    <aside
      className="paper-panel flex h-full w-full flex-col border-r border-sidebar-border/70"
      aria-label="课程知识树"
    >
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-sidebar-border/60 px-4">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-[10px] font-medium tracking-[0.22em] text-muted-foreground uppercase">
            Curriculum
          </span>
          <span className="rounded-full border border-border/60 bg-card/60 px-1.5 py-px font-mono text-[9.5px] text-muted-foreground">
            {chapters.length} 章
          </span>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
          aria-label="收起课程目录"
          title="收起目录"
        >
          <PanelLeftClose className="size-4" />
        </button>
      </div>

      <div className="shrink-0 px-4 pt-4">
        <h2 className="font-serif text-[17px] font-semibold tracking-tight">
          高等数学
          <span className="ml-1.5 text-[11.5px] font-normal text-muted-foreground">
            考研数学一
          </span>
        </h2>
        <p className="mt-1 text-[11px] leading-[1.65] text-muted-foreground text-pretty">
          沿着知识树走：先选章节，再选阶段，卡住时点一个知识点。
        </p>
        <label className="mt-3 flex h-9 items-center gap-2 rounded-xl border border-border/60 bg-card/70 px-2.5 transition-colors focus-within:border-primary/40">
          <Search className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索章节、阶段、知识点"
            className="min-w-0 flex-1 bg-transparent text-[12px] text-foreground outline-none placeholder:text-muted-foreground/80"
            aria-label="搜索课程知识树"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="inline-flex size-5 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              aria-label="清空搜索"
            >
              <X className="size-3" />
            </button>
          )}
        </label>
      </div>

      <nav className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2 pt-3 pb-4" aria-label="课程目录">
        {normalizedQuery ? (
          <SearchResults
            results={searchResults}
            activeStageId={activeStageId}
            onSelectChapter={(chapter) => {
              onSelectChapter(chapter.id)
              setQuery('')
            }}
            onSelectStage={(chapter, stage) => {
              onSelectStage(chapter.id, stage.id)
              setQuery('')
            }}
            onSelectSection={(chapter, section) => {
              onSelectChapter(chapter.id)
              setQuery('')
              setOpenChapters((previous) => ({ ...previous, [chapter.id]: true }))
              setOpenSections((previous) => ({
                ...previous,
                [`${chapter.id}:${section.id}`]: true,
              }))
            }}
            onSelectNode={selectNode}
          />
        ) : (
          chapters.map((chapter) => {
            const open = openChapters[chapter.id] ?? false
            const sections = sectionMap.get(chapter.id) ?? []
            return (
              <div key={chapter.id} className="mb-1">
                <div
                  className={cn(
                    'group flex items-start gap-0.5 rounded-xl px-0.5 transition-colors',
                    chapter.id === activeChapterId && 'bg-sidebar-accent/50',
                  )}
                >
                  <button
                    type="button"
                    onClick={() =>
                      setOpenChapters((previous) => ({
                        ...previous,
                        [chapter.id]: !open,
                      }))
                    }
                    className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
                    aria-expanded={open}
                    aria-label={open ? '收起章节' : '展开章节'}
                  >
                    <ChevronRight
                      className={cn('size-3.5 transition-transform duration-200', open && 'rotate-90')}
                    />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onSelectChapter(chapter.id)
                      setOpenChapters((previous) => ({ ...previous, [chapter.id]: true }))
                    }}
                    className="min-w-0 flex-1 py-1.5 pr-2 text-left"
                    aria-current={chapter.id === activeChapterId ? 'true' : undefined}
                  >
                    <span
                      className={cn(
                        'block font-serif text-[14.5px] leading-[1.5] font-medium tracking-tight text-pretty',
                        chapter.id === activeChapterId ? 'text-foreground' : 'text-foreground/80',
                      )}
                    >
                      {chapter.title}
                    </span>
                  </button>
                  {chapter.id === activeChapterId && (
                    <span className="mt-2.5 mr-2 size-1.5 shrink-0 rounded-full bg-primary" />
                  )}
                </div>

                {open && (
                  <div className="mt-1 ml-[13px] border-l border-sidebar-border/70 pl-2">
                    <p className="flex items-center gap-1.5 px-2 py-1.5 text-[10.5px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
                      <Waypoints className="size-3" aria-hidden="true" />
                      学习流程
                    </p>
                    <div className="space-y-0.5">
                      {stages.map((stage, index) => {
                        const isActive = stage.id === activeStageId
                        const progress = stageState(stageProgress, chapter.id, stage.id)
                        return (
                          <button
                            key={stage.id}
                            type="button"
                            onClick={() => onSelectStage(chapter.id, stage.id)}
                            className={cn(
                              'group flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors',
                              isActive
                                ? 'bg-card/90 shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_5%,transparent)]'
                                : 'hover:bg-sidebar-accent/45',
                            )}
                            aria-current={isActive ? 'step' : undefined}
                          >
                            <span
                              className={cn(
                                'mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border font-mono text-[9.5px] leading-none',
                                isActive
                                  ? 'border-primary/30 bg-primary/10 text-primary'
                                  : progress?.runCount
                                    ? 'border-sage/25 bg-sage/10 text-sage'
                                    : 'border-border/60 bg-card/40 text-muted-foreground',
                              )}
                            >
                              {String(index + 1).padStart(2, '0')}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span
                                className={cn(
                                  'block truncate text-[12px] leading-[1.45]',
                                  isActive ? 'font-medium text-foreground' : 'text-foreground/75',
                                )}
                              >
                                {stage.name}
                              </span>
                              <span className="mt-0.5 block text-[9.5px] leading-3 text-muted-foreground">
                                {progress?.runCount
                                  ? `已运行 ${progress.runCount} 次`
                                  : isActive
                                    ? '当前阶段 · 未运行'
                                    : '未运行'}
                              </span>
                            </span>
                            {isActive && (
                              <span className="mt-2 size-1 shrink-0 rounded-full bg-primary" />
                            )}
                          </button>
                        )
                      })}
                    </div>

                    <p className="mt-3 flex items-center gap-1.5 px-2 py-1.5 text-[10.5px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
                      <LibraryBig className="size-3" aria-hidden="true" />
                      知识结构
                    </p>
                    <div className="space-y-0.5 pb-2">
                      {sections.length === 0 && (
                        <p className="px-2 py-2 text-[10.5px] leading-4 text-muted-foreground">
                          本章还没有知识骨架，可在右侧「章节骨架」里补上。
                        </p>
                      )}
                      {sections.map((section) => {
                        const sectionKey = `${chapter.id}:${section.id}`
                        const sectionOpen = openSections[sectionKey] ?? false
                        return (
                          <div key={sectionKey}>
                            <button
                              type="button"
                              onClick={() =>
                                setOpenSections((previous) => ({
                                  ...previous,
                                  [sectionKey]: !sectionOpen,
                                }))
                              }
                              className="group flex w-full items-start gap-1.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-sidebar-accent/45"
                              aria-expanded={sectionOpen}
                            >
                              <ChevronRight
                                className={cn(
                                  'mt-0.5 size-3 shrink-0 text-muted-foreground/80 transition-transform duration-200',
                                  sectionOpen && 'rotate-90',
                                )}
                              />
                              <span className="min-w-0 flex-1 text-[11.5px] leading-[1.5] font-medium text-foreground/75 group-hover:text-foreground">
                                {section.title}
                              </span>
                              {section.count > 0 && (
                                <span className="mt-0.5 font-mono text-[9.5px] text-muted-foreground/80">
                                  {section.count}
                                </span>
                              )}
                            </button>
                            {sectionOpen && (
                              <div className="ml-[7px] border-l border-sidebar-border/60 pb-1 pl-1.5">
                                {section.summary && (
                                  <p className="px-2 py-1.5 text-[11px] leading-[1.75] text-muted-foreground">
                                    {section.summary}
                                  </p>
                                )}
                                <KnowledgeNodeRows
                                  nodes={section.nodes}
                                  chapter={chapter}
                                  section={section}
                                  selectedId={selection?.node.id ?? null}
                                  onSelect={selectNode}
                                />
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </nav>

      {selection && (
        <div className="shrink-0 border-t border-sidebar-border/70 bg-card/75 px-3 py-3">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate text-[9.5px] tracking-[0.14em] text-muted-foreground uppercase">
              {selection.sectionTitle}
            </p>
            <button
              type="button"
              onClick={clearSelection}
              className="inline-flex size-5 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              aria-label="取消选中知识点"
            >
              <X className="size-3" />
            </button>
          </div>
          <p className="mt-1 line-clamp-3 text-[12px] leading-[1.65] text-foreground/85">
            <MathText>{selection.node.label}</MathText>
          </p>
          <div className="mt-2 flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => {
                onPrefill(promptForNode(selection.node))
                clearSelection()
              }}
              className="inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary px-2.5 text-[11.5px] font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              <ArrowUpRight className="size-3.5" />
              带入追问
            </button>
            <button
              type="button"
              onClick={copySelection}
              className="inline-flex size-8 items-center justify-center rounded-lg border border-border/70 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              aria-label="复制知识点"
              title="复制知识点"
            >
              {copied ? <Check className="size-3.5 text-sage" /> : <Copy className="size-3.5" />}
            </button>
          </div>
          <p className="mt-1.5 text-[9.5px] leading-3 text-muted-foreground/80">
            只填入输入框，不会自动发送。
          </p>
        </div>
      )}

      <div className="shrink-0 border-t border-sidebar-border/70 px-3 py-3">
        <button
          type="button"
          onClick={onCreateChapter}
          className="flex h-9 w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border/80 text-[11.5px] text-muted-foreground transition-colors hover:border-primary/35 hover:bg-highlight/60 hover:text-primary"
        >
          <Plus className="size-3.5" />
          新增章节
        </button>
        <p className="mt-2 text-center font-mono text-[9.5px] text-muted-foreground/75">
          {chapters.length} CHAPTERS · {stages.length} STAGES
        </p>
      </div>
    </aside>
  )
}

function KnowledgeNodeRows({
  nodes,
  chapter,
  section,
  selectedId,
  onSelect,
}: {
  nodes: KnowledgeNode[]
  chapter: PromptChapter
  section: KnowledgeSection
  selectedId: string | null
  onSelect: (chapter: PromptChapter, section: KnowledgeSection, node: KnowledgeNode) => void
}) {
  return (
    <>
      {nodes.map((node) => {
        const selected = selectedId === node.id
        return (
          <div key={node.id}>
            <button
              type="button"
              onClick={() => onSelect(chapter, section, node)}
              className={cn(
                'group flex w-full items-start gap-2 rounded-lg px-2 py-[5px] text-left transition-colors',
                selected ? 'bg-primary/10 text-foreground' : 'hover:bg-sidebar-accent/55',
              )}
              aria-pressed={selected}
            >
              <span
                className={cn(
                  'mt-[7px] size-1 shrink-0 rounded-full transition-colors',
                  selected
                    ? 'bg-primary'
                    : 'bg-muted-foreground/35 group-hover:bg-primary/60',
                )}
              />
              <span
                className={cn(
                  'min-w-0 flex-1 text-[11px] leading-[1.7] text-pretty',
                  selected ? 'text-foreground' : 'text-foreground/70 group-hover:text-foreground/90',
                )}
              >
                <MathText>{node.label}</MathText>
              </span>
            </button>
            {node.children.length > 0 && (
              <div className="ml-[10px] border-l border-sidebar-border/60 pl-1.5">
                <KnowledgeNodeRows
                  nodes={node.children}
                  chapter={chapter}
                  section={section}
                  selectedId={selectedId}
                  onSelect={onSelect}
                />
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}

function SearchResults({
  results,
  activeStageId,
  onSelectChapter,
  onSelectStage,
  onSelectSection,
  onSelectNode,
}: {
  results: SearchResult[]
  activeStageId: string
  onSelectChapter: (chapter: PromptChapter) => void
  onSelectStage: (chapter: PromptChapter, stage: PromptStage) => void
  onSelectSection: (chapter: PromptChapter, section: KnowledgeSection) => void
  onSelectNode: (
    chapter: PromptChapter,
    section: KnowledgeSection,
    node: KnowledgeNode,
  ) => void
}) {
  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 px-4 py-14 text-center">
        <SearchX className="size-5 text-muted-foreground/70" aria-hidden="true" />
        <p className="text-[11.5px] text-muted-foreground">没有匹配的章节或知识点</p>
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {results.map((result, index) => {
        if (result.kind === 'chapter') {
          return (
            <button
              key={`chapter-${result.chapter.id}-${index}`}
              type="button"
              onClick={() => onSelectChapter(result.chapter)}
              className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left hover:bg-sidebar-accent/55"
            >
              <LibraryBig className="mt-0.5 size-3.5 shrink-0 text-primary" />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 font-serif text-[12px] leading-4 font-medium">
                  {result.chapter.title}
                </span>
                <span className="mt-0.5 block text-[9px] text-muted-foreground">章节</span>
              </span>
            </button>
          )
        }
        if (result.kind === 'stage') {
          return (
            <button
              key={`stage-${result.chapter.id}-${result.stage.id}-${index}`}
              type="button"
              onClick={() => onSelectStage(result.chapter, result.stage)}
              className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left hover:bg-sidebar-accent/55"
            >
              <span
                className={cn(
                  'mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border font-mono text-[9px]',
                  result.stage.id === activeStageId
                    ? 'border-primary/30 bg-primary/10 text-primary'
                    : 'border-border/60 text-muted-foreground',
                )}
              >
                {String(result.index + 1).padStart(2, '0')}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[11px] font-medium">{result.stage.name}</span>
                <span className="mt-0.5 block truncate text-[9px] text-muted-foreground">
                  学习阶段 · {result.chapter.title}
                </span>
              </span>
            </button>
          )
        }
        if (result.kind === 'section') {
          return (
            <button
              key={`section-${result.chapter.id}-${result.section.id}-${index}`}
              type="button"
              onClick={() => onSelectSection(result.chapter, result.section)}
              className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left hover:bg-sidebar-accent/55"
            >
              <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 text-[11px] font-medium">{result.section.title}</span>
                <span className="mt-0.5 block text-[9px] text-muted-foreground">
                  知识模块 · {result.section.count} 个知识点
                </span>
              </span>
            </button>
          )
        }
        return (
          <button
            key={`point-${result.chapter.id}-${result.node.id}-${index}`}
            type="button"
            onClick={() => onSelectNode(result.chapter, result.section, result.node)}
            className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-sidebar-accent/55"
          >
            <span className="mt-[7px] size-1 shrink-0 rounded-full bg-primary/50" />
            <span className="min-w-0 flex-1">
              <span className="line-clamp-2 text-[10.5px] leading-[1.6]">
                <MathText>{result.node.label}</MathText>
              </span>
              <span className="mt-0.5 block truncate text-[9px] text-muted-foreground">
                {result.section.title}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
