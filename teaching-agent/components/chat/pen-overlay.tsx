'use client'

import { useEffect, useRef, useState } from 'react'
import html2canvas from 'html2canvas-pro'
import { cn } from '@/lib/utils'

type Rect = { x: number; y: number; w: number; h: number }

type PenOverlayProps = {
  active: boolean
  busy?: boolean
  onCapture: (image: string) => void
  onError: (message: string) => void
  onWheel?: (deltaY: number) => void
}

export function PenOverlay({ active, busy, onCapture, onError, onWheel }: PenOverlayProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const startRef = useRef<{ x: number; y: number } | null>(null)
  const rectRef = useRef<Rect | null>(null)
  const [rect, setRectState] = useState<Rect | null>(null)
  const [capturing, setCapturing] = useState(false)
  const [working, setWorking] = useState(false)

  const setRect = (value: Rect | null) => {
    rectRef.current = value
    setRectState(value)
  }

  useEffect(() => {
    if (!active) {
      startRef.current = null
      setRect(null)
    }
  }, [active])

  const point = (event: React.PointerEvent) => {
    const element = overlayRef.current
    if (!element) return { x: 0, y: 0 }
    const box = element.getBoundingClientRect()
    return {
      x: Math.min(Math.max(event.clientX - box.left, 0), box.width),
      y: Math.min(Math.max(event.clientY - box.top, 0), box.height),
    }
  }

  const handleDown = (event: React.PointerEvent) => {
    if (!active || working || busy) return
    event.preventDefault()
    const pointNow = point(event)
    startRef.current = pointNow
    setRect({ x: pointNow.x, y: pointNow.y, w: 0, h: 0 })
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // synthetic pointer events may not support capture
    }
  }

  const handleMove = (event: React.PointerEvent) => {
    if (!startRef.current) return
    const pointNow = point(event)
    const start = startRef.current
    setRect({
      x: Math.min(start.x, pointNow.x),
      y: Math.min(start.y, pointNow.y),
      w: Math.abs(pointNow.x - start.x),
      h: Math.abs(pointNow.y - start.y),
    })
  }

  const handleUp = async (event: React.PointerEvent) => {
    if (!startRef.current) return
    try {
      event.currentTarget.releasePointerCapture(event.pointerId)
    } catch {
      // pointer already released
    }
    const current = rectRef.current
    startRef.current = null
    if (!current || current.w < 12 || current.h < 12) {
      setRect(null)
      return
    }

    setWorking(true)
    setCapturing(true)
    setRect(null)
    try {
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      )
      const box = overlayRef.current?.getBoundingClientRect()
      if (!box) throw new Error('找不到圈选区域')
      const canvas = await html2canvas(document.body, {
        x: box.left + current.x,
        y: box.top + current.y,
        width: current.w,
        height: current.h,
        scale: 2,
        backgroundColor: getComputedStyle(document.body).backgroundColor || '#16171a',
        logging: false,
        useCORS: true,
      })
      onCapture(canvas.toDataURL('image/jpeg', 0.92))
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error))
    } finally {
      setCapturing(false)
      setWorking(false)
    }
  }

  return (
    <div
      ref={overlayRef}
      className={cn(
        'absolute inset-0 z-30 select-none',
        active ? 'cursor-crosshair' : 'pointer-events-none',
        capturing && 'opacity-0',
      )}
      onPointerDown={handleDown}
      onPointerMove={handleMove}
      onPointerUp={handleUp}
      onPointerCancel={() => {
        startRef.current = null
        setRect(null)
      }}
      onWheel={(event) => {
        if (!onWheel) return
        event.preventDefault()
        onWheel(event.deltaY)
      }}
    >
      {active && !capturing && !busy && (
        <div className="pointer-events-none absolute top-3 left-1/2 -translate-x-1/2 rounded-full border border-primary/40 bg-card/95 px-3 py-1 text-[11px] font-medium text-primary shadow-sm backdrop-blur">
          拖动圈选不懂的内容 · Esc 退出
        </div>
      )}
      {rect && (
        <div
          className="pointer-events-none absolute rounded-sm border-2 border-primary bg-primary/15 shadow-[0_0_0_9999px_oklch(0_0_0/0.22)]"
          style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}
        />
      )}
      {working && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="rounded-full bg-card/95 px-4 py-2 text-xs text-foreground shadow-lg">
            正在截取圈选区域…
          </span>
        </div>
      )}
    </div>
  )
}
