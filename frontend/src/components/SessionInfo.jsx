import React, { useEffect, useMemo, useState } from 'react'

/**
 * Props:
 * - username?: string
 * - sessionNum?: number
 * - uptime?: string (optional override)
 * - msgCount?: number
 * - sessionStart?: Date
 */
export default function SessionInfo({
  username = 'user',
  sessionNum = 1,
  uptime,
  msgCount = 0,
  sessionStart = new Date()
}) {
  const [tick, setTick] = useState(Date.now())

  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), 60_000)
    return () => clearInterval(timer)
  }, [])

  const uptimeText = useMemo(() => {
    if (uptime) return uptime
    const diff = tick - new Date(sessionStart).getTime()
    const mins = Math.floor(diff / 60000)
    const hrs = Math.floor(mins / 60)
    if (hrs > 0) return `${hrs}h${mins % 60}m`
    return `${mins}m`
  }, [uptime, tick, sessionStart])

  return (
    <section className="session-info">
      <div>
        <span className="label">user</span>
        <span className="value">
          {username} @{username} session#{sessionNum} role:standard
        </span>
      </div>
      <div>
        <span className="label">host</span>
        <span className="value">gkt-terminal v1.0 uptime:{uptimeText} msgs:{msgCount}</span>
      </div>
    </section>
  )
}
