import React, { useState } from 'react'

/**
 * Props:
 * - onSubmit: (value: string) => void
 * - loading: { active?: boolean }
 * - onInputChange?: (value: string) => void
 * - inputValue?: string
 */
export default function InputBar({ onSubmit, loading = { active: false }, onInputChange, inputValue }) {
  const [value, setValue] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const effectiveValue = typeof inputValue === 'string' ? inputValue : value
  const showCursor = !loading.active && isFocused && !effectiveValue

  const submit = () => {
    const trimmed = effectiveValue.trim()
    if (!trimmed || loading.active) return
    onSubmit(trimmed)
    setValue('')
    onInputChange?.('')
  }

  return (
    <div className="input-bar">
      <div className="input-prompt">[GKT] #</div>
      <div className={`input-field-wrap ${showCursor ? 'show-cursor' : ''}`}>
        <input
          className={`input-field ${showCursor ? 'empty-focused' : ''}`}
          value={effectiveValue}
          disabled={loading.active}
          placeholder={loading.active ? 'Running command...' : 'Type a task or slash command...'}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onChange={(e) => {
            setValue(e.target.value)
            onInputChange?.(e.target.value)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              submit()
            }
          }}
        />
      </div>
      <button type="button" className="voice-btn" disabled={loading.active}>
        $ /v
      </button>
      <button type="button" className="send-btn" onClick={submit} disabled={loading.active}>
        Send ↵
      </button>
    </div>
  )
}
