'use client'

import { memo, useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  FileText,
  History,
  Layers,
  Loader2,
  Lock,
  LockOpen,
  Play,
  Plus,
  RotateCcw,
  Save,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { composeFirstPreview } from '@/lib/prompt-compose'
import type { PromptVersion, WorkbenchPayload } from '@/lib/prompt-types'
import { ChapterSkeletonDialog } from './chapter-skeleton-dialog'
import { PromptPreview } from './prompt-preview'

export type PromptDrafts = {
  globalPrompt: string
  systemInstruction: string
  stagePrompt: string
}

type PromptWorkbenchPanelProps = {
  payload: WorkbenchPayload
  busy: boolean
  onSelectStage: (id: string) => void
  onSelectChapter: (id: string) => void
  onUpdateGlobal: (globalPrompt: string) => void
  onToggleGlobalLock: (locked: boolean) => void
  onUpdateStage: (patch: {
    name?: string
    systemInstruction?: string
    stagePrompt?: string
  }) => void
  onCreateStage: () => void
  onDeleteStage: (id: string) => void
  onMoveStage: (id: string, direction: 'up' | 'down') => void
  onCreateChapter: () => void
  onUpdateChapter: (patch: { title?: string; skeleton?: string }) => void
  onSaveVersion: () => void
  onSelectVersion: (version: PromptVersion) => void
  onSelectRun: (runId: string) => void
  onRunStage: (drafts: PromptDrafts) => void
  onNextStage: () => void
  onPrevStage: () => void
  onResetRun: () => void
}

type LayerKey = 'G' | 'S' | 'P' | 'D'

const LAYER_META: Record<LayerKey, { label: string; hint: string; badge: string }> = {
  G: {
    label: '全局底座',
    hint: '整条流水线共用的人格与边界',
    badge: 'border-layer-g/25 bg-layer-g/10 text-layer-g',
  },
  S: {
    label: '系统设定',
    hint: '每次 API 调用都会附带的系统指令',
    badge: 'border-layer-s/25 bg-layer-s/10 text-layer-s',
  },
  P: {
    label: '阶段任务',
    hint: '本阶段真正要 AI 完成的事情',
    badge: 'border-layer-p/30 bg-layer-p/10 text-layer-p',
  },
  D: {
    label: '动态上下文',
    hint: '章节骨架与上一阶段产出，自动注入',
    badge: 'border-layer-d/25 bg-layer-d/10 text-layer-d',
  },
}

function PromptWorkbenchPanelComponent({
  payload,
  busy,
  onSelectStage,
  onSelectChapter,
  onUpdateGlobal,
  onToggleGlobalLock,
  onUpdateStage,
  onCreateStage,
  onDeleteStage,
  onMoveStage,
  onCreateChapter,
  onUpdateChapter,
  onSaveVersion,
  onSelectVersion,
  onSelectRun,
  onRunStage,
  onNextStage,
  onPrevStage,
  onResetRun,
}: PromptWorkbenchPanelProps) {
  const stage = payload.stages.find((item) => item.id === payload.activeStageId)
  const chapter = payload.chapters.find((item) => item.id === payload.activeChapterId)
  const stageIndex = payload.stages.findIndex((item) => item.id === payload.activeStageId)
  const chapterIndex = payload.chapters.findIndex(
    (item) => item.id === payload.activeChapterId,
  )
  const isLastStage = stageIndex === payload.stages.length - 1
  const isFirstStage = stageIndex <= 0

  const [globalDraft, setGlobalDraft] = useState(payload.workflow.globalPrompt)
  const [systemDraft, setSystemDraft] = useState(stage?.systemInstruction ?? '')
  const [stageDraft, setStageDraft] = useState(stage?.stagePrompt ?? '')
  const [nameDraft, setNameDraft] = useState(stage?.name ?? '')
  const [openLayer, setOpenLayer] = useState<LayerKey | null>('P')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [skeletonOpen, setSkeletonOpen] = useState(false)
  const [versionNote, setVersionNote] = useState('')
  const [copiedContext, setCopiedContext] = useState(false)

  const copiedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSaved = useRef<PromptDrafts>({
    globalPrompt: payload.workflow.globalPrompt,
    systemInstruction: stage?.systemInstruction ?? '',
    stagePrompt: stage?.stagePrompt ?? '',
  })
  const currentDrafts = useRef<PromptDrafts>({
    globalPrompt: globalDraft,
    systemInstruction: systemDraft,
    stagePrompt: stageDraft,
  })
  const stageKeyRef = useRef('')

  useEffect(() => {
    currentDrafts.current = {
      globalPrompt: globalDraft,
      systemInstruction: systemDraft,
      stagePrompt: stageDraft,
    }
  }, [globalDraft, systemDraft, stageDraft])

  useEffect(() => {
    if (!stage || !chapter) return
    const key = `${stage.id}:${chapter.id}`
    const switched = stageKeyRef.current !== key
    const current = currentDrafts.current
    const hasUnsaved =
      current.globalPrompt !== lastSaved.current.globalPrompt ||
      current.systemInstruction !== lastSaved.current.systemInstruction ||
      current.stagePrompt !== lastSaved.current.stagePrompt

    if (switched || !hasUnsaved) {
      const next: PromptDrafts = {
        globalPrompt: payload.workflow.globalPrompt,
        systemInstruction: stage.systemInstruction,
        stagePrompt: stage.stagePrompt,
      }
      setGlobalDraft(next.globalPrompt)
      setSystemDraft(next.systemInstruction)
      setStageDraft(next.stagePrompt)
    }

    if (switched) {
      setOpenLayer('P')
      setVersionNote('')
    }

    stageKeyRef.current = key
    setNameDraft(stage.name)
    lastSaved.current = {
      globalPrompt: payload.workflow.globalPrompt,
      systemInstruction: stage.systemInstruction,
      stagePrompt: stage.stagePrompt,
    }
  }, [
    stage?.id,
    chapter?.id,
    payload.workflow.globalPrompt,
    stage?.systemInstruction,
    stage?.stagePrompt,
    stage?.name,
  ])

  useEffect(() => {
    if (!stage) return
    const timer = setTimeout(() => {
      const saved = lastSaved.current
      if (!payload.workflow.globalLocked && globalDraft !== saved.globalPrompt) {
        saved.globalPrompt = globalDraft
        onUpdateGlobal(globalDraft)
      }
      if (systemDraft !== saved.systemInstruction || stageDraft !== saved.stagePrompt) {
        saved.systemInstruction = systemDraft
        saved.stagePrompt = stageDraft
        onUpdateStage({ systemInstruction: systemDraft, stagePrompt: stageDraft })
      }
    }, 700)
    return () => clearTimeout(timer)
  }, [
    globalDraft,
    systemDraft,
    stageDraft,
    payload.workflow.globalLocked,
    stage?.id,
    onUpdateGlobal,
    onUpdateStage,
  ])

  useEffect(
    () => () => {
      if (copiedTimer.current) clearTimeout(copiedTimer.current)
    },
    [],
  )

  if (!stage || !chapter) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        正在加载提示词工作台…
      </div>
    )
  }

  const preview = composeFirstPreview(
    {
      globalPrompt: globalDraft,
      systemInstruction: systemDraft,
      stagePrompt: stageDraft,
    },
    payload.dynamicContext,
  )
  const previewChars = preview.systemText.length + preview.userText.length
  const progressByStage = new Map(
    (payload.stageProgress ?? []).map((item) => [
      `${item.chapterId}:${item.stageId}`,
      item,
    ]),
  )

  const copyContext = async () => {
    try {
      await navigator.clipboard.writeText(payload.dynamicContext)
      setCopiedContext(true)
      if (copiedTimer.current) clearTimeout(copiedTimer.current)
      copiedTimer.current = setTimeout(() => setCopiedContext(false), 1400)
    } catch {
      // Clipboard access can be unavailable in embedded browsers.
    }
  }

  const applyVersion = (version: PromptVersion) => {
    setSystemDraft(version.snapshot.systemInstruction)
    setStageDraft(version.snapshot.stagePrompt)
    if (!payload.workflow.globalLocked) {
      setGlobalDraft(version.snapshot.globalPrompt)
    }
    lastSaved.current = {
      globalPrompt: payload.workflow.globalPrompt,
      systemInstruction: version.snapshot.systemInstruction,
      stagePrompt: version.snapshot.stagePrompt,
    }
    setVersionNote(
      payload.workflow.globalLocked &&
        version.snapshot.globalPrompt !== payload.workflow.globalPrompt
        ? `${version.label} 已载入 S/P；全局 G 处于锁定状态，未载入该版本 G。`
        : `${version.label} 已载入编辑区，运行时会生成新快照。`,
    )
    setOpenLayer('P')
    onSelectVersion(version)
  }

  const layers: Array<{
    key: LayerKey
    value: string
    locked: boolean
  }> = [
    { key: 'G', value: globalDraft, locked: payload.workflow.globalLocked },
    { key: 'S', value: systemDraft, locked: false },
    { key: 'P', value: stageDraft, locked: false },
    { key: 'D', value: payload.dynamicContext, locked: true },
  ]

  return (
    <div className="flex h-full flex-col">
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[960px] flex-col gap-4 px-4 py-4">
          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">
                Chapter
              </p>
              <span className="font-mono text-[9px] text-muted-foreground/80">
                {String(chapterIndex + 1).padStart(2, '0')} /{' '}
                {String(payload.chapters.length).padStart(2, '0')}
              </span>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <label className="relative flex h-10 min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-xl border border-border/60 bg-card/70 px-3 transition-colors hover:border-primary/30">
                <span className="min-w-0 flex-1 truncate font-serif text-[13.5px] font-medium tracking-tight">
                  {chapter.title}
                </span>
                <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <select
                  value={payload.activeChapterId}
                  onChange={(event) => onSelectChapter(event.target.value)}
                  className="absolute inset-0 cursor-pointer opacity-0"
                  aria-label="选择章节"
                >
                  {payload.chapters.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => setSkeletonOpen(true)}
                className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-card/70 text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                aria-label="编辑章节骨架"
                title="编辑章节骨架"
              >
                <FileText className="size-3.5" />
              </button>
              <button
                type="button"
                onClick={onCreateChapter}
                className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-card/70 text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                aria-label="新增章节"
                title="新增章节"
              >
                <Plus className="size-3.5" />
              </button>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">
                Learning Flow
              </p>
              <button
                type="button"
                onClick={onCreateStage}
                className="inline-flex items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-primary"
              >
                <Plus className="size-3" />
                新增阶段
              </button>
            </div>
            <div className="scrollbar-thin mt-1.5 flex items-center gap-1 overflow-x-auto rounded-xl bg-muted/40 p-1">
              {payload.stages.map((item, index) => {
                const active = item.id === stage.id
                const progress = progressByStage.get(
                  `${payload.activeChapterId}:${item.id}`,
                )
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelectStage(item.id)}
                    className={cn(
                      'flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2.5 transition-all duration-200',
                      active
                        ? 'bg-card text-foreground shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_7%,transparent)]'
                        : 'text-muted-foreground hover:text-foreground',
                    )}
                    aria-current={active ? 'step' : undefined}
                  >
                    <span
                      className={cn(
                        'font-mono text-[9px]',
                        active ? 'text-primary' : 'text-muted-foreground/70',
                      )}
                    >
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className="max-w-[108px] truncate text-[11px] font-medium">
                      {item.name}
                    </span>
                    {Boolean(progress?.runCount) && (
                      <span
                        className="size-1 shrink-0 rounded-full bg-sage"
                        title={`已运行 ${progress?.runCount} 次`}
                      />
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="group/stage flex items-center gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
                Stage {String(stageIndex + 1).padStart(2, '0')}
              </p>
              <input
                value={nameDraft}
                onChange={(event) => setNameDraft(event.target.value)}
                onBlur={() => {
                  const next = nameDraft.trim()
                  if (next && next !== stage.name) onUpdateStage({ name: next })
                  else if (!next) setNameDraft(stage.name)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') event.currentTarget.blur()
                }}
                className="mt-0.5 -ml-1 w-full rounded-lg border-0 bg-transparent px-1 py-0.5 font-serif text-[18px] font-semibold tracking-tight text-foreground outline-none transition-colors hover:bg-muted/40 focus:bg-muted/55"
                placeholder="阶段名称"
                aria-label="阶段名称"
              />
            </div>
            <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover/stage:opacity-100">
              <button
                type="button"
                onClick={() => onMoveStage(stage.id, 'up')}
                disabled={isFirstStage}
                className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-25"
                title="上移阶段"
                aria-label="上移阶段"
              >
                <ChevronUp className="size-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onMoveStage(stage.id, 'down')}
                disabled={isLastStage}
                className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-25"
                title="下移阶段"
                aria-label="下移阶段"
              >
                <ChevronDown className="size-3.5" />
              </button>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(`确定删除阶段「${stage.name}」？`)) {
                    onDeleteStage(stage.id)
                  }
                }}
                disabled={payload.stages.length <= 1}
                className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-25"
                title="删除阶段"
                aria-label="删除阶段"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          </div>

          <section className="overflow-hidden rounded-2xl border border-border/60 bg-card/55">
            <div className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
              <div className="flex min-w-0 items-center gap-2">
                <Layers className="size-3.5 text-primary" aria-hidden="true" />
                <span className="text-[12px] font-medium">提示词层</span>
                <span className="font-mono text-[9.5px] text-muted-foreground">G → S → P → D</span>
              </div>
              <span className="inline-flex shrink-0 items-center gap-1.5 text-[10px] text-muted-foreground">
                <span className="size-1 rounded-full bg-sage" />
                自动保存
              </span>
            </div>

            <div className="divide-y divide-border/55">
              {layers.map((layer) => {
                const meta = LAYER_META[layer.key]
                const open = openLayer === layer.key
                return (
                  <div
                    key={layer.key}
                    className={cn('transition-colors', open && 'bg-muted/15')}
                  >
                    <button
                      type="button"
                      onClick={() => setOpenLayer(open ? null : layer.key)}
                      className="flex w-full items-start gap-3 px-4 py-3 text-left"
                      aria-expanded={open}
                    >
                      <span
                        className={cn(
                          'mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg border font-mono text-[10.5px]',
                          meta.badge,
                        )}
                      >
                        {layer.key}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-1.5 text-[12px] font-medium text-foreground">
                          {meta.label}
                          {layer.key === 'G' && payload.workflow.globalLocked && (
                            <Lock className="size-3 text-muted-foreground/80" aria-label="已锁定" />
                          )}
                          {layer.key === 'D' && (
                            <span className="rounded bg-muted px-1 py-px text-[8.5px] font-normal text-muted-foreground">
                              只读
                            </span>
                          )}
                        </span>
                        <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">
                          {meta.hint}
                        </span>
                      </span>
                      <span className="mt-0.5 shrink-0 font-mono text-[9.5px] text-muted-foreground/85">
                        {layer.value.length} 字
                      </span>
                      <ChevronDown
                        className={cn(
                          'mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform duration-200',
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
                        <div className="px-4 pb-4">
                          {layer.key === 'D' ? (
                            <>
                              <pre className="scrollbar-thin max-h-60 overflow-y-auto rounded-xl border border-border/50 bg-background/55 px-3.5 py-3 text-[11.5px] leading-[1.8] whitespace-pre-wrap text-foreground/75">
                                {payload.dynamicContext}
                              </pre>
                              <div className="mt-2 flex items-center justify-between gap-2">
                                <p className="text-[10px] text-muted-foreground">
                                  由章节骨架与上一阶段产出自动拼合，不可直接编辑。
                                </p>
                                <button
                                  type="button"
                                  onClick={copyContext}
                                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[9.5px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                >
                                  {copiedContext ? (
                                    <Check className="size-3 text-sage" />
                                  ) : (
                                    <Copy className="size-3" />
                                  )}
                                  {copiedContext ? '已复制' : '复制'}
                                </button>
                              </div>
                            </>
                          ) : layer.key === 'G' && payload.workflow.globalLocked ? (
                            <>
                              <div className="mb-2 flex items-center justify-between gap-2">
                                <p className="text-[10px] text-muted-foreground">
                                  已锁定，运行时会原样拼在最终提示词最前面。
                                </p>
                                <button
                                  type="button"
                                  onClick={() => onToggleGlobalLock(false)}
                                  className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-[9.5px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                                >
                                  <LockOpen className="size-3" />
                                  解锁编辑
                                </button>
                              </div>
                              <pre className="scrollbar-thin max-h-60 overflow-y-auto rounded-xl border border-border/50 bg-background/55 px-3.5 py-3 text-[11.5px] leading-[1.8] whitespace-pre-wrap text-foreground/75">
                                {globalDraft}
                              </pre>
                            </>
                          ) : (
                            <>
                              <textarea
                                value={layer.value}
                                onChange={(event) => {
                                  if (layer.key === 'G') setGlobalDraft(event.target.value)
                                  if (layer.key === 'S') setSystemDraft(event.target.value)
                                  if (layer.key === 'P') setStageDraft(event.target.value)
                                }}
                                rows={layer.key === 'P' ? 10 : layer.key === 'S' ? 7 : 8}
                                className="scrollbar-thin w-full resize-y rounded-xl border border-border/55 bg-background/60 px-3.5 py-3 text-[12.5px] leading-[1.85] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/40"
                                aria-label={meta.label}
                              />
                              <div className="mt-2 flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-1.5 text-[9.5px] text-muted-foreground">
                                  <span className="size-1 rounded-full bg-sage" />
                                  改动后自动保存
                                </span>
                                {layer.key === 'G' && (
                                  <button
                                    type="button"
                                    onClick={() => onToggleGlobalLock(true)}
                                    className="inline-flex items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-[9.5px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                                  >
                                    <Lock className="size-3" />
                                    锁定
                                  </button>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <div className="overflow-hidden rounded-2xl border border-border/60 bg-card/55">
            <button
              type="button"
              onClick={() => setPreviewOpen((value) => !value)}
              className="flex w-full items-center gap-2.5 px-4 py-3 text-left"
              aria-expanded={previewOpen}
            >
              <Eye className="size-3.5 text-primary/90" aria-hidden="true" />
              <span className="text-[12px] font-medium">最终发送预览</span>
              <span className="ml-auto font-mono text-[9.5px] text-muted-foreground">
                {previewChars} 字
              </span>
              <ChevronDown
                className={cn(
                  'size-3.5 text-muted-foreground transition-transform duration-200',
                  previewOpen && 'rotate-180',
                )}
              />
            </button>
            {previewOpen && (
              <div className="border-t border-border/55 p-3.5">
                <PromptPreview preview={preview} compact />
              </div>
            )}
          </div>

          <div className="overflow-hidden rounded-2xl border border-border/60 bg-card/55">
            <button
              type="button"
              onClick={() => setLibraryOpen((value) => !value)}
              className="flex w-full items-center gap-2.5 px-4 py-3 text-left"
              aria-expanded={libraryOpen}
            >
              <History className="size-3.5 text-primary/90" aria-hidden="true" />
              <span className="text-[12px] font-medium">版本与运行历史</span>
              <span className="ml-auto font-mono text-[9.5px] text-muted-foreground">
                {payload.versions.length} 版本 · {payload.runs.length} 次运行
              </span>
              <ChevronDown
                className={cn(
                  'size-3.5 text-muted-foreground transition-transform duration-200',
                  libraryOpen && 'rotate-180',
                )}
              />
            </button>

            {libraryOpen && (
              <div className="border-t border-border/55 p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] leading-4 text-muted-foreground">
                    保存当前 G / S / P 快照，随时回滚。
                  </p>
                  <button
                    type="button"
                    onClick={onSaveVersion}
                    className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border/65 px-2.5 py-1.5 text-[10.5px] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                  >
                    <Save className="size-3" />
                    保存版本
                  </button>
                </div>
                {versionNote && <p className="mt-2 text-[10px] text-primary">{versionNote}</p>}

                <div className="mt-3">
                  <p className="text-[9.5px] font-medium tracking-[0.16em] text-muted-foreground uppercase">
                    版本快照
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {payload.versions.length === 0 ? (
                      <span className="text-[10.5px] text-muted-foreground">
                        还没有保存过版本
                      </span>
                    ) : (
                      payload.versions.slice(0, 12).map((version) => (
                        <button
                          key={version.id}
                          type="button"
                          onClick={() => applyVersion(version)}
                          className="rounded-lg border border-border/60 bg-background/50 px-2 py-1 font-mono text-[10px] text-muted-foreground transition-colors hover:border-primary/35 hover:text-primary"
                          title={new Date(version.createdAt).toLocaleString()}
                        >
                          {version.label}
                        </button>
                      ))
                    )}
                  </div>
                </div>

                <div className="mt-3">
                  <p className="text-[9.5px] font-medium tracking-[0.16em] text-muted-foreground uppercase">
                    运行历史
                  </p>
                  <div className="scrollbar-thin mt-1.5 max-h-44 space-y-0.5 overflow-y-auto pr-1">
                    {payload.runs.length === 0 ? (
                      <span className="text-[10.5px] text-muted-foreground">
                        还没有运行记录
                      </span>
                    ) : (
                      payload.runs.slice(0, 12).map((run) => (
                        <button
                          key={run.id}
                          type="button"
                          onClick={() => onSelectRun(run.id)}
                          className={cn(
                            'flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-[10.5px] transition-colors hover:bg-accent/70',
                            payload.activeRun?.id === run.id &&
                              'bg-highlight/60 text-foreground',
                          )}
                        >
                          <span className="font-mono text-muted-foreground">
                            {new Date(run.createdAt).toLocaleString()}
                          </span>
                          <span className="shrink-0 font-mono text-[9.5px] text-muted-foreground">
                            {run.versionLabel || '草稿快照'}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-border/65 bg-card/75 px-4 py-3 backdrop-blur">
        <div className="mx-auto w-full max-w-[960px]">
          <div className="mb-2 flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
            <span className="truncate">
              阶段 {stageIndex + 1}/{payload.stages.length} · {stage.name}
            </span>
            <span className="inline-flex shrink-0 items-center gap-1.5">
              <span
                className={cn(
                  'size-1 rounded-full',
                  payload.activeRun ? 'bg-sage' : 'bg-muted-foreground/40',
                )}
              />
              {payload.activeRun ? '当前运行已载入' : '尚未运行'}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={onPrevStage}
              disabled={isFirstStage || busy}
              className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl border border-border/65 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-30"
              aria-label="上一阶段"
              title="上一阶段"
            >
              <ArrowLeft className="size-4" />
            </button>
            <button
              type="button"
              onClick={() =>
                onRunStage({
                  globalPrompt: globalDraft,
                  systemInstruction: systemDraft,
                  stagePrompt: stageDraft,
                })
              }
              disabled={busy}
              className="inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-3 text-[12px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {busy ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="size-3.5" aria-hidden="true" />
              )}
              {busy ? '生成中…' : payload.activeRun ? '重新运行本阶段' : '运行本阶段'}
            </button>
            <button
              type="button"
              onClick={isLastStage ? onCreateStage : onNextStage}
              disabled={busy}
              className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl border border-border/65 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-30"
              aria-label={isLastStage ? '新增下一阶段' : '下一阶段'}
              title={isLastStage ? '新增下一阶段' : '下一阶段'}
            >
              {isLastStage ? <Plus className="size-4" /> : <ArrowRight className="size-4" />}
            </button>
            <button
              type="button"
              onClick={onResetRun}
              className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl border border-border/65 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              aria-label="清空当前运行"
              title="清空当前运行"
            >
              <RotateCcw className="size-4" />
            </button>
          </div>
        </div>
      </div>

      <ChapterSkeletonDialog
        open={skeletonOpen}
        chapter={chapter}
        onClose={() => setSkeletonOpen(false)}
        onSave={(patch) => onUpdateChapter(patch)}
      />
    </div>
  )
}

export const PromptWorkbenchPanel = memo(PromptWorkbenchPanelComponent)
