import React, { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    TrendingDown,
    DollarSign,
    AlertTriangle,
    Zap,
    MapPin,
    ChevronRight,
    Crosshair,
    Receipt,
    UserCheck,
    Activity,
} from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import {
    fmtINR,
    fmtPct,
    fmtML,
    fmtInt,
    fmtDateTime,
    severityClass,
    zoneStatus,
} from '../lib/format'
import { latestPerZone, townSeries, zoneSeries } from '../lib/derive'
import { Card, SectionTitle, ErrorState, Spinner, Pill, EmptyState } from '../components/ui'
import { LineChart } from '../components/Charts'

/* =========================================================================
   Dashboard overview — every KPI computed from /nrw/summary,
   /alerts, /actions and /data/town-profile. Zero mock arrays.
   ========================================================================= */

export default function DashboardPage() {
    const navigate = useNavigate()
    const { zones, alerts, actions, refresh } = useStore()
    const snaps = useAsync(() => api.getNRWSummary(), [])
    const town = useAsync(() => api.getTownProfile(), [])

    const zoneById = useMemo(() => new Map(zones.map((z) => [z.id, z])), [zones])
    const anchor = town.data?.total_nrw_percent ?? 55.0

    const series = useMemo(() => zoneSeries(snaps.data ?? []), [snaps.data])
    const townPts = useMemo(() => townSeries(snaps.data ?? []), [snaps.data])
    const latest = useMemo(() => latestPerZone(snaps.data ?? []), [snaps.data])

    const current = townPts.length > 0 ? townPts[townPts.length - 1] : null
    const previous = townPts.length > 1 ? townPts[0] : null

    const dailyRevenueRisk = useMemo(() => {
        let total = 0
        for (const [zoneId, snap] of latest) {
            const tariff = zoneById.get(zoneId)?.tariff_rate ?? 0.005
            total += snap.loss_litres * tariff
        }
        return total
    }, [latest, zoneById])

    const activeAlerts = alerts.filter((a) => a.status === 'ACTIVE')
    const critical = activeAlerts.filter((a) => a.severity.toUpperCase() === 'CRITICAL').length
    const high = activeAlerts.filter((a) => a.severity.toUpperCase() === 'HIGH').length
    const pending = actions.filter((a) => a.status === 'PENDING').length

    const coverage = zones.length > 0 ? (latest.size / zones.length) * 100 : 0
    const delta = current && previous ? current.nrw - previous.nrw : null

    const worstZone = useMemo(() => {
        let worst: api.NRWSnapshot | null = null
        for (const s of latest.values()) {
            if (!worst || s.nrw_percentage > worst.nrw_percentage) worst = s
        }
        return worst
    }, [latest])

    if (snaps.loading || town.loading) return <Spinner label="Loading dashboard…" />
    if (snaps.error)
        return <ErrorState error={snaps.error} onRetry={() => { snaps.reload(); refresh() }} />

    return (
        <div className="space-y-6">
            {/* -------------------------------------------------- KPI cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <KpiCard
                    label="Town NRW Loss Rate"
                    icon={TrendingDown}
                    iconCls="text-emerald-600"
                    value={current ? fmtPct(current.nrw) : '—'}
                    sub={
                        current
                            ? `${delta === null ? '—' : delta >= 0 ? '+' : ''}${delta?.toFixed(1)} pp since ${townPts.length} snapshots ago · anchor ${fmtPct(anchor)}`
                            : 'no snapshots'
                    }
                    subCls="text-emerald-700"
                />
                <KpiCard
                    label="Daily Revenue at Risk"
                    icon={DollarSign}
                    iconCls="text-stone-600"
                    value={`${fmtINR(dailyRevenueRisk)}/day`}
                    sub={`Town anchor: ${fmtINR(town.data?.estimated_annual_loss_inr, 1)}/yr`}
                    subCls="text-stone-600"
                />
                <KpiCard
                    label="Active Leak Alerts"
                    icon={AlertTriangle}
                    iconCls="text-amber-600"
                    value={String(activeAlerts.length)}
                    sub={
                        activeAlerts.length
                            ? `${critical} critical, ${high} high · rest medium/low`
                            : 'no active alerts in DB'
                    }
                    subCls={activeAlerts.length ? 'text-amber-700' : 'text-stone-500'}
                />
                <KpiCard
                    label="Telemetry Coverage"
                    icon={Zap}
                    iconCls="text-blue-600"
                    value={fmtPct(coverage, 0)}
                    sub={`${latest.size} / ${zones.length} zones reporting this week`}
                    subCls="text-blue-700"
                />
            </div>

            {/* ------------------------------------- trend chart + alerts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="lg:col-span-2">
                    <SectionTitle
                        icon={Activity}
                        right={
                            <span className="text-[10px] text-stone-400">
                                source: GET /nrw/summary · weekly snapshots
                            </span>
                        }
                    >
                        Town NRW Trend vs {fmtPct(anchor)} Anchor
                    </SectionTitle>
                    {townPts.length > 1 ? (
                        <LineChart
                            points={townPts.map((p) => ({ t: p.t, value: p.nrw }))}
                            anchor={anchor}
                            anchorLabel={`Lucknow anchor ${fmtPct(anchor)}`}
                        />
                    ) : (
                        <EmptyState
                            title="Not enough snapshots for a trend"
                            hint="At least two weekly NRWSnapshot batches are needed to draw the town trend."
                        />
                    )}
                    {townPts.length > 0 && (
                        <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
                            <div className="p-2.5 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                                <div className="text-[10px] uppercase text-stone-500 font-semibold">
                                    Latest inflow
                                </div>
                                <div className="font-bold text-stone-800">
                                    {current ? fmtML(current.inflow) : '—'}/day
                                </div>
                            </div>
                            <div className="p-2.5 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                                <div className="text-[10px] uppercase text-stone-500 font-semibold">
                                    Latest loss
                                </div>
                                <div className="font-bold text-rose-700">
                                    {current ? fmtML(current.loss) : '—'}/day
                                </div>
                            </div>
                            <div className="p-2.5 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                                <div className="text-[10px] uppercase text-stone-500 font-semibold">
                                    Worst DMA
                                </div>
                                <div className="font-bold text-rose-700">
                                    {worstZone
                                        ? `${zoneById.get(worstZone.zone_id)?.name || worstZone.zone_id} · ${fmtPct(worstZone.nrw_percentage)}`
                                        : '—'}
                                </div>
                            </div>
                        </div>
                    )}
                </Card>

                <Card>
                    <SectionTitle
                        right={
                            <button
                                onClick={() => navigate('/app/alerts')}
                                className="text-xs font-medium text-stone-600 hover:text-stone-900"
                            >
                                View all →
                            </button>
                        }
                    >
                        Recent Alerts
                    </SectionTitle>
                    {alerts.length === 0 ? (
                        <EmptyState
                            icon={AlertTriangle}
                            title="No alerts recorded"
                            hint="Leak alerts appear here after POST /detect or water-balance runs."
                        />
                    ) : (
                        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                            {alerts.slice(0, 6).map((a) => (
                                <button
                                    key={a.id}
                                    onClick={() => navigate('/app/alerts')}
                                    className="w-full text-left p-3 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] hover:bg-[#f3f0e8] transition-colors space-y-1"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs font-bold text-stone-800">
                                            ALT-{a.id} · {zoneById.get(a.zone_id)?.name || a.zone_id}
                                        </span>
                                        <Pill className={severityClass(a.severity)}>{a.severity}</Pill>
                                    </div>
                                    <div className="text-[11px] text-stone-500">
                                        {fmtML(a.estimated_loss_litres)} loss ·{' '}
                                        {Math.round(a.confidence_score * 100)}% confidence ·{' '}
                                        {fmtDateTime(a.timestamp)}
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </Card>
            </div>

            {/* --------------------------- quick actions + DMA overview */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card>
                    <SectionTitle icon={Zap}>Quick Municipal Actions</SectionTitle>
                    <div className="space-y-2">
                        <QuickAction
                            onClick={() => navigate('/app/leak')}
                            title="Run PPA Sensor Localization"
                            hint="Pinpoint physical bursts on the simulated pressure grid"
                            icon={Crosshair}
                        />
                        <QuickAction
                            onClick={() => navigate('/app/billing')}
                            title="Run Commercial Loss Audit"
                            hint="ML scoring of billing anomalies per consumer"
                            icon={Receipt}
                        />
                        <QuickAction
                            onClick={() => navigate('/app/revenue')}
                            title="Approve Pending Dispatch Actions"
                            hint={
                                pending > 0
                                    ? `${pending} dispatch request${pending > 1 ? 's' : ''} waiting approval`
                                    : 'No dispatch requests waiting approval'
                            }
                            icon={UserCheck}
                        />
                    </div>
                </Card>

                <Card className="lg:col-span-2">
                    <SectionTitle
                        icon={MapPin}
                        right={
                            <button
                                onClick={() => navigate('/app/zones')}
                                className="text-xs font-medium text-stone-600 hover:text-stone-900"
                            >
                                View All Zones →
                            </button>
                        }
                    >
                        District Metered Areas (DMAs) Overview
                    </SectionTitle>
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                        {zones.map((z) => {
                            const snap = latest.get(z.id)
                            const nrw = snap?.nrw_percentage ?? null
                            const st = zoneStatus(nrw, anchor)
                            return (
                                <button
                                    key={z.id}
                                    onClick={() => navigate(`/app/zones?zone=${z.id}`)}
                                    className="p-3.5 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] hover:bg-[#f3f0e8] transition-colors text-left flex justify-between items-center"
                                >
                                    <div>
                                        <div className="text-xs font-bold text-stone-800">{z.name}</div>
                                        <div className="text-[11px] text-stone-500 mt-0.5">
                                            Flow: {snap ? fmtML(snap.inflow_litres, 1) : '—'}/d | NRW:{' '}
                                            <span className="font-semibold">
                                                {nrw !== null ? fmtPct(nrw) : '—'}
                                            </span>
                                        </div>
                                    </div>
                                    <span
                                        className={`px-2 py-0.5 text-[9px] font-semibold rounded-full ${st.cls}`}
                                    >
                                        {st.label}
                                    </span>
                                </button>
                            )
                        })}
                    </div>
                    <div className="text-[10px] text-stone-400 mt-3">
                        NRW per zone from latest NRWSnapshot · status measured against the{' '}
                        {fmtPct(anchor)} Lucknow anchor
                    </div>
                </Card>
            </div>
        </div>
    )
}

/* ------------------------------------------------------------- helpers */

function KpiCard({
    label,
    icon: Icon,
    iconCls,
    value,
    sub,
    subCls,
}: {
    label: string
    icon: React.ComponentType<{ className?: string }>
    iconCls: string
    value: string
    sub: string
    subCls: string
}) {
    return (
        <div className="bg-gradient-to-br from-white to-[#f7f5f0] p-5 rounded-xl border border-[#dad6cb] shadow-sm flex flex-col justify-between">
            <div className="flex items-center justify-between text-stone-500">
                <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
                <Icon className={`w-4 h-4 ${iconCls}`} />
            </div>
            <div className="mt-3">
                <div className="text-2xl font-bold text-stone-900">{value}</div>
                <div className={`text-xs mt-1 font-medium ${subCls}`}>{sub}</div>
            </div>
        </div>
    )
}

function QuickAction({
    onClick,
    title,
    hint,
    icon: Icon,
}: {
    onClick: () => void
    title: string
    hint: string
    icon: React.ComponentType<{ className?: string }>
}) {
    return (
        <button
            onClick={onClick}
            className="w-full flex items-center justify-between p-3 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] hover:bg-[#f3f0e8] transition-colors text-left"
        >
            <div className="flex items-start space-x-2.5">
                <Icon className="w-4 h-4 text-stone-500 mt-0.5" />
                <div>
                    <div className="text-xs font-semibold text-stone-800">{title}</div>
                    <div className="text-[11px] text-stone-500">{hint}</div>
                </div>
            </div>
            <ChevronRight className="w-4 h-4 text-stone-400" />
        </button>
    )
}
