// API Response Types

export interface HealthResponse {
  ok: boolean
  mqtt_connected: boolean
  db_ok: boolean
  gate_last_seen_seconds: number | null
  uptime_seconds: number
}

export interface StatsResponse {
  in_cart_count: number
  paid_count: number
  alarms_last_24h: number
}

export interface AlarmEvent {
  id: number
  gate_id: string
  epc: string
  qr_code: string | null
  rssi: number | null
  antenna: number | null
  created_at: string
}

export interface AlarmListResponse {
  items: AlarmEvent[]
  total: number
  page: number
  limit: number
}

export interface ConfigResponse {
  ok: boolean
  config: EdgeConfig
}

export interface EdgeConfig {
  http: {
    host: string
    port: number
  }
  mqtt: {
    host: string
    port: number
    username: string
    password: string
  }
  gate: {
    client_id: string
    topic_tag_stream: string
    topic_gpo_cmd: string
    gpo_pulse_seconds: number
  }
  ttl: {
    in_cart_seconds: number
    paid_seconds: number
    cleanup_interval_seconds: number
  }
  decision: {
    pass_when_in_cart: boolean
    debounce_ms: number
    alarm_cooldown_ms: number
  }
  storage: {
    sqlite_path: string
  }
  auth: {
    enabled: boolean
    token: string
  }
}

export interface CalibrationResponse {
  ok: boolean
  message: string
}

export interface InventoryStatusResponse {
  ok: boolean
  mqtt_connected: boolean
  inventory_running: boolean
}

// WebSocket Event Types

export type WSEvent =
  | WSTagDetectedEvent
  | WSAlarmTriggeredEvent
  | WSStatusUpdateEvent
  | WSCommandResponseEvent
  | WSReaderStatusEvent
  | WSInventoryStateEvent

export interface WSTagDetectedEvent {
  type: 'TAG_DETECTED'
  tag_id: string
  rssi: number | null
  antenna: number | null
  decision: 'PASS' | 'ALARM'
  timestamp: string
}

export interface WSAlarmTriggeredEvent {
  type: 'ALARM_TRIGGERED'
  tag_id: string
  gate_id: string
  rssi: number | null
  timestamp: string
}

export interface WSStatusUpdateEvent {
  type: 'STATUS_UPDATE'
  mqtt_connected: boolean
  in_cart_count: number
  paid_count: number
}

export interface WSCommandResponseEvent {
  type: 'COMMAND_RESPONSE'
  command: string
  action: string
  status: 'success' | 'error'
  message: string
  data?: {
    ant1?: number
    ant2?: number
    ant3?: number
    ant4?: number
    [key: string]: unknown
  }
  timestamp: string
}

export interface WSReaderStatusEvent {
  type: 'READER_STATUS'
  status: string
  uptime: number
  memory: number
  antennas?: number[]
  inventory_running?: boolean
  timestamp: string
}

export interface WSInventoryStateEvent {
  type: 'INVENTORY_STATE'
  inventory_running: boolean
  timestamp: string
}

