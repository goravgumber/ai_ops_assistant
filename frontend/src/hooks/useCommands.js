import { useState, useCallback, useRef } from 'react'
import { parseCommand, getSuggestions } from '../utils/commandParser'
import * as api from '../services/api'

export function useCommands(addMessage, setLoading) {
  const [lastPlan, setLastPlan] = useState(null)
  const [lastResults, setLastResults] = useState(null)
  const [lastTask, setLastTask] = useState('')
  const [sessionHistory, setSessionHistory] = useState([])
  const [sessionStart] = useState(new Date())
  const [msgCount, setMsgCount] = useState(0)
  const streamCleanupRef = useRef(null)

  const executeCommand = useCallback(async (input) => {
    const parsed = parseCommand(input)
    setMsgCount((c) => c + 1)

    addMessage({
      type: 'user',
      content: input,
      timestamp: new Date()
    })
    setSessionHistory((prev) => [...prev, { text: input, timestamp: new Date().toISOString() }])

    if (!parsed.isCommand) {
      setLastTask(input)
      await handleFullRun(input)
      return
    }

    if (parsed.error) {
      addMessage({ type: 'error', content: parsed.error })
      return
    }

    switch (parsed.command.action) {
      case 'SHOW_HISTORY': {
        addMessage({
          type: 'response',
          content: formatSessionHistory(sessionHistory),
          label: '/h SESSION HISTORY'
        })
        break
      }

      case 'SHOW_USERS':
        addMessage({
          type: 'response',
          content: formatUserInfo(sessionStart, msgCount),
          label: 'USER LOG'
        })
        break

      case 'CLEAR':
        addMessage({ type: 'system', content: '__CLEAR__' })
        break

      case 'PREV_CHAT': {
        const hist = await api.getHistory()
        addMessage({
          type: 'response',
          content: formatHistory(hist),
          label: '/pr PREVIOUS CHATS'
        })
        break
      }

      case 'TOGGLE_VOICE':
        addMessage({
          type: 'system',
          content: 'Voice mode toggled. (Microphone support depends on backend)'
        })
        break

      case 'EXIT':
        addMessage({ type: 'system', content: 'Session ended. Goodbye.' })
        setTimeout(() => window.close(), 1500)
        break

      case 'RUN_PLANNER':
        if (!parsed.args && !lastTask) {
          addMessage({ type: 'error', content: 'Usage: /planner <your task description>' })
          break
        }
        await handlePlannerOnly(parsed.args || lastTask)
        break

      case 'RUN_EXECUTOR':
        if (!lastPlan) {
          addMessage({ type: 'error', content: 'No plan available. Run /planner first.' })
          break
        }
        await handleExecutorOnly(lastPlan)
        break

      case 'RUN_VERIFIER':
        if (!lastPlan || !lastResults) {
          addMessage({
            type: 'error',
            content: 'No results to verify. Run /planner then /executor first.'
          })
          break
        }
        await handleVerifierOnly(lastPlan, lastResults)
        break

      case 'RUN_FULL': {
        const task = parsed.args || input
        setLastTask(task)
        await handleFullRun(task)
        break
      }

      case 'SHOW_COST': {
        const cost = await api.getCostReport()
        addMessage({ type: 'response', content: formatCostReport(cost), label: 'COST REPORT' })
        break
      }

      case 'SHOW_CACHE': {
        const cache = await api.getCacheStats()
        addMessage({ type: 'response', content: formatCacheStats(cache), label: 'CACHE STATS' })
        break
      }

      case 'SHOW_MEMORY': {
        const memory = await api.getMemory()
        addMessage({ type: 'response', content: formatMemory(memory), label: 'SESSION MEMORY' })
        break
      }

      case 'SHOW_HELP':
        addMessage({ type: 'response', content: formatHelp(), label: 'HELP' })
        break

      default:
        addMessage({ type: 'error', content: 'Unsupported command.' })
    }
  }, [lastPlan, lastResults, lastTask, addMessage, setLoading, sessionStart, msgCount, sessionHistory])

  async function handlePlannerOnly(task) {
    setLoading({ active: true, agent: 'planner', message: 'Planner Agent thinking...' })
    addMessage({ type: 'agent-start', agent: 'PLANNER', content: `Analyzing task: "${task}"` })

    try {
      const result = await api.runPlannerOnly(task)
      if (result?.error) {
        throw new Error(result.error)
      }
      setLastPlan(result.plan)
      setLastTask(task)
      addMessage({
        type: 'agent-result',
        agent: 'PLANNER',
        content: formatPlan(result.plan),
        metadata: `${result.step_count ?? result?.plan?.steps?.length ?? 0} steps planned`
      })
    } catch (e) {
      addMessage({ type: 'error', content: 'Planner failed: ' + e.message })
    }

    setLoading({ active: false })
  }

  async function handleExecutorOnly(plan) {
    setLoading({ active: true, agent: 'executor', message: 'Executor Agent running steps...' })
    addMessage({
      type: 'agent-start',
      agent: 'EXECUTOR',
      content: `Executing ${plan?.steps?.length ?? 0} planned steps...`
    })

    try {
      const result = await api.runExecutorOnly(plan)
      if (result?.error) {
        throw new Error(result.error)
      }
      const executionPayload = normalizeExecutionPayload(result)
      setLastResults(executionPayload)
      addMessage({
        type: 'agent-result',
        agent: 'EXECUTOR',
        content: formatExecutionResults(executionPayload),
        metadata: `${executionPayload.steps_executed}/${executionPayload.steps_total} steps | ${executionPayload.cache_hits} cached`
      })
    } catch (e) {
      addMessage({ type: 'error', content: 'Executor failed: ' + e.message })
    }

    setLoading({ active: false })
  }

  async function handleVerifierOnly(plan, results) {
    setLoading({ active: true, agent: 'verifier', message: 'Verifier Agent validating...' })
    addMessage({
      type: 'agent-start',
      agent: 'VERIFIER',
      content: 'Validating and formatting results...'
    })

    try {
      let safeResults = results
      if (typeof safeResults === 'string') {
        try {
          safeResults = JSON.parse(safeResults)
        } catch {
          throw new Error('Verifier input is invalid. Run /executor again before /verifier.')
        }
      }

      if (!safeResults || typeof safeResults !== 'object') {
        throw new Error('Verifier input is invalid. Run /executor again before /verifier.')
      }

      const result = await api.runVerifierOnly(plan, safeResults)
      if (result?.error) {
        throw new Error(result.error)
      }
      addMessage({
        type: 'agent-result',
        agent: 'VERIFIER',
        content: formatVerifiedResult(result),
        metadata: `Confidence: ${result.confidence_score ?? 0}/100 (${result.confidence_grade ?? 'N/A'})`
      })
    } catch (e) {
      addMessage({ type: 'error', content: 'Verifier failed: ' + e.message })
    }

    setLoading({ active: false })
  }

  async function handleFullRun(task) {
    setLoading({ active: true, agent: 'pipeline', message: 'Running full pipeline...' })

    if (streamCleanupRef.current) {
      streamCleanupRef.current()
      streamCleanupRef.current = null
    }

    streamCleanupRef.current = await api.streamTask(task, {}, (event) => {
      switch (event.event) {
        case 'task_received':
          addMessage({ type: 'step', content: `Task received: ${event.task_id}` })
          break
        case 'planning_start':
          addMessage({ type: 'agent-start', agent: 'PLANNER', content: 'Analyzing your request...' })
          break
        case 'plan_ready':
          setLastPlan(event.plan)
          addMessage({
            type: 'agent-result',
            agent: 'PLANNER',
            content: formatPlan(event.plan),
            metadata: `${event.step_count} steps`
          })
          break
        case 'step_complete': {
          const icon = event.success ? '✓' : '✗'
          const cache = event.from_cache ? ' [cache]' : ''
          const heal = event.self_healed ? ' [healed]' : ''
          addMessage({
            type: 'step',
            content: `${icon} Step ${event.step}: ${event.tool}.${event.action}${cache}${heal}`
          })
          break
        }
        case 'execution_complete':
          addMessage({
            type: 'step',
            content: `Execution complete: ${event.steps_executed} steps, ${event.cache_hits} cache hits`
          })
          break
        case 'verification_start':
          addMessage({ type: 'agent-start', agent: 'VERIFIER', content: 'Validating final output...' })
          break
        case 'complete':
          setLastResults(event.result)
          addMessage({
            type: 'agent-result',
            agent: 'VERIFIER',
            content: formatVerifiedResult(event.result),
            metadata: `${event.confidence_score}/100 (${event.confidence_grade}) | ${event.execution_time}s`
          })
          setLoading({ active: false })
          break
        case 'error':
          addMessage({ type: 'error', content: event.message })
          setLoading({ active: false })
          break
        default:
          break
      }
    })
  }

  function formatHistory(history) {
    if (history?.error) return `Error: ${history.error}`
    if (!history?.length) return 'No previous tasks found.'

    return history
      .map(
        (h, i) =>
          `  › ${i + 1}. ${(h.task || '').substring(0, 50)}${(h.task || '').length > 50 ? '…' : ''}\t\t${formatTimeAgo(h.timestamp)}`
      )
      .join('\n')
  }

  function formatSessionHistory(history) {
    if (!history?.length) return 'No messages in this session yet.'
    return history
      .map(
        (h, i) =>
          `  › ${i + 1}. ${(h.text || '').substring(0, 70)}${(h.text || '').length > 70 ? '…' : ''}\t\t${formatTimeAgo(
            h.timestamp
          )}`
      )
      .join('\n')
  }

  function formatUserInfo(start, count) {
    const uptime = formatUptime(Date.now() - start.getTime())
    return [
      `  user\tSession User    @user    session#1   role:standard`,
      `  host\tgkt-terminal v1.0   uptime:${uptime}   msgs:${count}`
    ].join('\n')
  }

  function formatPlan(plan) {
    if (!plan?.steps) return 'No plan available'
    const lines = [`  Task: ${plan.task_summary}`, '']
    plan.steps.forEach((s) => {
      lines.push(`  [${s.step}] ${s.tool}.${s.action}`)
      lines.push(`      └─ ${s.description}`)
    })
    return lines.join('\n')
  }

  function formatExecutionResults(results) {
    if (!results?.results) return 'No results'
    const lines = []
    if (!Array.isArray(results.results)) return 'No results'
    results.results.forEach((r) => {
      const status = r.success ? '✓' : '✗'
      const cache = r.from_cache ? ' (cached)' : ''
      lines.push(`  ${status} ${r.tool}.${r.action}${cache}`)
    })
    return lines.join('\n')
  }

  function normalizeExecutionPayload(payload) {
    if (!payload || typeof payload !== 'object') {
      return {
        results: [],
        steps_executed: 0,
        steps_total: 0,
        cache_hits: 0,
        execution_time_seconds: 0
      }
    }

    if (payload.results && Array.isArray(payload.results)) {
      return payload
    }

    if (payload.results && typeof payload.results === 'object') {
      const inner = payload.results
      return {
        ...inner,
        steps_executed: payload.steps_executed ?? inner.steps_executed ?? 0,
        steps_total: payload.steps_total ?? inner.steps_total ?? 0,
        cache_hits: payload.cache_hits ?? inner.cache_hits ?? 0,
        execution_time_seconds: payload.execution_time ?? inner.execution_time_seconds ?? 0
      }
    }

    return {
      results: [],
      steps_executed: payload.steps_executed ?? 0,
      steps_total: payload.steps_total ?? 0,
      cache_hits: payload.cache_hits ?? 0,
      execution_time_seconds: payload.execution_time ?? 0
    }
  }

  function formatVerifiedResult(result) {
    if (!result) return 'No result'
    const lines = []
    if (result.summary) lines.push(`  ${result.summary}`, '')

    const repoKey = Object.keys(result).find((k) => k.includes('repo') || k.includes('github'))
    if (repoKey && Array.isArray(result[repoKey])) {
      lines.push('  Repositories:')
      result[repoKey].slice(0, 5).forEach((r, i) => {
        lines.push(`  ${i + 1}. ${r.name} — ⭐ ${(r.stars || 0).toLocaleString()}`)
      })
      lines.push('')
    }

    const weatherKey = Object.keys(result).find((k) => k.includes('weather'))
    if (weatherKey && result[weatherKey]) {
      const w = result[weatherKey]
      lines.push(`  Weather: ${w.temperature_c}°C, ${w.condition}`)
      lines.push(`  Humidity: ${w.humidity_percent}% | Wind: ${w.wind_kmh} km/h`)
      lines.push('')
    }

    const newsKey = Object.keys(result).find((k) => k.includes('news') || k.includes('headline'))
    if (newsKey && Array.isArray(result[newsKey])) {
      lines.push('  Headlines:')
      result[newsKey].slice(0, 3).forEach((n, i) => {
        lines.push(`  ${i + 1}. ${n.source} — ${n.title}`)
      })
    }

    return lines.join('\n')
  }

  function formatCostReport(cost) {
    if (cost?.error) return `Error: ${cost.error}`
    if (!cost) return 'No cost data'
    return [
      `  Requests: ${cost.total_requests}`,
      `  Input tokens: ${cost.total_input_tokens}`,
      `  Output tokens: ${cost.total_output_tokens}`,
      `  Total cost: $${cost.total_cost_usd}`
    ].join('\n')
  }

  function formatCacheStats(stats) {
    if (stats?.error) return `Error: ${stats.error}`
    if (!stats) return 'No cache data'
    const rate =
      stats.hit_count + stats.miss_count > 0
        ? ((stats.hit_count / (stats.hit_count + stats.miss_count)) * 100).toFixed(1)
        : 0

    return [
      `  Cache size: ${stats.cache_size}/${stats.max_size}`,
      `  TTL: ${stats.ttl_seconds}s`,
      `  Hits: ${stats.hit_count} | Misses: ${stats.miss_count}`,
      `  Hit rate: ${rate}%`
    ].join('\n')
  }

  function formatMemory(memory) {
    if (memory?.error) return `Error: ${memory.error}`
    if (!memory?.total_tasks) return 'No tasks in memory yet.'

    const lines = [`  Tasks remembered: ${memory.total_tasks}`, '']
    memory.memories?.forEach((m) => {
      lines.push(`  [${m.id}] ${(m.task || '').substring(0, 50)}`)
      lines.push(`       Tools: ${m.tools_used?.join(', ') || ''}`)
    })
    return lines.join('\n')
  }

  function formatHelp() {
    return [
      '  QUICK COMMANDS:',
      '  /h          Show chat history',
      '  /u          Show user info',
      '  /c          Clear terminal',
      '  /pr         Previous chats',
      '  /v          Toggle voice',
      '  /e          Exit session',
      '',
      '  AGENT COMMANDS:',
      '  /planner <task>   Run only Planner Agent',
      '  /executor         Run only Executor Agent',
      '  /verifier         Run only Verifier Agent',
      '  /run <task>       Full pipeline',
      '  /cost             Token cost report',
      '  /cache            Cache statistics',
      '  /memory           Session memory',
      '  /help             This help screen',
      '',
      '  Or just type any task in plain English!'
    ].join('\n')
  }

  function formatTimeAgo(ts) {
    if (!ts) return ''
    const diff = Date.now() - new Date(ts).getTime()
    const mins = Math.floor(diff / 60000)
    const hours = Math.floor(mins / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`
    if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`
    if (mins > 0) return `${mins} min${mins > 1 ? 's' : ''} ago`
    return 'just now'
  }

  function formatUptime(ms) {
    const m = Math.floor(ms / 60000)
    const h = Math.floor(m / 60)
    if (h > 0) return `${h}h${m % 60}m`
    return `${m}m`
  }

  const getCommandSuggestions = useCallback((partial) => getSuggestions(partial), [])

  return { executeCommand, lastPlan, lastResults, getCommandSuggestions }
}
