import React, { useEffect, useMemo, useRef, useState } from 'react'

/**
 * Props:
 * - messages: Array<{ type: string, content: string, ... }>
 */
export default function MessageList({ messages = [] }) {
  const endRef = useRef(null)
  const initialIdsRef = useRef(new Set(messages.map((m) => m.id)))
  const mountedRef = useRef(false)
  const timersRef = useRef(new Map())
  const [animatedContent, setAnimatedContent] = useState({})

  const visibleMessages = useMemo(() => {
    const clearIndex = [...messages].map((m) => m.type === 'system' && m.content === '__CLEAR__').lastIndexOf(true)
    return clearIndex >= 0 ? messages.slice(clearIndex + 1) : messages
  }, [messages])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      timersRef.current.forEach((timerId) => clearInterval(timerId))
      timersRef.current.clear()
    }
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [visibleMessages])

  useEffect(() => {
    visibleMessages.forEach((msg) => {
      const canAnimate =
        mountedRef.current &&
        msg.type === 'agent-result' &&
        !initialIdsRef.current.has(msg.id) &&
        !msg.fromHistory &&
        typeof msg.content === 'string' &&
        !timersRef.current.has(msg.id) &&
        animatedContent[msg.id] === undefined

      if (!canAnimate) return

      let index = 0
      const text = msg.content
      const timerId = setInterval(() => {
        index += 1
        setAnimatedContent((prev) => ({
          ...prev,
          [msg.id]: text.slice(0, index),
        }))
        if (index >= text.length) {
          clearInterval(timerId)
          timersRef.current.delete(msg.id)
        }
      }, 8)
      timersRef.current.set(msg.id, timerId)
    })
  }, [visibleMessages, animatedContent])

  return (
    <main className="message-list">
      {visibleMessages.map((msg, idx) => {
        const ts = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''

        if (msg.type === 'user') {
          return (
            <div className="message" key={idx}>
              <div className="message-prompt">[GKT] #</div>
              <div className="message-content">{msg.content}</div>
              {ts ? <div className="message-timestamp">{ts}</div> : null}
            </div>
          )
        }

        if (msg.type === 'response') {
          return (
            <div className="message message-response" key={idx}>
              {msg.label ? <div className="message-system">── {msg.label} ──────</div> : null}
              <div className="message-prompt">[Response/GKT]</div>
              <pre className="message-content">{msg.content}</pre>
              {ts ? <div className="message-timestamp">{ts}</div> : null}
            </div>
          )
        }

        if (msg.type === 'agent-start') {
          return (
            <div className="message message-agent" key={idx}>
              <div className="message-prompt">[{msg.agent}]</div>
              <div className="message-content">{msg.content}</div>
            </div>
          )
        }

        if (msg.type === 'agent-result') {
          const content =
            animatedContent[msg.id] !== undefined ? animatedContent[msg.id] : msg.content
          return (
            <div className="message message-agent" key={idx}>
              <div className="message-prompt">[Response/{msg.agent}]</div>
              <pre className="message-content">{content}</pre>
              {msg.metadata ? <div className="message-timestamp">{msg.metadata}</div> : null}
            </div>
          )
        }

        if (msg.type === 'step') {
          return (
            <div className="message" key={idx}>
              <div className="message-system">{msg.content}</div>
            </div>
          )
        }

        if (msg.type === 'error') {
          return (
            <div className="message message-error" key={idx}>
              <div className="message-content">[ERROR] {msg.content}</div>
            </div>
          )
        }

        if (msg.type === 'loading') {
          return (
            <div className="message" key={idx}>
              <div className="message-prompt">[{msg.agent}] #</div>
              <div className="message-content">
                <span className="loading-dots">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          )
        }

        if (msg.type === 'system') {
          if (msg.content === '__CLEAR__') return null
          return (
            <div className="message" key={idx}>
              <div className="message-system">{msg.content}</div>
            </div>
          )
        }

        return (
          <div className="message" key={idx}>
            <div className="message-content">{msg.content}</div>
          </div>
        )
      })}
      <div ref={endRef} />
    </main>
  )
}
