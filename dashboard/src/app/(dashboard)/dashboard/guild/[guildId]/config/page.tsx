'use client'

import { use, useState } from 'react'
import { useGuildConfig } from '@/hooks/useGuildConfig'
import { DEFAULT_SETTINGS } from '@/lib/config.types'

interface PageProps {
  params: Promise<{ guildId: string }>
}

export default function ConfigPage({ params }: PageProps) {
  const { guildId } = use(params)
  const { config, isLoading, updateSettings } = useGuildConfig(guildId)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  if (isLoading || !config) {
    return <LoadingSkeleton />
  }

  const handleSave = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    const formData = new FormData(e.currentTarget)
    const newSettings = {
      temperature: parseFloat(formData.get('temperature') as string),
      scoreThreshold: parseInt(formData.get('scoreThreshold') as string),
      maxResponseTokens: parseInt(formData.get('maxResponseTokens') as string),
      rateLimitSeconds: parseInt(formData.get('rateLimitSeconds') as string),
      maxTokensPerChannel: parseInt(formData.get('maxTokensPerChannel') as string),
      messageExpiryDays: parseInt(formData.get('messageExpiryDays') as string),
    }

    try {
      await updateSettings(newSettings)
      setMessage({ type: 'success', text: 'Settings saved successfully!' })
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save settings' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-dark-50">Configuration</h1>
        <p className="text-dark-400">Adjust how ClaudeBot responds in this server</p>
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

      <form onSubmit={handleSave} className="space-y-8">
        {/* Response Settings */}
        <section className="card">
          <h2 className="text-lg font-semibold text-dark-100 mb-6">Response Settings</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="label">
                Temperature
                <span className="text-dark-500 font-normal ml-2">({config.settings.temperature})</span>
              </label>
              <input
                type="range"
                name="temperature"
                min="0"
                max="1"
                step="0.1"
                defaultValue={config.settings.temperature}
                className="w-full"
              />
              <p className="text-xs text-dark-500 mt-1">
                Lower = more focused, Higher = more creative
              </p>
            </div>

            <div>
              <label className="label">
                Score Threshold
                <span className="text-dark-500 font-normal ml-2">({config.settings.scoreThreshold})</span>
              </label>
              <input
                type="range"
                name="scoreThreshold"
                min="1"
                max="10"
                step="1"
                defaultValue={config.settings.scoreThreshold}
                className="w-full"
              />
              <p className="text-xs text-dark-500 mt-1">
                Minimum score (1-10) required for bot to respond
              </p>
            </div>

            <div>
              <label className="label">Max Response Tokens</label>
              <input
                type="number"
                name="maxResponseTokens"
                defaultValue={config.settings.maxResponseTokens}
                min="50"
                max="2000"
                className="input"
              />
              <p className="text-xs text-dark-500 mt-1">
                Maximum length of bot responses (default: {DEFAULT_SETTINGS.maxResponseTokens})
              </p>
            </div>

            <div>
              <label className="label">Rate Limit (seconds)</label>
              <input
                type="number"
                name="rateLimitSeconds"
                defaultValue={config.settings.rateLimitSeconds}
                min="0"
                max="60"
                className="input"
              />
              <p className="text-xs text-dark-500 mt-1">
                Minimum time between responses in a channel
              </p>
            </div>
          </div>
        </section>

        {/* Cache Settings */}
        <section className="card">
          <h2 className="text-lg font-semibold text-dark-100 mb-6">Cache Settings</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="label">Max Tokens Per Channel</label>
              <input
                type="number"
                name="maxTokensPerChannel"
                defaultValue={config.settings.maxTokensPerChannel}
                min="10000"
                max="500000"
                step="10000"
                className="input"
              />
              <p className="text-xs text-dark-500 mt-1">
                Token limit for conversation history per channel
              </p>
            </div>

            <div>
              <label className="label">Message Expiry (days)</label>
              <input
                type="number"
                name="messageExpiryDays"
                defaultValue={config.settings.messageExpiryDays}
                min="1"
                max="365"
                className="input"
              />
              <p className="text-xs text-dark-500 mt-1">
                Auto-delete cached messages older than this
              </p>
            </div>
          </div>
        </section>

        {/* Save Button */}
        <div className="flex items-center gap-4">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          <p className="text-sm text-dark-500">
            Last updated: {new Date(config.updatedAt).toLocaleString()}
          </p>
        </div>
      </form>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-dark-800 rounded w-48 mb-2" />
      <div className="h-4 bg-dark-800 rounded w-72 mb-8" />
      <div className="card mb-6">
        <div className="h-6 bg-dark-700 rounded w-40 mb-6" />
        <div className="grid grid-cols-2 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i}>
              <div className="h-4 bg-dark-700 rounded w-24 mb-2" />
              <div className="h-10 bg-dark-700 rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
