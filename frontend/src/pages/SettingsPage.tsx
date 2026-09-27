import React, { useState } from 'react'
import {
    Settings,
    Server,
    Database,
    ExternalLink,
    Search,
    BookOpen,
    Cpu,
    MessageSquare,
} from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import { fmtInt, fmtINR, fmtPct } from '../lib/format'
import {
    Card,
    SectionTitle,
    ErrorState,
    Spinner,
    Pill,
    EmptyState,
    inputCls,
    InlineNotice,
} from '../components/ui'

/* =========================================================================
   Settings & Status — live backend info (GET /), database row counts,
   the REAL endpoint inventory from /openapi.json, and honest notes about
   integrations that are configured outside the API surface.
   ========================================================================= */

const METHOD_CLS: Record<string, string> = {
    get: 'bg-emerald-100 text-emerald-800',
    post: 'bg-amber-100 text-amber-800',
    put: 'bg-blue-100 text-blue-800',
    delete: 'bg-rose-100 text-rose-800',
}

export default function SettingsPage() {
    const { zones, alerts, actions, root, error: storeError, refresh } = useStore()
    const openapi = useAsync(() => api.getOpenAPI(), [])
    const snapshots = useAsync(() => api.getNRWSummary(), [])
    const revenue = useAsync(() => api.getRevenue(), [])
    const profile = useAsync(() => api.getTownProfile(), [])
    const [filter, setFilter] = useState('')

    const endpoints = React.useMemo(() => {
        const paths = (openapi.data?.paths || {}) as Record<string, Record<string, unknown>>
        const rows: { method: string; path: string }[] = []
        for (const [p, methods] of Object.entries(paths)) {
            for (const m of Object.keys(methods)) rows.push({ method: m.toUpperCase(), path: p })
        }
        rows.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method))
        const q = filter.trim().toLowerCase()
        return q ? rows.filter((r) => r.path.toLowerCase().includes(q) || r.method.toLowerCase().includes(q)) : rows
    }, [openapi.data, filter])

    if (storeError) return <ErrorState error={storeError} onRetry={refresh} />

    return (
        <div className="space-y-6">
            {/* backend status */}
            <div className="grid md:grid-cols-2 gap-6">
                <Card>
                    <SectionTitle icon={Server} right={<Pill className={root ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}>
                        {root ? root.status.toUpperCase() : 'UNREACHABLE'}
                    </Pill>}>
                        API Engine
                    </SectionTitle>
                    {root ? (
                        <div className="space-y-2 text-xs">
                            <Row k="Platform" v={root.platform} />
                            <Row k="Version" v={root.version} />
                            <Row k="Base URL" v={api.API_BASE} mono />
                            <Row k="OpenAPI docs" v={`${api.API_BASE}${root.docs}`} mono />
                            <a
                                href={`${api.API_BASE}${root.docs}`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center space-x-1.5 bg-[#1c1917] hover:bg-stone-800 text-white px-3 py-2 rounded-lg text-xs font-medium transition-all mt-1"
                            >
                                <BookOpen className="w-3.5 h-3.5" />
                                <span>Open Swagger UI</span>
                                <ExternalLink className="w-3 h-3" />
                            </a>
                        </div>
                    ) : (
                        <ErrorState error={storeError || 'Backend unreachable'} onRetry={refresh} />
                    )}
                </Card>

                <Card>
                    <SectionTitle icon={Database}>Database (live counts)</SectionTitle>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                        <Cell label="Zones" value={fmtInt(zones.length)} />
                        <Cell label="Alerts" value={fmtInt(alerts.length)} />
                        <Cell
                            label="NRW snapshots"
                            value={snapshots.data ? fmtInt(snapshots.data.length) : '…'}
                        />
                        <Cell label="Actions" value={fmtInt(actions.length)} />
                        <Cell
                            label="Revenue entries"
                            value={revenue.data ? fmtInt(revenue.data.length) : '…'}
                        />
                        <Cell
                            label="Investigations (memory)"
                            value={alerts.length >= 0 ? 'via /agent/memory' : '…'}
                            small
                        />
                    </div>
                    {profile.data && (
                        <div className="mt-3 p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb] text-[11px] space-y-1">
                            <div className="font-bold text-stone-800">
                                Town anchor: {profile.data.town_name} · {fmtPct(profile.data.total_nrw_percent)} NRW ·{' '}
                                {fmtINR(profile.data.estimated_annual_loss_inr, 1)}/yr
                            </div>
                            <div className="text-stone-500">{profile.data.data_source}</div>
                        </div>
                    )}
                </Card>
            </div>

            {/* integrations — honest */}
            <div className="grid md:grid-cols-2 gap-6">
                <Card>
                    <SectionTitle icon={Cpu}>AI model (Groq)</SectionTitle>
                    <div className="space-y-2 text-xs text-stone-600 leading-relaxed">
                        <div className="flex items-center justify-between">
                            <span>gpt-oss-20b via Groq tool-loop</span>
                            <Pill className="bg-blue-100 text-blue-800">backend/.env</Pill>
                        </div>
                        <p>
                            Live availability is only provable by running the agent — the Copilot
                            page shows <span className="font-mono">ai_available</span> per run and
                            an explicit fallback banner when the key is missing or rejected.
                        </p>
                        <a
                            href="/app/copilot"
                            className="inline-block text-[11px] font-semibold text-stone-900 underline"
                            onClick={(e) => {
                                e.preventDefault()
                                window.location.href = '/app/copilot'
                            }}
                        >
                            Verify a live run →
                        </a>
                    </div>
                </Card>

                <Card>
                    <SectionTitle icon={MessageSquare}>Notifications (Twilio)</SectionTitle>
                    <InlineNotice tone="amber" title="Not configured — mock fallback">
                        SMS/WhatsApp dispatch notifications run through the documented mock fallback
                        because Twilio credentials are unset in this deployment (see README
                        limitations). Actions, approvals and revenue logging are unaffected.
                    </InlineNotice>
                </Card>
            </div>

            {/* live endpoint inventory */}
            <Card>
                <SectionTitle
                    icon={Settings}
                    right={
                        <div className="relative">
                            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-stone-400" />
                            <input
                                value={filter}
                                onChange={(e) => setFilter(e.target.value)}
                                placeholder="Filter endpoints…"
                                className="pl-8 pr-3 py-1.5 bg-white border border-[#dad6cb] rounded-lg text-xs w-56 focus:outline-none focus:ring-1 focus:ring-stone-400"
                            />
                        </div>
                    }
                >
                    Endpoint inventory — GET /openapi.json
                </SectionTitle>
                {openapi.loading && <Spinner label="Loading schema…" />}
                {openapi.error && <ErrorState error={openapi.error} onRetry={openapi.reload} />}
                {openapi.data && endpoints.length === 0 && (
                    <EmptyState title="No endpoints match the filter" />
                )}
                {endpoints.length > 0 && (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {endpoints.map((e) => (
                            <div
                                key={`${e.method} ${e.path}`}
                                className="flex items-center space-x-2 p-2 rounded-lg border border-[#dad6cb] bg-[#fbfaf8]"
                            >
                                <span
                                    className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${METHOD_CLS[e.method.toLowerCase()] || 'bg-stone-200 text-stone-700'}`}
                                >
                                    {e.method}
                                </span>
                                <span className="font-mono text-[11px] text-stone-700 truncate">
                                    {e.path}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        </div>
    )
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
    return (
        <div className="flex items-center justify-between p-2 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
            <span className="text-[11px] text-stone-500">{k}</span>
            <span className={`text-[11px] font-semibold text-stone-800 text-right ${mono ? 'font-mono' : ''}`}>
                {v}
            </span>
        </div>
    )
}

function Cell({ label, value, small, mono }: { label: string; value: string; small?: boolean; mono?: boolean }) {
    return (
        <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
            <div className="text-[10px] uppercase text-stone-500 font-semibold">{label}</div>
            <div className={`font-bold text-stone-900 mt-0.5 ${small ? 'text-xs' : 'text-lg'} ${mono ? 'font-mono' : ''}`}>
                {value}
            </div>
        </div>
    )
}
