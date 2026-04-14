import React, { useState, useEffect, useRef, useCallback } from 'react'
import StatusBar from './StatusBar'
import MessageList from './MessageList'
import InputBar from './InputBar'
import QuickCommands from './QuickCommands'
import AgentCommands from './AgentCommands'
import SessionInfo from './SessionInfo'
import CommandPalette from './CommandPalette'
import { useCommands } from '../hooks/useCommands'

function LoadingDots() {
  return (
    <span className="loading-dots">
      <span />
      <span />
      <span />
    </span>
  )
}

export default function Terminal() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState({ active: false, agent: '', message: '' })
  const [inputValue, setInputValue] = useState('')
  const [sessionStart] = useState(new Date())
  const [msgCount, setMsgCount] = useState(0)
  const [username] = useState('user')
  const [voiceUiActive, setVoiceUiActive] = useState(false)
  const initializedRef = useRef(false)

  const addMessage = useCallback((msg) => {
    if (msg.content === '__CLEAR__') {
      setMessages([])
      return
    }

    const normalized = {
      id: Date.now() + Math.random(),
      timestamp: msg.timestamp || new Date(),
      ...msg,
    }
    setMessages((prev) => [...prev, normalized])
    setMsgCount((c) => c + 1)
  }, [])

  const { executeCommand } = useCommands(addMessage, setLoading)

  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    addMessage({
      type: 'response',
      content: 'Welcome back. Session #1 started.',
      label: 'Response/GKT',
    })
    addMessage({
      type: 'system',
      content: 'Type a message or use /h for help. Voice available via /v.',
    })
  }, [addMessage])

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((r) => r.json())
      .then((data) => {
        addMessage({
          type: 'system',
          content: `Backend connected. ${data.total_requests} requests served.`,
        })
      })
      .catch(() => {
        addMessage({
          type: 'error',
          content: 'Backend not connected. Start api_server.py first.',
        })
      })
  }, [addMessage])

  const handleSubmit = useCallback(
    (valueFromInput) => {
      const value = String(valueFromInput ?? inputValue).trim()
      if (!value) return
      setInputValue('')
      executeCommand(value)
    },
    [executeCommand, inputValue]
  )

  const handleQuickCommand = useCallback(
    (cmdKey) => {
      if (cmdKey === '/v') {
        setVoiceUiActive((prev) => !prev)
      }
      if (cmdKey === '/planner' || cmdKey === '/run') {
        setInputValue(cmdKey + ' ')
        return
      }
      executeCommand(cmdKey)
    },
    [executeCommand]
  )

  return (
    <div className="terminal-root" style={{ position: 'relative' }}>
      <StatusBar username={username} />

      <MessageList messages={messages} />

      {loading.active && (
        <div className="agent-progress-box">
          <span className="agent-name">[{loading.agent?.toUpperCase()}]</span>
          <span className="agent-step"> {loading.message}</span>
          <LoadingDots />
        </div>
      )}

      <SessionInfo username={username} sessionNum={1} sessionStart={sessionStart} msgCount={msgCount} />

      <QuickCommands onCommand={handleQuickCommand} />

      <AgentCommands onCommand={handleQuickCommand} />

      {inputValue.startsWith('/') && (
        <CommandPalette
          input={inputValue}
          onSelect={(cmd) => {
            setInputValue(cmd + ' ')
          }}
          visible={true}
        />
      )}

      <InputBar
        onSubmit={handleSubmit}
        loading={loading}
        onInputChange={setInputValue}
        inputValue={inputValue}
        voiceActive={voiceUiActive}
      />
    </div>
  )
}
