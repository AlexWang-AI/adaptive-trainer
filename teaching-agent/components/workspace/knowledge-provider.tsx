'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { getJSON, postJSON } from '@/lib/client-api'
import type { KnowledgeTree, KpNode } from '@/lib/quiz-types'

type KnowledgeContextValue = {
  tree: KnowledgeTree | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  markMastered: (kpId: string, score?: number) => Promise<KnowledgeTree | null>
  pendingStart: StartRequest | null
  /** focus = 知识点内部的某个子项（例如「七种未定式」里的「0/0 型」），为空表示讲整个知识点 */
  requestStart: (kp: KpNode, focus?: string) => void
  clearPendingStart: () => void
  activeKpId: string | null
  setActiveKpId: (id: string | null) => void
}

export type StartRequest = { kp: KpNode; focus: string }

const KnowledgeContext = createContext<KnowledgeContextValue | null>(null)

export function KnowledgeProvider({ children }: { children: React.ReactNode }) {
  const [tree, setTree] = useState<KnowledgeTree | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingStart, setPendingStart] = useState<StartRequest | null>(null)
  const [activeKpId, setActiveKpId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getJSON<KnowledgeTree>('/api/knowledge?student_id=local-user')
      setTree(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    // 预热流式路由 + 后端讲练图，减少第一次点击的等待
    void fetch('/api/teach_proxy/stream', { method: 'GET', cache: 'no-store' }).catch(() => {})
  }, [refresh])

  const markMastered = useCallback(async (kpId: string, score?: number) => {
    try {
      const data = await postJSON<KnowledgeTree>('/api/knowledge', {
        kp_id: kpId,
        student_id: 'local-user',
        score: score ?? null,
      })
      if (data && Array.isArray(data.chapters)) setTree(data)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      return null
    }
  }, [])

  const requestStart = useCallback((kp: KpNode, focus = '') => {
    setActiveKpId(kp.id)
    setPendingStart({ kp, focus })
  }, [])

  const clearPendingStart = useCallback(() => setPendingStart(null), [])

  const value = useMemo<KnowledgeContextValue>(
    () => ({
      tree,
      loading,
      error,
      refresh,
      markMastered,
      pendingStart,
      requestStart,
      clearPendingStart,
      activeKpId,
      setActiveKpId,
    }),
    [tree, loading, error, refresh, markMastered, pendingStart, requestStart, clearPendingStart, activeKpId],
  )

  return <KnowledgeContext.Provider value={value}>{children}</KnowledgeContext.Provider>
}

export function useKnowledge() {
  const ctx = useContext(KnowledgeContext)
  if (!ctx) throw new Error('useKnowledge 必须在 KnowledgeProvider 内使用')
  return ctx
}
