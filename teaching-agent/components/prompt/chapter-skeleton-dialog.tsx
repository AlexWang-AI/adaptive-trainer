'use client'

import { useEffect, useMemo, useState } from 'react'
import { FileText, X } from 'lucide-react'
import { buildKnowledgeSections } from '@/lib/knowledge-tree'
import type { PromptChapter } from '@/lib/prompt-types'

type ChapterSkeletonDialogProps = {
  open: boolean
  chapter: PromptChapter
  onClose: () => void
  onSave: (patch: { title: string; skeleton: string }) => void
}

export function ChapterSkeletonDialog({
  open,
  chapter,
  onClose,
  onSave,
}: ChapterSkeletonDialogProps) {
  const [title, setTitle] = useState(chapter.title)
  const [skeleton, setSkeleton] = useState(chapter.skeleton)

  useEffect(() => {
    if (!open) return
    setTitle(chapter.title)
    setSkeleton(chapter.skeleton)
  }, [chapter.id, chapter.skeleton, chapter.title, open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, open])

  const sectionCount = useMemo(
    () => buildKnowledgeSections(skeleton).length,
    [skeleton],
  )

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/25 p-6 backdrop-blur-[6px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="chapter-skeleton-title"
        className="warm-shadow flex max-h-[88vh] w-[min(760px,94vw)] flex-col overflow-hidden rounded-2xl border border-border/70 bg-card"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border/60 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 grid size-8 place-items-center rounded-xl border border-primary/20 bg-primary/8 text-primary">
              <FileText className="size-4" aria-hidden="true" />
            </span>
            <div>
              <h2
                id="chapter-skeleton-title"
                className="font-serif text-[17px] font-semibold tracking-tight"
              >
                章节骨架
              </h2>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                左侧知识树会自动解析这里的内容，也会进入 D · 动态上下文。
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label="关闭章节骨架"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <label className="block">
            <span className="text-[10.5px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
              章节标题
            </span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              autoFocus
              className="mt-1.5 h-10 w-full rounded-xl border border-border/70 bg-background/70 px-3 font-serif text-[15px] font-medium outline-none transition-colors focus:border-primary/45"
              placeholder="第 9 讲 一元函数积分学的计算"
            />
          </label>

          <label className="mt-4 block">
            <span className="flex items-center justify-between gap-2 text-[10.5px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
              知识骨架
              <span className="font-mono tracking-normal normal-case">
                {skeleton.length} 字 · {sectionCount} 个模块
              </span>
            </span>
            <textarea
              value={skeleton}
              onChange={(event) => setSkeleton(event.target.value)}
              rows={18}
              className="scrollbar-thin mt-1.5 w-full resize-y rounded-xl border border-border/70 bg-background/70 px-3.5 py-3 text-[13px] leading-[1.85] text-foreground outline-none transition-colors focus:border-primary/45"
              placeholder={'# 第 9 讲 一元函数积分学的计算\n\n## 一、考题与题型\n- 考题：...\n- 题型：...'}
            />
          </label>

          <p className="mt-2 rounded-lg bg-muted/50 px-3 py-2 text-[11px] leading-5 text-muted-foreground">
            用 <code className="rounded bg-card px-1 font-mono text-[10px]">##</code> 分模块，用{' '}
            <code className="rounded bg-card px-1 font-mono text-[10px]">-</code> 写知识点；缩进两个空格可以生成子知识点。
          </p>
        </div>

        <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border/60 px-5 py-3">
          <p className="text-[10.5px] text-muted-foreground">保存后右侧 D 层会同步更新。</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="h-8 rounded-lg px-3 text-[12px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => {
                onSave({ title: title.trim() || chapter.title, skeleton })
                onClose()
              }}
              className="h-8 rounded-lg bg-primary px-3.5 text-[12px] font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              保存章节
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
