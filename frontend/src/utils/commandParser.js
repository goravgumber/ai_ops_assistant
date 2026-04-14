export const COMMANDS = {
  '/h': {
    key: '/h',
    label: 'History',
    description: 'Show all chat history from this session',
    category: 'quick',
    action: 'SHOW_HISTORY'
  },
  '/u': {
    key: '/u',
    label: 'Users',
    description: 'Show user session log and info',
    category: 'quick',
    action: 'SHOW_USERS'
  },
  '/c': {
    key: '/c',
    label: 'Clear',
    description: 'Clear the terminal screen',
    category: 'quick',
    action: 'CLEAR'
  },
  '/pr': {
    key: '/pr',
    label: 'Prev Chat',
    description: 'Load previous chat sessions',
    category: 'quick',
    action: 'PREV_CHAT'
  },
  '/v': {
    key: '/v',
    label: 'Voice',
    description: 'Toggle voice input mode',
    category: 'quick',
    action: 'TOGGLE_VOICE'
  },
  '/e': {
    key: '/e',
    label: 'Exit',
    description: 'Exit the terminal session',
    category: 'quick',
    action: 'EXIT'
  },
  '/planner': {
    key: '/planner',
    label: 'Plan a task',
    description: 'Run only the Planner Agent on your task',
    category: 'agent',
    action: 'RUN_PLANNER',
    usage: '/planner <your task>'
  },
  '/executor': {
    key: '/executor',
    label: 'Execute plan',
    description: 'Run only the Executor Agent on last plan',
    category: 'agent',
    action: 'RUN_EXECUTOR',
    usage: '/executor'
  },
  '/verifier': {
    key: '/verifier',
    label: 'Verify result',
    description: 'Run only the Verifier Agent on last result',
    category: 'agent',
    action: 'RUN_VERIFIER',
    usage: '/verifier'
  },
  '/run': {
    key: '/run',
    label: 'Full pipeline',
    description: 'Run complete Plan→Execute→Verify pipeline',
    category: 'agent',
    action: 'RUN_FULL',
    usage: '/run <your task>'
  },
  '/cost': {
    key: '/cost',
    label: 'Cost report',
    description: 'Show token usage and cost breakdown',
    category: 'agent',
    action: 'SHOW_COST'
  },
  '/cache': {
    key: '/cache',
    label: 'Cache stats',
    description: 'Show cache hit rate and statistics',
    category: 'agent',
    action: 'SHOW_CACHE'
  },
  '/memory': {
    key: '/memory',
    label: 'Memory',
    description: 'Show session memory contents',
    category: 'agent',
    action: 'SHOW_MEMORY'
  },
  '/help': {
    key: '/help',
    label: 'Help',
    description: 'Show all available commands',
    category: 'agent',
    action: 'SHOW_HELP'
  }
}

export function parseCommand(input) {
  const raw = String(input ?? '')
  const trimmed = raw.trim()

  if (!trimmed.startsWith('/')) {
    return {
      isCommand: false,
      text: trimmed,
      raw
    }
  }

  const firstSpace = trimmed.indexOf(' ')
  const cmd = (firstSpace === -1 ? trimmed : trimmed.slice(0, firstSpace)).toLowerCase()
  const args = firstSpace === -1 ? '' : trimmed.slice(firstSpace + 1)

  if (COMMANDS[cmd]) {
    return {
      isCommand: true,
      command: COMMANDS[cmd],
      args: args.trim(),
      raw
    }
  }

  return {
    isCommand: true,
    command: null,
    args: trimmed,
    raw,
    error: `Unknown command: ${cmd}. Type /help for list.`
  }
}

export function getSuggestions(partial) {
  const value = String(partial ?? '').trim().toLowerCase()
  if (!value || !value.startsWith('/')) return []

  return Object.keys(COMMANDS)
    .filter((key) => key.startsWith(value))
    .slice(0, 6)
    .map((key) => COMMANDS[key])
}
