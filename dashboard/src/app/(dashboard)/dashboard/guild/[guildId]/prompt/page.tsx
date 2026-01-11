'use client'

import { use, useState, useEffect } from 'react'
import { useGuildConfig } from '@/hooks/useGuildConfig'
import { DEFAULT_SYSTEM_PROMPT } from '@/lib/config.types'

interface PageProps {
  params: Promise<{ guildId: string }>
}

export default function PromptPage({ params }: PageProps) {
  const { guildId } = use(params)
  const { config, isLoading, updatePrompt } = useGuildConfig(guildId)
  const [prompt, setPrompt] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (config) {
      setPrompt(config.systemPrompt || DEFAULT_SYSTEM_PROMPT)
    }
  }, [config])

  if (isLoading || !config) {
    return <LoadingSkeleton />
  }

  const isCustom = config.systemPrompt !== null
  const hasChanges = prompt !== (config.systemPrompt || DEFAULT_SYSTEM_PROMPT)

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)

    try {
      // If prompt matches default, save as null (use default)
      const promptToSave = prompt.trim() === DEFAULT_SYSTEM_PROMPT.trim() ? null : prompt.trim()
      await updatePrompt(promptToSave)
      setMessage({ type: 'success', text: 'System prompt saved!' })
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save prompt' })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setPrompt(DEFAULT_SYSTEM_PROMPT)
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-dark-50">System Prompt</h1>
        <p className="text-dark-400">Customize how ClaudeBot behaves and responds</p>
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

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h2 className="font-medium text-dark-100">Prompt Editor</h2>
            {isCustom ? (
              <span className="px-2 py-0.5 text-xs rounded bg-coral/10 text-coral">Custom</span>
            ) : (
              <span className="px-2 py-0.5 text-xs rounded bg-dark-700 text-dark-400">Default</span>
            )}
          </div>
          <button
            onClick={handleReset}
            className="btn-ghost text-sm"
            disabled={prompt === DEFAULT_SYSTEM_PROMPT}
          >
            Reset to Default
          </button>
        </div>

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="w-full h-96 input font-mono text-sm resize-none"
          placeholder="Enter system prompt..."
        />

        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-dark-500">
            {prompt.length} characters
          </p>
          <div className="flex items-center gap-3">
            {hasChanges && (
              <span className="text-sm text-coral">Unsaved changes</span>
            )}
            <button
              onClick={handleSave}
              className="btn-primary"
              disabled={saving || !hasChanges}
            >
              {saving ? 'Saving...' : 'Save Prompt'}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-6 card bg-dark-800/50">
        <h3 className="font-medium text-dark-200 mb-2">Tips</h3>
        <ul className="text-sm text-dark-400 space-y-1">
          <li>- Keep the SCORING section to control when the bot responds</li>
          <li>- The [MENTIONED] marker is added automatically when users @mention the bot</li>
          <li>- Use "SCORE: X" format at the end to maintain response filtering</li>
          <li>- Reset to default if something breaks</li>
        </ul>
      </div>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-dark-800 rounded w-44 mb-2" />
      <div className="h-4 bg-dark-800 rounded w-72 mb-8" />
      <div className="card">
        <div className="h-6 bg-dark-700 rounded w-32 mb-4" />
        <div className="h-96 bg-dark-700 rounded" />
      </div>
    </div>
  )
}
