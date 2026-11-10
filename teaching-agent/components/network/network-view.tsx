'use client'

import { cn } from '@/lib/utils'
import type { Neuron } from '@/lib/neurons'
import { NeuronCanvas } from './neuron-canvas'
import { ReviewDrawer } from './review-drawer'

type NetworkViewProps = {
  neurons: Neuron[]
  selectedId: string | null
  chapter: string
  onChapterChange: (chapter: string) => void
  onSelect: (id: string | null) => void
  onToggleSolved: (id: string) => void
  onRemove: (id: string) => void
  onBackToWorkspace: () => void
}

export function NetworkView({
  neurons,
  selectedId,
  chapter,
  onChapterChange,
  onSelect,
  onToggleSolved,
  onRemove,
  onBackToWorkspace,
}: NetworkViewProps) {
  const selected = neurons.find((n) => n.id === selectedId)
  const open = Boolean(selected)

  return (
    <div className="dark flex h-full bg-background text-foreground">
      <div
        className={cn(
          'min-w-0 transition-[width] duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]',
          open ? 'w-[65%]' : 'w-full',
        )}
      >
        <NeuronCanvas
          neurons={neurons}
          selectedId={selectedId}
          chapter={chapter}
          onChapterChange={onChapterChange}
          onSelect={onSelect}
        />
      </div>
      <div
        className={cn(
          'min-w-0 overflow-hidden transition-[width] duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]',
          open ? 'w-[35%]' : 'w-0',
        )}
        inert={!open}
        aria-hidden={!open}
      >
        <div className="h-full w-[35vw] min-w-[380px]">
          {selected && (
            <ReviewDrawer
              neuron={selected}
              onClose={() => onSelect(null)}
              onToggleSolved={() => onToggleSolved(selected.id)}
              onRemove={() => onRemove(selected.id)}
              onBackToWorkspace={onBackToWorkspace}
            />
          )}
        </div>
      </div>
    </div>
  )
}
