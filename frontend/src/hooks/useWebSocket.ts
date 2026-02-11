import { useEffect, useRef, useCallback, useState } from 'react'
import type { ProgressMessage } from '../api/types'

export function useWebSocket(onMessage?: (msg: ProgressMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<ProgressMessage | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const reconnectDelay = useRef(1000)

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/ws/progress`)

    ws.onopen = () => {
      setConnected(true)
      reconnectDelay.current = 1000
    }
    ws.onclose = () => {
      setConnected(false)
      // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
      reconnectTimer.current = setTimeout(connect, reconnectDelay.current)
      reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
    }
    ws.onerror = () => ws.close()
    ws.onmessage = (ev) => {
      try {
        const msg: ProgressMessage = JSON.parse(ev.data)
        setLastMessage(msg)
        onMessage?.(msg)
      } catch { /* ignore parse errors */ }
    }

    wsRef.current = ws
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, lastMessage }
}
