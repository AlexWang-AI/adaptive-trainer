'use client'

import { BookOpen, Layers3, Sparkles } from 'lucide-react'

const TREE = [
  {
    title: '高等数学',
    items: ['第9讲 · 一元函数积分学', '第10讲 · 微分方程', '第11讲 · 多元函数'],
  },
  {
    title: '线性代数',
    items: ['行列式与矩阵', '向量组与秩', '特征值与二次型'],
  },
  {
    title: '概率统计',
    items: ['随机变量', '数字特征', '参数估计'],
  },
]

export function DecorationSidebar() {
  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-sidebar-border/60 bg-sidebar/35">
      <header className="shrink-0 border-b border-border/55 px-4 py-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[9px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
            Knowledge Tree
          </span>
          <span className="rounded-full border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[8.5px] text-muted-foreground">
            装饰
          </span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary">
            <Layers3 className="size-3.5" />
          </span>
          <div>
            <h2 className="font-serif text-[16px] font-semibold tracking-tight">知识树</h2>
            <p className="text-[9.5px] text-muted-foreground">仅作视觉导航，不参与 Agent 对话</p>
          </div>
        </div>
      </header>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <div className="space-y-4">
          {TREE.map((group) => (
            <div key={group.title}>
              <div className="flex items-center gap-2 px-1 text-[10px] font-semibold tracking-wide text-foreground/75">
                <BookOpen className="size-3 text-primary/70" />
                {group.title}
              </div>
              <div className="mt-1.5 space-y-0.5 border-l border-border/55 pl-3">
                {group.items.map((item) => (
                  <div
                    key={item}
                    className="rounded-md px-2 py-1 text-[10.5px] leading-5 text-muted-foreground/80"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-lg border border-dashed border-border/55 bg-card/40 px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-[9px] text-primary/80">
            <Sparkles className="size-3" />
            已解耦
          </div>
          <p className="mt-1 text-[9.5px] leading-5 text-muted-foreground">
            这一栏不再驱动章节/阶段/提示词；只保留工作台的视觉骨架。
          </p>
        </div>
      </div>

      <footer className="shrink-0 border-t border-border/50 px-4 py-3 text-[9px] text-muted-foreground/70">
        MathNeuron · Teaching Shell
      </footer>
    </aside>
  )
}
