import { useQuery } from '@tanstack/react-query'
import { getHealth, getCases, getCandidates, getGeojson, getStats } from '@/lib/api'

export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 20_000 })
export const useStats = () => useQuery({ queryKey: ['stats'], queryFn: getStats })
export const useGeojson = () => useQuery({ queryKey: ['geojson'], queryFn: getGeojson })
export const useCandidates = () => useQuery({ queryKey: ['candidates'], queryFn: getCandidates })
export const useCases = (filters = {}) =>
  useQuery({ queryKey: ['cases', filters], queryFn: () => getCases(filters) })
