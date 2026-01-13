import { useEffect, useState } from 'react'
import { getAlarms, exportAlarmsUrl } from '../api/client'
import type { AlarmEvent } from '../api/types'
import { Card, Button, Input } from '../components'

export default function AlarmLogs() {
  const [alarms, setAlarms] = useState<AlarmEvent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const limit = 20

  useEffect(() => {
    fetchAlarms()
  }, [page, fromDate, toDate])

  const fetchAlarms = async () => {
    setLoading(true)
    try {
      const response = await getAlarms({
        page,
        limit,
        from: fromDate || undefined,
        to: toDate || undefined,
      })
      setAlarms(response.items)
      setTotal(response.total)
    } catch (e) {
      console.error('Failed to fetch alarms:', e)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Alarm Logs</h1>
        <a
          href={exportAlarmsUrl(fromDate, toDate)}
          className="px-4 py-2 bg-circa-600 text-white rounded-md text-sm hover:bg-circa-700 transition-colors"
          download
        >
          Export CSV
        </a>
      </div>

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap gap-4 items-end">
          <Input
            label="From Date"
            type="date"
            value={fromDate}
            onChange={(e) => { setFromDate(e.target.value); setPage(1) }}
          />
          <Input
            label="To Date"
            type="date"
            value={toDate}
            onChange={(e) => { setToDate(e.target.value); setPage(1) }}
          />
          <Button
            onClick={() => { setFromDate(''); setToDate(''); setPage(1) }}
            variant="ghost"
            size="sm"
          >
            Clear Filters
          </Button>
          <div className="ml-auto text-sm text-gray-500">
            Total: <span className="font-semibold text-circa-600">{total}</span> alarms
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date/Time</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Gate</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">QR Code</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">EPC</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">RSSI</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Antenna</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-circa-500">Loading...</td>
              </tr>
            ) : alarms.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-gray-500">No alarms found</td>
              </tr>
            ) : (
              alarms.map((alarm) => (
                <tr key={alarm.id} className="hover:bg-circa-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{alarm.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {new Date(alarm.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{alarm.gate_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                    {alarm.qr_code || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500" title={alarm.epc}>
                    {alarm.epc.length > 16 ? `${alarm.epc.substring(0, 16)}...` : alarm.epc}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {alarm.rssi?.toFixed(1) ?? '-'} dBm
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{alarm.antenna ?? '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="bg-gray-50 px-6 py-3 flex items-center justify-between border-t border-gray-200">
            <div className="text-sm text-gray-500">
              Page <span className="font-medium text-circa-600">{page}</span> of {totalPages}
            </div>
            <div className="flex space-x-2">
              <Button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                variant="secondary"
                size="sm"
              >
                Previous
              </Button>
              <Button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                variant="secondary"
                size="sm"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

