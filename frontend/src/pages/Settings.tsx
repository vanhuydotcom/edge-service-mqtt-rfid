import { useEffect, useState } from 'react'
import { getConfig, updateConfig, reloadConfig } from '../api/client'
import type { EdgeConfig } from '../api/types'
import { Card, CardHeader, Button, Alert, Input, Checkbox, Spinner } from '../components'

export default function Settings() {
  const [config, setConfig] = useState<EdgeConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const response = await getConfig()
      console.log("Config",response.config)
      setConfig(response.config)
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to load config' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    setMessage(null)

    try {
      await updateConfig({
        mqtt: config.mqtt,
        gate: config.gate,
        ttl: config.ttl,
        decision: config.decision,
      })
      setMessage({ type: 'success', text: 'Configuration saved successfully' })
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to save' })
    } finally {
      setSaving(false)
    }
  }

  const handleReload = async () => {
    setLoading(true)
    try {
      await reloadConfig()
      await fetchConfig()
      setMessage({ type: 'success', text: 'Configuration reloaded' })
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to reload' })
    } finally {
      setLoading(false)
    }
  }

  if (loading) return (
    <div className="text-center py-8">
      <Spinner size="lg" className="mx-auto mb-2" />
      <p className="text-gray-500">Loading configuration...</p>
    </div>
  )
  if (!config) return <div className="text-center py-8 text-danger-600">Failed to load configuration</div>

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <div className="space-x-2">
          <Button onClick={handleReload} variant="secondary" size="sm">
            Reload from File
          </Button>
          <Button onClick={handleSave} loading={saving} size="sm">
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {message && (
        <Alert variant={message.type === 'success' ? 'success' : 'error'}>
          {message.text}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* MQTT Settings */}
        <Card>
          <CardHeader title="MQTT Broker" icon="📡" />
          <div className="space-y-4">
            <Input
              label="Host"
              type="text"
              value={config.mqtt.host}
              onChange={(e) => setConfig({ ...config, mqtt: { ...config.mqtt, host: e.target.value } })}
            />
            <Input
              label="Port"
              type="number"
              value={config.mqtt.port}
              onChange={(e) => setConfig({ ...config, mqtt: { ...config.mqtt, port: parseInt(e.target.value) } })}
            />
          </div>
        </Card>

        {/* Gate Settings */}
        <Card>
          <CardHeader title="Gate Reader" icon="🚪" />
          <div className="space-y-4">
            <Input
              label="Client ID"
              type="text"
              value={config.gate.client_id}
              onChange={(e) => setConfig({ ...config, gate: { ...config.gate, client_id: e.target.value } })}
            />
            <Input
              label="Alarm Duration (seconds)"
              type="number"
              value={config.gate.gpo_pulse_seconds}
              onChange={(e) => setConfig({ ...config, gate: { ...config.gate, gpo_pulse_seconds: parseInt(e.target.value) } })}
            />
          </div>
        </Card>

        {/* TTL Settings */}
        <Card>
          <CardHeader title="TTL Settings" icon="⏱️" />
          <div className="space-y-4">
            <Input
              label="In-Cart TTL (seconds)"
              type="number"
              value={config.ttl.in_cart_seconds}
              onChange={(e) => setConfig({ ...config, ttl: { ...config.ttl, in_cart_seconds: parseInt(e.target.value) } })}
              hint="Default: 3600 (1 hour)"
            />
            <Input
              label="Paid TTL (seconds)"
              type="number"
              value={config.ttl.paid_seconds}
              onChange={(e) => setConfig({ ...config, ttl: { ...config.ttl, paid_seconds: parseInt(e.target.value) } })}
              hint="Default: 86400 (24 hours)"
            />
          </div>
        </Card>

        {/* Decision Settings */}
        <Card>
          <CardHeader title="Decision Engine" icon="⚙️" />
          <div className="space-y-4">
            <Checkbox
              label="Pass when In Cart"
              description="When enabled, tags in IN_CART state will pass through without alarm"
              checked={config.decision.pass_when_in_cart}
              onChange={(e) => setConfig({ ...config, decision: { ...config.decision, pass_when_in_cart: e.target.checked } })}
            />
            <Input
              label="Debounce (ms)"
              type="number"
              value={config.decision.debounce_ms}
              onChange={(e) => setConfig({ ...config, decision: { ...config.decision, debounce_ms: parseInt(e.target.value) } })}
            />
            <Input
              label="Alarm Cooldown (ms)"
              type="number"
              value={config.decision.alarm_cooldown_ms}
              onChange={(e) => setConfig({ ...config, decision: { ...config.decision, alarm_cooldown_ms: parseInt(e.target.value) } })}
            />
          </div>
        </Card>
      </div>
    </div>
  )
}

