'use client'

import { use, useState } from 'react'
import { useGuildConfig } from '@/hooks/useGuildConfig'

interface PageProps {
  params: Promise<{ guildId: string }>
}

const COMMAND_INFO: Record<string, { name: string; description: string }> = {
  beer: {
    name: '/beer',
    description: 'Share a beer with ClaudeBot - increments a fun counter',
  },
  ping: {
    name: '/ping',
    description: 'Check bot latency and responsiveness',
  },
  uptime: {
    name: '/uptime',
    description: 'See how long the bot has been running',
  },
  cacheStats: {
    name: '/cache-stats',
    description: 'View conversation cache statistics (admin only)',
  },
  clearCache: {
    name: '/clear-cache',
    description: 'Clear conversation cache for a channel (admin only)',
  },
}

export default function CommandsPage({ params }: PageProps) {
  const { guildId } = use(params)
  const { config, isLoading, updateCommands } = useGuildConfig(guildId)
  const [saving, setSaving] = useState<string | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  if (isLoading || !config) {
    return <LoadingSkeleton />
  }

  const handleToggle = async (command: string, enabled: boolean) => {
    setSaving(command)
    setMessage(null)

    try {
      await updateCommands({ [command]: enabled })
      setMessage({ type: 'success', text: `${COMMAND_INFO[command].name} ${enabled ? 'enabled' : 'disabled'}` })
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to update command' })
    } finally {
      setSaving(null)
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-dark-50">Commands</h1>
        <p className="text-dark-400">Enable or disable slash commands for this server</p>
      </div>

      {message && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            message.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="space-y-3">
        {Object.entries(COMMAND_INFO).map(([key, info]) => {
          const enabled = config.commands[key as keyof typeof config.commands]
          const isSaving = saving === key

          return (
            <div key={key} className="card flex items-center justify-between">
              <div>
                <h3 className="font-medium text-dark-100">{info.name}</h3>
                <p className="text-sm text-dark-400">{info.description}</p>
              </div>
              <button
                onClick={() => handleToggle(key, !enabled)}
                disabled={isSaving}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  enabled ? 'bg-coral' : 'bg-dark-700'
                } ${isSaving ? 'opacity-50' : ''}`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                    enabled ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>
          )
        })}
      </div>

      <p className="text-sm text-dark-500 mt-6">
        Note: Changes take effect immediately. Disabled commands will show an error message when used.
      </p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-dark-800 rounded w-36 mb-2" />
      <div className="h-4 bg-dark-800 rounded w-64 mb-8" />
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="card flex items-center justify-between">
            <div>
              <div className="h-5 bg-dark-700 rounded w-20 mb-2" />
              <div className="h-4 bg-dark-700 rounded w-48" />
            </div>
            <div className="w-12 h-6 bg-dark-700 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}
