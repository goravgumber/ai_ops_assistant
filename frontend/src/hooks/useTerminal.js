import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import useCommands from './useCommands'
import { filterCommands } from '../utils/commandParser'

function now() {
  return new Date().toLocaleTimeString()
}

function createId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export default function useTerminal() {
  const [messages, setMessages] = useState([
    {
      id: createId(),
      type: 'system',
      prompt: '[System/GKT]',
      content: 'Terminal initialized. API wiring is disabled in this stage.',
      timestamp: now()
    }
  ])
  const [input, setInput] = useState('')
  const [voiceActive, setVoiceActive] = useState(false)
  const [selectedPaletteIndex, setSelectedPaletteIndex] = useState(0)
  const startTimeRef = useRef(Date.now())

  const { executeCommand } = useCommands()

  const addMessage = useCallback((type, prompt, content) => {
    setMessages((prev) => [
      ...prev,
      {
        id: createId(),
        type,
        prompt,
        content,
        timestamp: now()
      }
    ])
  }, [])

  const addUserMessage = useCallback((content) => addMessage('user', '[GKT] #', content), [addMessage])
  const addAgentMessage = useCallback((prompt, content) => addMessage('response', `[${prompt}]`, content), [addMessage])
  const addSystemMessage = useCallback((content) => addMessage('system', '[System/GKT]', content), [addMessage])
  const addErrorMessage = useCallback((content) => addMessage('error', '[Error/GKT]', content), [addMessage])
  const addAgentProgress = useCallback((agent, step, status) => {
    addMessage('agent', `[${agent}]`, `${step}\nStatus: ${status}`)
  }, [addMessage])

  const clearMessages = useCallback(() => setMessages([]), [])
  const toggleVoice = useCallback(() => setVoiceActive((prev) => !prev), [])

  const onSubmit = useCallback(() => {
    if (!input.trim()) return

    executeCommand(input, {
      addUserMessage,
      addAgentMessage,
      addSystemMessage,
      addErrorMessage,
      addAgentProgress,
      clearMessages,
      toggleVoice,
      voiceActive
    })

    setInput('')
    setSelectedPaletteIndex(0)
  }, [
    input,
    executeCommand,
    addUserMessage,
    addAgentMessage,
    addSystemMessage,
    addErrorMessage,
    addAgentProgress,
    clearMessages,
    toggleVoice,
    voiceActive
  ])

  const suggestions = useMemo(() => filterCommands(input), [input])
  const showPalette = input.startsWith('/') && suggestions.length > 0

  useEffect(() => {
    if (selectedPaletteIndex >= suggestions.length) {
      setSelectedPaletteIndex(0)
    }
  }, [suggestions.length, selectedPaletteIndex])

  const selectSuggestion = useCallback((cmd) => {
    setInput(`${cmd} `)
    setSelectedPaletteIndex(0)
  }, [])

  const uptime = Math.floor((Date.now() - startTimeRef.current) / 1000)

  return {
    messages,
    input,
    setInput,
    onSubmit,
    voiceActive,
    toggleVoice,
    suggestions,
    showPalette,
    selectedPaletteIndex,
    setSelectedPaletteIndex,
    selectSuggestion,
    uptime
  }
}
