import { useEffect, useState, useCallback } from 'react'
import { getHealth, getStats } from '../api/client'
import type { HealthResponse, StatsResponse, WSEvent, WSTagDetectedEvent } from '../api/types'
import { useWebSocket } from '../hooks/useWebSocket'
import { Card, Alert, StatusIndicator } from '../components'

interface RecentEvent extends WSTagDetectedEvent {
  id: number
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [recentEvents, setRecentEvents] = useState<RecentEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleWsMessage = useCallback((event: WSEvent) => {
    if (event.type === 'TAG_DETECTED') {
      setRecentEvents((prev) => [
        { ...event, id: Date.now() },
        ...prev.slice(0, 19), // Keep last 20 events
      ])
    }
    if (event.type === 'STATUS_UPDATE') {
      setStats((prev) => ({
        in_cart_count: event.in_cart_count,
        paid_count: event.paid_count,
        alarms_last_24h: prev?.alarms_last_24h ?? 0,
      }))
    }
  }, [])

  const { isConnected: wsConnected } = useWebSocket({ onMessage: handleWsMessage })

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthData, statsData] = await Promise.all([getHealth(), getStats()])
        setHealth(healthData)
        setStats(statsData)
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to fetch data')
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${mins}m`
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {error && <Alert variant="error">{error}</Alert>}

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <div className="text-sm font-medium text-gray-500">Service Status</div>
          <div className="mt-2 flex items-center">
            <StatusIndicator status={health?.ok ?? false} />
            <span className="text-lg font-semibold ml-2">{health?.ok ? 'Online' : 'Offline'}</span>
          </div>
          <div className="text-xs text-gray-400 mt-1">
            Uptime: {health ? formatUptime(health.uptime_seconds) : '-'}
          </div>
        </Card>

        <Card>
          <div className="text-sm font-medium text-gray-500">MQTT Connection</div>
          <div className="mt-2 flex items-center">
            <StatusIndicator status={health?.mqtt_connected ?? false} />
            <span className="text-lg font-semibold ml-2">{health?.mqtt_connected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <div className="text-xs text-gray-400 mt-1">
            WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}
          </div>
        </Card>

        <Card>
          <div className="text-sm font-medium text-gray-500">Tags in System</div>
          <div className="mt-2">
            <span className="text-2xl font-bold text-circa-600">{stats?.in_cart_count ?? 0}</span>
            <span className="text-sm text-gray-500 ml-2">In Cart</span>
          </div>
          <div className="text-sm text-gray-500">
            <span className="font-medium">{stats?.paid_count ?? 0}</span> Paid
          </div>
        </Card>

        <Card>
          <div className="text-sm font-medium text-gray-500">Alarms (24h)</div>
          <div className="mt-2">
            <span className={`text-2xl font-bold ${(stats?.alarms_last_24h ?? 0) > 10 ? 'text-danger-600' : 'text-gray-900'}`}>
              {stats?.alarms_last_24h ?? 0}
            </span>
          </div>
          <div className="text-xs text-gray-400 mt-1">
            Gate last seen: {health?.gate_last_seen_seconds != null ? `${health.gate_last_seen_seconds}s ago` : 'Never'}
          </div>
        </Card>
      </div>

      {/* Recent Events */}
      <Card padding="none">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Recent Tag Detections</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tag ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">RSSI</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Antenna</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Decision</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {recentEvents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                    No recent events. Waiting for tag detections...
                  </td>
                </tr>
              ) : (
                recentEvents.map((event) => (
                  <tr key={event.id} className={event.decision === 'ALARM' ? 'bg-danger-50' : ''}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                      {event.tag_id.substring(0, 16)}...
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {event.rssi?.toFixed(1) ?? '-'} dBm
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {event.antenna ?? '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        event.decision === 'PASS' ? 'bg-success-100 text-success-800' : 'bg-danger-100 text-danger-800'
                      }`}>
                        {event.decision}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

