import { useEffect, useRef, useState } from 'react'
import type { WSEvent } from '../api/types'

interface UseWebSocketOptions {
  onMessage?: (event: WSEvent) => void
  reconnectInterval?: number
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { onMessage, reconnectInterval = 3000 } = options
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const onMessageRef = useRef(onMessage)

  // Keep onMessage ref updated without triggering reconnection
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    let isMounted = true

    const connect = () => {
      // Don't create new connection if one already exists and is open/connecting
      if (wsRef.current?.readyState === WebSocket.OPEN ||
          wsRef.current?.readyState === WebSocket.CONNECTING) {
        return
      }

      // Determine WebSocket URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/ws`

      try {
        const ws = new WebSocket(wsUrl)

        ws.onopen = () => {
          if (isMounted) {
            console.log('WebSocket connected')
            setIsConnected(true)
          }
        }

        ws.onclose = () => {
          if (isMounted) {
            console.log('WebSocket disconnected')
            setIsConnected(false)
            wsRef.current = null

            // Attempt reconnection
            reconnectTimeoutRef.current = window.setTimeout(() => {
              if (isMounted) {
                connect()
              }
            }, reconnectInterval)
          }
        }

        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as WSEvent
            onMessageRef.current?.(data)
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        wsRef.current = ws
      } catch (error) {
        console.error('Failed to create WebSocket:', error)
        // Retry connection
        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (isMounted) {
            connect()
          }
        }, reconnectInterval)
      }
    }

    connect()

    return () => {
      isMounted = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [reconnectInterval]) // Only reconnectInterval as dependency

  return { isConnected }
}

