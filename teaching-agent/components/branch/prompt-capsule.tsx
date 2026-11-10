'use client'

import { useState } from 'react'
import { Loader2, Pencil, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

type PromptCapsuleProps = {
  prompt: string
  busy?: boolean
  onSave: (prompt: string) => void
}

export function PromptCapsule({ prompt, busy, onSave }: PromptCapsuleProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(prompt)

  const startEdit = () => {
    if (busy) return
    setDraft(prompt)
    setEditing(true)
  }

  return (
    <div
      className={cn(
        'border transition-all duration-300 ease-out',
        editing
          ? 'rounded-xl border-border/60 bg-card/60 p-3'
          : 'rounded-xl border-border/50 bg-card/40 px-3 py-2',
      )}
    >
      {editing ? (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const next = draft.trim()
            if (!next || busy) return
            onSave(next)
            setEditing(false)
          }}
          className="flex flex-col gap-2.5"
        >
          <label
            htmlFor="prompt-edit"
            className="flex items-center gap-1.5 text-[9.5px] font-medium tracking-[0.12em] text-primary uppercase"
          >
            <Sparkles className="size-3" aria-hidden="true" />
            编辑分支指令
          </label>
          <textarea
            id="prompt-edit"
            autoFocus
            rows={3}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="w-full resize-none rounded-xl border border-border/60 bg-background/60 px-3 py-2.5 text-[11.5px] leading-[1.8] text-foreground outline-none transition-colors focus:border-primary/45"
          />
          <div className="flex items-center justify-between gap-2">
            <p className="text-[9px] leading-4 text-muted-foreground">
              保存后会清空当前分支回答并重新生成。
            </p>
            <div className="flex justify-end gap-1.5">
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="h-7 rounded-lg px-2.5 text-[10.5px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={busy}
                className="inline-flex h-7 items-center gap-1.5 rounded-lg bg-primary px-2.5 text-[10.5px] font-medium text-primary-foreground transition-opacity disabled:opacity-40"
              >
                {busy ? <Loader2 className="size-3 animate-spin" /> : null}
                保存并重新生成
              </button>
            </div>
          </div>
        </form>
      ) : (
        <div className="flex items-center gap-2">
          <span className="grid size-6 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="size-3" aria-hidden="true" />
          </span>
          <p
            className="min-w-0 flex-1 truncate text-[11px] text-foreground/75"
            title={prompt}
          >
            <span className="mr-1.5 text-[9px] tracking-[0.1em] text-muted-foreground uppercase">
              分支指令
            </span>
            {`“${prompt}”`}
          </p>
          {busy ? (
            <span className="inline-flex shrink-0 items-center gap-1 pr-1 text-[9.5px] text-primary">
              <Loader2 className="size-3 animate-spin" aria-hidden="true" />
              生成中
            </span>
          ) : (
            <button
              type="button"
              onClick={startEdit}
              aria-label="编辑当前指令"
              className="inline-flex size-6 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-highlight-strong hover:text-primary"
            >
              <Pencil className="size-3" />
            </button>
          )}
        </div>
      )}
    </div>
  )
}
