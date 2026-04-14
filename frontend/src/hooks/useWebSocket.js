import { useCallback, useState } from 'react'

export default function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [lastEvent, setLastEvent] = useState(null)

  const startStream = useCallback(() => {
    setConnected(false)
    setStreaming(false)
    setLastEvent({ type: 'info', message: 'Streaming not wired yet' })
  }, [])

  const stopStream = useCallback(() => {
    setStreaming(false)
    setConnected(false)
  }, [])

  return {
    connected,
    streaming,
    lastEvent,
    startStream,
    stopStream
  }
}
