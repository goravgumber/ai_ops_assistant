import React from 'react'

const QUICK_TAGS = [
  { key: '/h', label: 'History' },
  { key: '/u', label: 'Users' },
  { key: '/c', label: 'Clear' },
  { key: '/pr', label: 'Prev Chat' },
  { key: '/v', label: 'Voice' },
  { key: '/e', label: 'Exit' }
]

/**
 * Props:
 * - onCommand: (cmd: string) => void
 */
export default function QuickCommands({ onCommand }) {
  return (
    <section className="quick-commands">
      <div className="section-label">QUICK COMMANDS</div>
      {QUICK_TAGS.map((item) => (
        <button key={item.key} type="button" className="cmd-tag" onClick={() => onCommand(item.key)}>
          <span className="cmd-key">{item.key}</span>
          <span className="cmd-label">{item.label}</span>
        </button>
      ))}
    </section>
  )
}
