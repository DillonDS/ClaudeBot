'use client'

import { use } from 'react'
import Link from 'next/link'
import { useGuildConfig } from '@/hooks/useGuildConfig'
import { useLiveStats } from '@/hooks/useLiveStats'

interface PageProps {
  params: Promise<{ guildId: string }>
}

export default function GuildOverviewPage({ params }: PageProps) {
  const { guildId } = use(params)
  const { config, isLoading: configLoading } = useGuildConfig(guildId)
  const { stats, isLoading: statsLoading } = useLiveStats(guildId)

  if (configLoading) {
    return <LoadingSkeleton />
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-dark-50">{config?.guildName || 'Server'}</h1>
        <p className="text-dark-400">Overview and quick settings</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Messages Cached"
          value={statsLoading ? '...' : stats?.messagesCached?.toString() || '0'}
        />
        <StatCard
          label="Tokens Used"
          value={statsLoading ? '...' : stats?.tokensUsed?.toLocaleString() || '0'}
        />
        <StatCard
          label="Bot Latency"
          value={statsLoading ? '...' : `${stats?.botLatency || 0}ms`}
        />
        <StatCard
          label="Bot Uptime"
          value={statsLoading ? '...' : stats?.botUptime || 'Unknown'}
        />
      </div>

      {/* Quick Actions */}
      <h2 className="text-lg font-semibold text-dark-100 mb-4">Quick Actions</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <QuickActionCard
          href={`/dashboard/guild/${guildId}/config`}
          title="Configuration"
          description="Adjust response thresholds, token limits, and more"
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          }
        />
        <QuickActionCard
          href={`/dashboard/guild/${guildId}/commands`}
          title="Commands"
          description="Enable or disable individual slash commands"
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          }
        />
        <QuickActionCard
          href={`/dashboard/guild/${guildId}/prompt`}
          title="System Prompt"
          description="Customize the bot's personality and behavior"
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          }
        />
      </div>

      {/* Current Settings Summary */}
      {config && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-dark-100 mb-4">Current Settings</h2>
          <div className="card">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-dark-500">Temperature</p>
                <p className="text-dark-100 font-medium">{config.settings.temperature}</p>
              </div>
              <div>
                <p className="text-dark-500">Score Threshold</p>
                <p className="text-dark-100 font-medium">{config.settings.scoreThreshold}</p>
              </div>
              <div>
                <p className="text-dark-500">Max Response Tokens</p>
                <p className="text-dark-100 font-medium">{config.settings.maxResponseTokens}</p>
              </div>
              <div>
                <p className="text-dark-500">Rate Limit</p>
                <p className="text-dark-100 font-medium">{config.settings.rateLimitSeconds}s</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <p className="text-dark-500 text-sm mb-1">{label}</p>
      <p className="text-2xl font-bold text-dark-50">{value}</p>
    </div>
  )
}

function QuickActionCard({
  href,
  title,
  description,
  icon,
}: {
  href: string
  title: string
  description: string
  icon: React.ReactNode
}) {
  return (
    <Link href={href} className="card hover:border-coral transition-colors group">
      <div className="flex items-start gap-4">
        <div className="p-2 rounded-lg bg-dark-800 text-coral group-hover:bg-coral group-hover:text-white transition-colors">
          {icon}
        </div>
        <div>
          <h3 className="font-medium text-dark-100 group-hover:text-coral transition-colors">
            {title}
          </h3>
          <p className="text-sm text-dark-400 mt-1">{description}</p>
        </div>
      </div>
    </Link>
  )
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-dark-800 rounded w-48 mb-2" />
      <div className="h-4 bg-dark-800 rounded w-64 mb-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card">
            <div className="h-4 bg-dark-700 rounded w-20 mb-2" />
            <div className="h-8 bg-dark-700 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  )
}
