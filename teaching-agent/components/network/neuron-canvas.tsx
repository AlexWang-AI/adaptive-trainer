'use client'

import { useRef, useState } from 'react'
import { LocateFixed, Minus, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CHAPTERS, STATUS_META, neuronTag, type Neuron } from '@/lib/neurons'

const VIEW_W = 1200
const VIEW_H = 820

function seeded(i: number, n: number) {
  const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453
  return Math.round((x - Math.floor(x)) * 1000) / 1000
}

const STARS = Array.from({ length: 110 }, (_, i) => ({
  x: Math.round(seeded(i, 1) * VIEW_W - VIEW_W / 2),
  y: Math.round(seeded(i, 2) * VIEW_H - VIEW_H / 2),
  r: 0.4 + seeded(i, 3) * 1.1,
  delay: `${(seeded(i, 4) * 5).toFixed(2)}s`,
}))

const CROSS_LINKS: [string, string][] = [
  ['n-implicit', 'n-lagrange'],
  ['n-hessian', 'n-lagrange'],
  ['n-diff', 'n-gradient'],
  ['n-constraint', 'n-implicit'],
  ['n-constraint', 'n-diff'],
]

function synapsePath(x: number, y: number) {
  const cx = x / 2 - y * 0.18
  const cy = y / 2 + x * 0.18
  return `M0 0 Q${cx} ${cy} ${x} ${y}`
}

type NeuronCanvasProps = {
  neurons: Neuron[]
  selectedId: string | null
  chapter: string
  onChapterChange: (chapter: string) => void
  onSelect: (id: string | null) => void
}

export function NeuronCanvas({ neurons, selectedId, chapter, onChapterChange, onSelect }: NeuronCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; y: number; px: number; py: number; moved: boolean } | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [dragging, setDragging] = useState(false)
  const [hoverId, setHoverId] = useState<string | null>(null)

  const byId = new Map(neurons.map((n) => [n.id, n]))
  const hovered = hoverId ? byId.get(hoverId) : undefined
  const inChapter = (n: Neuron) => chapter === CHAPTERS[0] || n.chapter === chapter

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest('[data-node]')) return
    e.currentTarget.setPointerCapture(e.pointerId)
    drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y, moved: false }
    setDragging(true)
  }

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current
    const svg = svgRef.current
    if (!d || !svg) return
    const k = Math.max(VIEW_W / svg.clientWidth, VIEW_H / svg.clientHeight)
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true
    setPan({ x: d.px + dx * k, y: d.py + dy * k })
  }

  const handlePointerUp = () => {
    if (drag.current && !drag.current.moved) onSelect(null)
    drag.current = null
    setDragging(false)
  }

  return (
    <div
      className="relative h-full w-full overflow-hidden"
      style={{
        backgroundColor: 'oklch(0.12 0.006 260)',
        backgroundImage:
          'radial-gradient(ellipse at 50% 45%, oklch(0.2 0.025 258 / 0.55), transparent 65%), radial-gradient(oklch(1 0 0 / 0.07) 1px, transparent 1px)',
        backgroundSize: '100% 100%, 26px 26px',
      }}
    >
      <svg
        ref={svgRef}
        viewBox={`${-VIEW_W / 2} ${-VIEW_H / 2} ${VIEW_W} ${VIEW_H}`}
        className={cn('h-full w-full touch-none select-none', dragging ? 'cursor-grabbing' : 'cursor-grab')}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        role="img"
        aria-label="认知神经元网络图谱"
      >
        <defs>
          <radialGradient id="gem-shine" cx="35%" cy="30%" r="70%">
            <stop offset="0%" stopColor="white" stopOpacity="0.55" />
            <stop offset="45%" stopColor="white" stopOpacity="0.08" />
            <stop offset="100%" stopColor="black" stopOpacity="0.25" />
          </radialGradient>
          <filter id="soft-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="8" />
          </filter>
        </defs>

        <g aria-hidden="true">
          {STARS.map((s, i) => (
            <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="white" className="animate-twinkle" style={{ animationDelay: s.delay }} />
          ))}
        </g>

        <g
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transition: dragging ? 'none' : 'transform 450ms cubic-bezier(0.32,0.72,0,1)',
          }}
        >
          <g aria-hidden="true">
            {CROSS_LINKS.map(([a, b]) => {
              const na = byId.get(a)
              const nb = byId.get(b)
              if (!na || !nb) return null
              const lit = [a, b].includes(hoverId ?? '') || [a, b].includes(selectedId ?? '')
              return (
                <line
                  key={`${a}-${b}`}
                  x1={na.x}
                  y1={na.y}
                  x2={nb.x}
                  y2={nb.y}
                  stroke="oklch(0.8 0.02 260)"
                  strokeOpacity={lit ? 0.3 : 0.08}
                  strokeDasharray="2 6"
                  style={{ transition: 'stroke-opacity 400ms' }}
                />
              )
            })}

            {neurons.map((n) => {
              const color = STATUS_META[n.status].color
              const lit = n.id === hoverId || n.id === selectedId
              const d = synapsePath(n.x, n.y)
              return (
                <g key={n.id} opacity={inChapter(n) ? 1 : 0.15} style={{ transition: 'opacity 400ms' }}>
                  <path
                    d={d}
                    fill="none"
                    stroke={color}
                    strokeOpacity={lit ? 0.55 : 0.2}
                    strokeWidth={lit ? 1.8 : 1.1}
                    style={{ transition: 'stroke 900ms, stroke-opacity 400ms, stroke-width 400ms' }}
                  />
                  <path
                    d={d}
                    fill="none"
                    stroke={color}
                    strokeWidth={lit ? 2.4 : 1.6}
                    strokeLinecap="round"
                    pathLength={100}
                    strokeDasharray="4 96"
                    className="animate-synapse"
                    style={{ animationDuration: lit ? '1.6s' : '3.6s', transition: 'stroke 900ms' }}
                  />
                </g>
              )
            })}
          </g>

          <g aria-hidden="true">
            <circle r={62} fill="oklch(0.6 0.13 256)" opacity={0.12} className="animate-halo" />
            <circle r={40} fill="oklch(0.6 0.13 256)" opacity={0.35} filter="url(#soft-glow)" />
            <circle r={28} fill="oklch(0.42 0.12 258)" />
            <circle r={28} fill="url(#gem-shine)" />
            <circle r={28} fill="none" stroke="oklch(0.75 0.1 256)" strokeOpacity={0.5} />
            <text y={52} textAnchor="middle" fontSize={14} fontWeight={600} fill="oklch(0.94 0.01 260)">
              高等数学 · 多元函数微积分
            </text>
            <text y={70} textAnchor="middle" fontSize={10.5} fill="oklch(0.65 0.02 260)">
              {`当前攻坚章节 · ${neurons.length} 个神经元`}
            </text>
          </g>

          {neurons.map((n) => {
            const color = STATUS_META[n.status].color
            const lit = n.id === hoverId || n.id === selectedId
            return (
              <g
                key={n.id}
                data-node
                transform={`translate(${n.x} ${n.y})`}
                opacity={inChapter(n) ? 1 : 0.2}
                role="button"
                tabIndex={0}
                aria-label={`${n.label}，${neuronTag(n)}，点击进入复盘`}
                aria-pressed={n.id === selectedId}
                className="cursor-pointer outline-none"
                style={{ transition: 'opacity 400ms' }}
                onClick={() => onSelect(n.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelect(n.id)
                  }
                }}
                onMouseEnter={() => setHoverId(n.id)}
                onMouseLeave={() => setHoverId(null)}
                onFocus={() => setHoverId(n.id)}
                onBlur={() => setHoverId(null)}
              >
                <g
                  style={{
                    transform: `scale(${lit ? 1.18 : 1})`,
                    transformBox: 'fill-box',
                    transformOrigin: 'center',
                    transition: 'transform 450ms cubic-bezier(0.34,1.56,0.64,1)',
                  }}
                >
                  <circle
                    r={34}
                    fill={color}
                    opacity={lit ? 0.24 : 0.09}
                    className={lit ? 'animate-halo' : undefined}
                    style={{ transition: 'fill 900ms, opacity 400ms' }}
                  />
                  <circle r={20} fill={color} opacity={0.3} filter="url(#soft-glow)" style={{ transition: 'fill 900ms' }} />
                  <circle r={13} fill={color} style={{ transition: 'fill 900ms' }} />
                  <circle r={13} fill="url(#gem-shine)" />
                  <circle r={13} fill="none" stroke="white" strokeOpacity={lit ? 0.5 : 0.18} />
                </g>
                <text y={36} textAnchor="middle" fontSize={12.5} fontWeight={500} fill="oklch(0.92 0.006 260)">
                  {n.label}
                </text>
                <text y={53} textAnchor="middle" fontSize={10.5} fill={color} opacity={0.85} style={{ transition: 'fill 900ms' }}>
                  {neuronTag(n)}
                </text>
              </g>
            )
          })}

          {hovered && (
            <g transform={`translate(${hovered.x} ${hovered.y - 78})`} pointerEvents="none" className="animate-in fade-in duration-200">
              <rect x={-92} y={-22} width={184} height={46} rx={10} fill="oklch(0.2 0.006 260 / 0.92)" stroke="oklch(1 0 0 / 0.12)" />
              <text y={-3} textAnchor="middle" fontSize={11} fill="oklch(0.92 0.006 260)">
                {`真题频次 · ${hovered.frequency}`}
              </text>
              <text y={14} textAnchor="middle" fontSize={10} fill="oklch(0.65 0.015 260)">
                {`录入时间 · ${hovered.recordedAt}`}
              </text>
            </g>
          )}
        </g>
      </svg>

      <div className="absolute top-4 right-4 flex items-center gap-2">
        <label htmlFor="chapter-filter" className="sr-only">
          章节筛选
        </label>
        <select
          id="chapter-filter"
          value={chapter}
          onChange={(e) => onChapterChange(e.target.value)}
          className="h-8 rounded-full border border-white/10 bg-white/[0.06] px-3 text-xs text-foreground/85 backdrop-blur-md outline-none hover:bg-white/10 focus-visible:border-primary/60"
        >
          {CHAPTERS.map((c) => (
            <option key={c} value={c} className="bg-popover text-popover-foreground">
              {c}
            </option>
          ))}
        </select>
        <div className="flex items-center rounded-full border border-white/10 bg-white/[0.06] p-0.5 backdrop-blur-md">
          {[
            { label: '放大', icon: Plus, onClick: () => setZoom((z) => Math.min(2, +(z + 0.2).toFixed(2))) },
            { label: '缩小', icon: Minus, onClick: () => setZoom((z) => Math.max(0.5, +(z - 0.2).toFixed(2))) },
            {
              label: '居中复位',
              icon: LocateFixed,
              onClick: () => {
                setZoom(1)
                setPan({ x: 0, y: 0 })
              },
            },
          ].map(({ label, icon: Icon, onClick }) => (
            <button
              key={label}
              type="button"
              onClick={onClick}
              aria-label={label}
              title={label}
              className="inline-flex size-7 items-center justify-center rounded-full text-foreground/70 transition-colors hover:bg-white/10 hover:text-foreground"
            >
              <Icon className="size-3.5" />
            </button>
          ))}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-4 left-4 flex flex-col gap-2">
        <ul className="flex items-center gap-3 text-[11px] text-foreground/60">
          {(['critical', 'warning', 'solved'] as const).map((s) => (
            <li key={s} className="flex items-center gap-1.5">
              <span
                className="size-2 rounded-full"
                style={{ backgroundColor: STATUS_META[s].color, boxShadow: `0 0 8px ${STATUS_META[s].color}` }}
                aria-hidden="true"
              />
              {STATUS_META[s].label}
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-foreground/40">{`拖拽平移画布 · 点击神经元进入复盘 · 缩放 ${Math.round(zoom * 100)}%`}</p>
      </div>
    </div>
  )
}
