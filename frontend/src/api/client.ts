import type {
  HealthResponse,
  StatsResponse,
  ConfigResponse,
  AlarmListResponse,
  CalibrationResponse,
  InventoryStatusResponse,
  EdgeConfig,
} from './types'

const API_BASE = ''

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }))
    throw new Error(error.detail || error.message || 'API Error')
  }

  return response.json()
}

// Health & Stats
export const getHealth = (): Promise<HealthResponse> => fetchApi('/health')

export const getStats = (): Promise<StatsResponse> => fetchApi('/v1/stats')

// Configuration
export const getConfig = (): Promise<ConfigResponse> => fetchApi('/v1/config')

export const updateConfig = (config: Partial<EdgeConfig>): Promise<ConfigResponse> =>
  fetchApi('/v1/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })

export const reloadConfig = (): Promise<{ ok: boolean; message: string }> =>
  fetchApi('/v1/config/reload', { method: 'POST' })

// Calibration
export const startInventory = (): Promise<CalibrationResponse> =>
  fetchApi('/v1/calibration/start', { method: 'POST' })

export const stopInventory = (): Promise<CalibrationResponse> =>
  fetchApi('/v1/calibration/stop', { method: 'POST' })

export const setAntennaPower = (power: {
  antenna1: number
  antenna2: number
  antenna3: number
  antenna4: number
}): Promise<CalibrationResponse> =>
  fetchApi('/v1/calibration/power', {
    method: 'POST',
    body: JSON.stringify(power),
  })

export const testAlarm = (): Promise<CalibrationResponse> =>
  fetchApi('/v1/calibration/test-alarm', { method: 'POST' })

export const getAntennaPower = (): Promise<CalibrationResponse> =>
  fetchApi('/v1/calibration/power', { method: 'GET' })

export const getReaderStatus = (): Promise<CalibrationResponse> =>
  fetchApi('/v1/calibration/status', { method: 'GET' })

export const getInventoryStatus = (): Promise<InventoryStatusResponse> =>
  fetchApi('/v1/calibration/inventory-status', { method: 'GET' })

// Alarms
export const getAlarms = (params: {
  page?: number
  limit?: number
  from?: string
  to?: string
}): Promise<AlarmListResponse> => {
  const searchParams = new URLSearchParams()
  if (params.page) searchParams.set('page', params.page.toString())
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.from) searchParams.set('from', params.from)
  if (params.to) searchParams.set('to', params.to)

  return fetchApi(`/v1/alarms?${searchParams.toString()}`)
}

export const exportAlarmsUrl = (from?: string, to?: string): string => {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  return `/v1/alarms/export?${params.toString()}`
}

