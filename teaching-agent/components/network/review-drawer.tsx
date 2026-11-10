'use client'

import { ArrowUpRight, Check, RotateCcw, Trash2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Tex } from '@/components/math/tex'
import { MathText } from '@/components/math/math-text'
import { STATUS_META, neuronTag, type Neuron } from '@/lib/neurons'

type ReviewDrawerProps = {
  neuron: Neuron
  onClose: () => void
  onToggleSolved: () => void
  onRemove: () => void
  onBackToWorkspace: () => void
}

function Module({ index, title, children }: { index: string; title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="flex items-center gap-2 text-[12px] font-semibold text-foreground">
        <span className="font-mono text-[10.5px] text-muted-foreground">{index}</span>
        {title}
      </h3>
      {children}
    </section>
  )
}

export function ReviewDrawer({ neuron, onClose, onToggleSolved, onRemove, onBackToWorkspace }: ReviewDrawerProps) {
  const solved = neuron.status === 'solved'
  const color = STATUS_META[neuron.status].color

  return (
    <aside
      aria-label="复盘档案"
      className="flex h-full flex-col border-l border-white/10 bg-[oklch(0.16_0.005_260/0.82)] text-foreground backdrop-blur-xl"
    >
      <header className="flex shrink-0 flex-col gap-3 border-b border-border px-5 pt-4 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1.5">
            <span
              className="inline-flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors duration-700"
              style={{ color, backgroundColor: `color-mix(in oklch, ${color} 14%, transparent)` }}
            >
              <span className="size-1.5 rounded-full" style={{ backgroundColor: color }} aria-hidden="true" />
              {solved ? '已攻克' : STATUS_META[neuron.status].label}
            </span>
            <h2 className="text-[15px] font-semibold text-balance">{neuron.label}</h2>
            <p className="text-[11.5px] text-muted-foreground">{neuronTag(neuron)}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭复盘档案"
            className="inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleSolved}
            className={cn(
              'inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg text-[12.5px] font-medium transition-all duration-300',
              solved
                ? 'border border-border text-muted-foreground hover:bg-accent hover:text-foreground'
                : 'bg-[oklch(0.75_0.08_165)] text-[oklch(0.18_0.02_165)] shadow-[0_0_20px_oklch(0.75_0.08_165/0.35)] hover:shadow-[0_0_28px_oklch(0.75_0.08_165/0.55)]',
            )}
          >
            {solved ? <RotateCcw className="size-3.5" aria-hidden="true" /> : <Check className="size-3.5" aria-hidden="true" />}
            {solved ? '重新标记为待复盘' : '标记为已攻克'}
          </button>
          <button
            type="button"
            onClick={onRemove}
            aria-label="移除漏洞"
            title="移除漏洞"
            className="inline-flex size-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-[oklch(0.67_0.1_12/0.5)] hover:text-[oklch(0.75_0.1_12)]"
          >
            <Trash2 className="size-3.5" />
          </button>
        </div>
      </header>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-6 px-5 py-5">
          <Module index="01" title="真题盲区切片">
            <div className="rounded-lg border border-border bg-card/60 p-3.5">
              <p className="mb-2 text-[11px] text-muted-foreground">{neuron.source}</p>
              <p className="text-[13px] leading-relaxed text-foreground/90">
                <MathText>{neuron.question}</MathText>
              </p>
              <div className="relative mt-3 rounded-md bg-highlight px-2 py-0.5 ring-1 ring-primary/30">
                <span className="absolute -top-2 left-2 rounded bg-background px-1 text-[10px] text-primary">画笔圈注</span>
                <Tex display className="text-[13px]">
                  {neuron.formula}
                </Tex>
              </div>
            </div>
          </Module>

          <Module index="02" title="你当初的原始自述">
            <blockquote className="rounded-lg border-l-2 border-muted-foreground/40 bg-muted px-4 py-3 text-[13px] leading-relaxed text-foreground/80 italic">
              {neuron.transcript}
            </blockquote>
          </Module>

          <Module index="03" title="AI 认知偏差剖析">
            <div className="flex flex-col gap-2 text-[13px] leading-relaxed text-foreground/90">
              <p>
                <MathText>{neuron.purified}</MathText>
              </p>
              <p className="rounded-md bg-primary/[0.08] px-3 py-2 text-[12.5px] text-foreground/85">
                <span className="mr-1 font-medium text-primary">段位评估</span>
                {neuron.level}
              </p>
            </div>
          </Module>

          <Module index="04" title="即时微型变式重测">
            <div className="rounded-lg border border-border p-3.5 text-[13px] leading-relaxed">
              <p className="mb-1 text-[11px] text-muted-foreground">1 分钟口算 · 考前过脑检测</p>
              <p className="text-foreground/90">
                <MathText>{neuron.variant.question}</MathText>
              </p>
              <details className="group mt-2.5 border-t border-border pt-2.5">
                <summary className="cursor-pointer list-none text-[12px] font-medium text-primary marker:hidden">
                  <span className="group-open:hidden">揭晓答案</span>
                  <span className="hidden group-open:inline">收起答案</span>
                </summary>
                <p className="mt-2 text-foreground/85">
                  <MathText>{neuron.variant.answer}</MathText>
                </p>
              </details>
            </div>
          </Module>
        </div>
      </div>

      <footer className="shrink-0 border-t border-border px-5 py-3">
        <button
          type="button"
          onClick={onBackToWorkspace}
          className="inline-flex items-center gap-1 text-[12.5px] text-muted-foreground transition-colors hover:text-primary"
        >
          返回工作台查看完整推导步骤
          <ArrowUpRight className="size-3.5" aria-hidden="true" />
        </button>
      </footer>
    </aside>
  )
}
