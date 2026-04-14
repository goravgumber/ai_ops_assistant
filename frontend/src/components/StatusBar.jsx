import React from 'react'

/**
 * Props:
 * - username?: string
 */
export default function StatusBar({ username = 'user' }) {
  return (
    <header className="terminal-header">
      <div className="header-left">
        <span className="dot dot-red" />
        <span className="dot dot-yellow" />
        <span className="dot dot-green" />
      </div>
      <div className="header-center">{username}@gkt: ~</div>
      <div className="header-right">
        <span className="online-dot" />GKT v1.0 ONLINE
      </div>
    </header>
  )
}
