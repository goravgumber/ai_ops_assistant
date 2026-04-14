import React, { useEffect, useMemo, useState } from 'react'
import { getSuggestions } from '../utils/commandParser'

/**
 * Props:
 * - input: string
 * - onSelect: (command: string) => void
 * - visible: boolean
 */
export default function CommandPalette({ input = '', onSelect, visible }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const suggestions = useMemo(() => getSuggestions(input), [input])

  useEffect(() => {
    setSelectedIndex(0)
  }, [input])

  useEffect(() => {
    if (!visible || suggestions.length === 0) return undefined

    const onKeyDown = (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev + 1) % suggestions.length)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length)
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const selected = suggestions[selectedIndex]
        if (selected) onSelect(selected.key)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visible, suggestions, selectedIndex, onSelect])

  if (!visible || suggestions.length === 0) return null

  return (
    <div className="command-palette">
      {suggestions.map((item, idx) => (
        <div
          key={item.key}
          className={`palette-item ${idx === selectedIndex ? 'selected' : ''}`}
          onMouseEnter={() => setSelectedIndex(idx)}
          onMouseDown={(e) => {
            e.preventDefault()
            onSelect(item.key)
          }}
        >
          <span className="palette-cmd">{item.key}</span>
          <span className="palette-desc">{item.description}</span>
        </div>
      ))}
    </div>
  )
}
