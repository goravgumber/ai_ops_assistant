export const API_BASE = 'https://aiopsassistant-production.up.railway.app/'

async function request(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      },
      ...options
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      return { error: data.error || `HTTP ${response.status}` }
    }
    return data
  } catch (error) {
    return { error: error?.message || 'Network request failed' }
  }
}

export async function runFullPipeline(task, options = {}) {
  return request('/task', {
    method: 'POST',
    body: JSON.stringify({
      task,
      use_cache: true,
      parallel_execution: false,
      ...options
    })
  })
}

export async function runPlannerOnly(task) {
  return request('/planner', {
    method: 'POST',
    body: JSON.stringify({ task })
  })
}

export async function runExecutorOnly(plan) {
  return request('/executor', {
    method: 'POST',
    body: JSON.stringify({ plan })
  })
}

export async function runVerifierOnly(plan, results) {
  return request('/verifier', {
    method: 'POST',
    body: JSON.stringify({ plan, results })
  })
}

export async function streamTask(task, options = {}, onEvent = () => {}) {
  const response = await fetch('http://localhost:8000/task/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task,
      use_cache: options.use_cache ?? true,
      parallel_execution: options.parallel ?? false
    })
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  if (!response.body) {
    throw new Error('Streaming not supported by browser')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (!data || data === '[DONE]') continue
      try {
        onEvent(JSON.parse(data))
      } catch (e) {
        console.warn('SSE parse error:', e)
      }
    }
  }

  if (buffer.startsWith('data: ')) {
    const data = buffer.slice(6).trim()
    if (data && data !== '[DONE]') {
      try {
        onEvent(JSON.parse(data))
      } catch (e) {
        console.warn('SSE parse error:', e)
      }
    }
  }
  try {
    reader.releaseLock()
  } catch {
    // no-op
  }
}

export async function getCostReport() {
  return request('/cost')
}

export async function getCacheStats() {
  return request('/cache')
}

export async function getMemory() {
  return request('/memory')
}

export async function getHistory() {
  const data = await request('/history')
  if (data?.error) return data
  return Array.isArray(data?.history) ? data.history : data
}

export async function clearCache() {
  return request('/cache', { method: 'DELETE' })
}

export async function clearMemory() {
  return request('/memory', { method: 'DELETE' })
}

export async function getHealth() {
  return request('/health')
}
