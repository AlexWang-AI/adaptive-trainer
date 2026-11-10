'use client'

import { useEffect } from 'react'
import { Highlighter, Loader2, Sparkles, Wand2, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const PRESETS = [
  '只讲几何直觉，不要展开计算。',
  '把这段拆成第一步、第二步、第三步，每步写清为什么。',
  '指出最容易错的 3 个地方，并给出自检方法。',
  '出 3 道同类型考研例题，先题目后答案。',
]

type LassoPromptDialogProps = {
  open: boolean
  loading: boolean
  error: string | null
  anchorText: string
  prompt: string
  onAnchorChange: (value: string) => void
  onPromptChange: (value: string) => void
  onCancel: () => void
  onGenerate: () => void
}

export function LassoPromptDialog({
  open,
  loading,
  error,
  anchorText,
  prompt,
  onAnchorChange,
  onPromptChange,
  onCancel,
  onGenerate,
}: LassoPromptDialogProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  const canGenerate = Boolean(anchorText.trim() && prompt.trim())

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4 backdrop-blur-[6px] dark:bg-black/55"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="圈选拆解提示词"
        className="warm-shadow flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border/70 bg-card"
      >
        <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 inline-flex size-8 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
              <Highlighter className="size-4" aria-hidden="true" />
            </span>
            <div>
              <p className="text-[9px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
                Lasso · 灵巧笔圈选
              </p>
              <h2 className="mt-0.5 font-serif text-[16px] font-semibold tracking-tight text-foreground">
                确认圈选内容与分支提示词
              </h2>
              <p className="mt-0.5 text-[10.5px] leading-4 text-muted-foreground">
                先确认圈选到的内容，再决定右侧分支按什么提示词解答。
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="关闭圈选对话框"
            className="inline-flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-4">
            <section>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label
                  htmlFor="lasso-anchor"
                  className="flex items-center gap-1.5 text-[10.5px] font-semibold text-foreground"
                >
                  圈选内容
                  <span className="rounded-md bg-muted px-1.5 py-0.5 text-[9px] font-normal text-muted-foreground">
                    可修改
                  </span>
                </label>
                {loading ? (
                  <span className="inline-flex items-center gap-1 text-[9.5px] text-primary">
                    <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                    正在识别…
                  </span>
                ) : (
                  <span className="font-mono text-[9px] text-muted-foreground">
                    {anchorText.length} 字符
                  </span>
                )}
              </div>
              <textarea
                id="lasso-anchor"
                value={anchorText}
                onChange={(event) => onAnchorChange(event.target.value)}
                rows={5}
                placeholder={
                  loading
                    ? '正在识别圈选内容……也可以直接在这里手动输入。'
                    : '识别结果会出现在这里；如果识别有误，直接修改即可。'
                }
                className="scrollbar-thin w-full resize-y rounded-xl border border-border/60 bg-background/60 px-3 py-2.5 text-[11.5px] leading-[1.8] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/45"
              />
              {error && (
                <p className="mt-1.5 rounded-lg border border-destructive/30 bg-destructive/[0.05] px-2.5 py-1.5 text-[9.5px] leading-4 text-destructive">
                  {error}
                </p>
              )}
            </section>

            <section>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label
                  htmlFor="lasso-prompt"
                  className="flex items-center gap-1.5 text-[10.5px] font-semibold text-foreground"
                >
                  <Sparkles className="size-3.5 text-primary" aria-hidden="true" />
                  分支提示词
                </label>
                <button
                  type="button"
                  onClick={() =>
                    onPromptChange(
                      '把这段内容讲透：先说明它在原推导中的作用，再逐步拆解每一步的动机和依据，指出最容易错的地方，最后给出 3 道同类型考研例题及标准答案。',
                    )
                  }
                  className="text-[9.5px] text-muted-foreground transition-colors hover:text-foreground"
                >
                  恢复默认
                </button>
              </div>
              <p className="mb-1.5 text-[9.5px] leading-4 text-muted-foreground">
                分支是独立分析：只发送「圈选内容 + 这段提示词」，不继承主对话的 G / S / P。生成后仍可在分支顶部修改并重新生成。
              </p>
              <textarea
                id="lasso-prompt"
                value={prompt}
                onChange={(event) => onPromptChange(event.target.value)}
                rows={5}
                className="scrollbar-thin w-full resize-y rounded-xl border border-border/60 bg-background/60 px-3 py-2.5 text-[11.5px] leading-[1.8] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/45"
              />
              <div className="mt-1.5 flex flex-wrap gap-1">
                {PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() =>
                      onPromptChange(
                        prompt.trim()
                          ? `${prompt.trim()}\n\n额外要求：${preset}`
                          : `额外要求：${preset}`,
                      )
                    }
                    className="rounded-full border border-border/60 px-2 py-0.5 text-[9px] text-muted-foreground transition-colors hover:border-primary/35 hover:text-primary"
                  >
                    + {preset.replace(/。$/, '')}
                  </button>
                ))}
              </div>
            </section>
          </div>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 px-5 py-3">
          <p className="text-[9px] leading-4 text-muted-foreground">
            生成后可在「分支拆解」里继续改提示词、追问或重新生成。
          </p>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={onCancel}
              className="h-8 rounded-lg px-3 text-[10.5px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              取消
            </button>
            <button
              type="button"
              onClick={onGenerate}
              disabled={!canGenerate}
              className={cn(
                'inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-[10.5px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40',
              )}
            >
              <Wand2 className="size-3.5" aria-hidden="true" />
              按此提示词生成分支
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}
