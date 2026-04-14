import React from 'react'

const AGENT_TAGS = [
  { key: '/planner', desc: 'Plan a task' },
  { key: '/executor', desc: 'Execute plan' },
  { key: '/verifier', desc: 'Verify result' },
  { key: '/run', desc: 'Full pipeline' },
  { key: '/cost', desc: 'Cost' },
  { key: '/cache', desc: 'Cache' },
  { key: '/memory', desc: 'Memory' },
  { key: '/help', desc: 'Help' }
]

/**
 * Props:
 * - onCommand: (cmd: string) => void
 */
export default function AgentCommands({ onCommand }) {
  return (
    <section className="agent-commands">
      <div className="section-label">AGENTIC COMMANDS</div>
      {AGENT_TAGS.map((item) => (
        <button key={item.key} type="button" className="agent-tag" onClick={() => onCommand(item.key)}>
          <span className="agent-key">{item.key}</span>
          <span className="agent-desc">{item.desc}</span>
        </button>
      ))}
    </section>
  )
}
