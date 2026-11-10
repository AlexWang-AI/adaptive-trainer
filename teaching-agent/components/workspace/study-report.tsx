'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, BookOpenCheck, Loader2, Radar, RefreshCw, TrendingUp, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getJSON } from '@/lib/client-api'
import { useKnowledge } from './knowledge-provider'

type ChapterScore = { chapter: string; name: string; mastery: number; covered: number; weight_sum: number }
type HeatCell = {
  kp: string
  name: string
  chapter: string
  exam_weight: number
  mastery: number
  unknown: boolean
  mastered: boolean
}
type HistoryPoint = { ts: number; overall: number; reason: string }
type DueItem = { kp_id: string; name?: string; stage: number; streak: number; overdue_days: number }

type Analytics = {
  student_id: string
  overall: number
  chapters: ChapterScore[]
  heatmap: HeatCell[]
  history: HistoryPoint[]
  due: { count: number; items: DueItem[] }
  coverage: { practiced: number; total: number; mastered: number }
}

type Props = { open: boolean; onClose: () => void }

function masteryColor(m: number, unknown: boolean) {
  if (unknown) return 'bg-muted/60 text-muted-foreground/70'
  if (m >= 0.8) return 'bg-emerald-500/80 text-white'
  if (m >= 0.6) return 'bg-emerald-400/60 text-emerald-950'
  if (m >= 0.4) return 'bg-amber-400/70 text-amber-950'
  if (m >= 0.2) return 'bg-orange-400/70 text-orange-950'
  return 'bg-rose-400/70 text-rose-950'
}

/** 能力雷达：六边形（按章节加权掌握度） */
function RadarChart({ chapters }: { chapters: ChapterScore[] }) {
  const items = chapters.slice(0, 6)
  const size = 200
  const center = size / 2
  const radius = size / 2 - 26
  const points = items.map((item, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(items.length, 1) - Math.PI / 2
    const r = radius * Math.max(0.03, item.mastery)
    return [center + r * Math.cos(angle), center + r * Math.sin(angle)]
  })
  const rings = [0.25, 0.5, 0.75, 1].map((scale) =>
    items
      .map((_, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(items.length, 1) - Math.PI / 2
        return `${center + radius * scale * Math.cos(angle)},${center + radius * scale * Math.sin(angle)}`
      })
      .join(' '),
  )
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="h-[200px] w-[200px]">
      {rings.map((ring, index) => (
        <polygon key={index} points={ring} fill="none" stroke="currentColor" strokeOpacity={0.12} />
      ))}
      {items.map((item, index) => {
        const angle = (Math.PI * 2 * index) / Math.max(items.length, 1) - Math.PI / 2
        return (
          <line
            key={item.chapter}
            x1={center}
            y1={center}
            x2={center + radius * Math.cos(angle)}
            y2={center + radius * Math.sin(angle)}
            stroke="currentColor"
            strokeOpacity={0.1}
          />
        )
      })}
      <polygon points={points.map((p) => p.join(',')).join(' ')} fill="rgb(194 65 12 / 0.25)" stroke="#c2410c" strokeWidth={1.6} />
      {points.map((p, index) => (
        <circle key={index} cx={p[0]} cy={p[1]} r={2.8} fill="#c2410c" />
      ))}
    </svg>
  )
}

/** 提分曲线：overall 历史折线 */
function TrendLine({ history }: { history: HistoryPoint[] }) {
  if (history.length < 2) {
    return <p className="text-[11.5px] text-muted-foreground">再练 1 轮就能看到曲线（当前 {history.length} 个记录点）。</p>
  }
  const width = 260
  const height = 64
  const values = history.map((h) => h.overall)
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 0.05)
  const pts = history.map((h, i) => {
    const x = (i / (history.length - 1)) * width
    const y = height - ((h.overall - min) / (max - min || 1)) * height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-16 w-full">
      <polyline points={pts.join(' ')} fill="none" stroke="#c2410c" strokeWidth={2} strokeLinejoin="round" />
      <polygon points={`0,${height} ${pts.join(' ')} ${width},${height}`} fill="rgb(194 65 12 / 0.12)" />
    </svg>
  )
}


const cleanChapterName = (name: string) =>
  name.replace(/^第[\d\-–]+讲\s*/, '').replace(/^第\d+讲\s*/, '')

export function StudyReport({ open, onClose }: Props) {
  const { tree, requestStart } = useKnowledge()
  const [data, setData] = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await getJSON<Analytics>('/api/analytics'))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  // 雷达只放 6 个轴：按考频权重降序取，避免字母序把微分方程/级数挤掉（红队 P1-6）
  const radarChapters = useMemo(() => {
    if (!data) return []
    return [...data.chapters].sort((a, b) => b.weight_sum - a.weight_sum).slice(0, 6)
  }, [data])

  const hotKps = useMemo(() => {
    if (!data) return []
    return [...data.heatmap]
      .filter((cell) => cell.exam_weight >= 4)
      .sort((a, b) => a.mastery - b.mastery || b.exam_weight - a.exam_weight)
      .slice(0, 18)
  }, [data])

  const startReview = useCallback(
    (kpId: string) => {
      const kp =
        tree?.chapters.flatMap((c) => c.kps).find((item) => item.id === kpId) ?? null
      if (kp) requestStart(kp)
      onClose()
    },
    [onClose, requestStart, tree],
  )

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/25" onClick={onClose}>
      <div
        className="scrollbar-thin h-full w-full max-w-[440px] overflow-y-auto border-l border-border/70 bg-background shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-border/60 bg-background/95 px-4 py-3 backdrop-blur">
          <Activity className="size-4 text-primary" />
          <span className="text-[14px] font-medium">学习报告</span>
          <button type="button" onClick={() => void load()} className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted/50">
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          </button>
          <button type="button" onClick={onClose} className="rounded p-1 text-muted-foreground hover:bg-muted/50">
            <X className="size-3.5" />
          </button>
        </header>

        {!data && loading && (
          <div className="flex items-center gap-2 px-4 py-6 text-[12px] text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> 正在汇总…
          </div>
        )}
        {error && <p className="px-4 py-3 text-[12px] text-rose-600">{error}</p>}

        {data && (
          <div className="space-y-4 px-4 py-4">
            <section className="rounded-xl border border-border/60 bg-card/60 p-3.5">
              <div className="flex items-end gap-3">
                <div>
                  <div className="text-[10.5px] text-muted-foreground">当前能力分（加权掌握度）</div>
                  <div className="font-serif text-[30px] leading-none">{Math.round(data.overall * 100)}</div>
                </div>
                <div className="mb-1 text-[11px] leading-5 text-muted-foreground">
                  已练 {data.coverage.practiced}/{data.coverage.total} 个知识点
                  <br />
                  已通关 {data.coverage.mastered} 个
                </div>
              </div>
              <div className="mt-3">
                <div className="mb-1 flex items-center gap-1 text-[10.5px] text-muted-foreground">
                  <TrendingUp className="size-3" /> 提分曲线
                </div>
                <TrendLine history={data.history} />
              </div>
            </section>

            <section className="rounded-xl border border-border/60 bg-card/60 p-3.5">
              <div className="mb-1 flex items-center gap-1 text-[10.5px] text-muted-foreground">
                <Radar className="size-3" /> 能力雷达（按考频加权）
              </div>
              <div className="flex items-center gap-2">
                <RadarChart chapters={radarChapters} />
                <ul className="min-w-0 flex-1 space-y-1 text-[11px]">
                  {radarChapters.map((ch) => (
                    <li key={ch.chapter} className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-foreground/75">{cleanChapterName(ch.name)}</span>
                      <span className="shrink-0 tabular-nums text-muted-foreground">{Math.round(ch.mastery * 100)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            <section className="rounded-xl border border-border/60 bg-card/60 p-3.5">
              <div className="mb-2 flex items-center gap-1 text-[10.5px] text-muted-foreground">
                <BookOpenCheck className="size-3" /> 高频考点热力图（考频≥4，越红越弱）
              </div>
              <div className="grid grid-cols-3 gap-1.5">
                {hotKps.map((cell) => (
                  <button
                    key={cell.kp}
                    type="button"
                    title={`${cell.name} ｜ 考频 ${cell.exam_weight} ｜ 掌握 ${Math.round(cell.mastery * 100)}`}
                    onClick={() => startReview(cell.kp)}
                    className={cn(
                      'truncate rounded-md px-1.5 py-1 text-left text-[10px] transition-opacity hover:opacity-80',
                      masteryColor(cell.mastery, cell.unknown),
                    )}
                  >
                    {cell.name}
                  </button>
                ))}
              </div>
            </section>

            <section className="rounded-xl border border-border/60 bg-card/60 p-3.5">
              <div className="mb-2 flex items-center gap-1 text-[10.5px] text-muted-foreground">
                <RefreshCw className="size-3" /> 待复习（{data.due.count}）
              </div>
              {data.due.count === 0 ? (
                <p className="text-[11.5px] text-muted-foreground">今天没有到期的复习。答错的知识点会按 1/3/7 天自动排进队列。</p>
              ) : (
                <ul className="space-y-1.5">
                  {data.due.items.map((item) => (
                    <li key={item.kp_id} className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => startReview(item.kp_id)}
                        className="min-w-0 flex-1 truncate rounded-md border border-primary/30 bg-primary/[0.06] px-2 py-1 text-left text-[11.5px] text-primary hover:bg-primary/10"
                      >
                        {item.name ?? item.kp_id}
                      </button>
                      <span className="shrink-0 text-[10px] text-muted-foreground">
                        第 {item.stage + 1} 档
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <p className="text-[10px] leading-4 text-muted-foreground">
              口径：掌握度 = 平滑答对率 (正确+1)/(作答+2) × 遗忘衰减（半衰期 14 天）；没练过的知识点直接记 0，不按 50% 起算；章节分按考频加权。
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
