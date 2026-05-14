import { useState, useCallback } from 'react'
import { api } from '../api'
import type { Recommendation } from '../types'

export function useRecommendation() {
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null)
  const [loading, setLoading] = useState(false)

  const getNext = useCallback(async (skipId?: number) => {
    setLoading(true)
    try {
      const rec = await api.getRecommendation(skipId) as Recommendation
      setRecommendation(rec)
    } catch {
      setRecommendation(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const setAsNext = useCallback(async (taskId: number) => {
    await api.updateTask(taskId, { slot: 'next' })
  }, [])

  return { recommendation, loading, getNext, setAsNext }
}
