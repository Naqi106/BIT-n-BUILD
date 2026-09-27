import React, { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
    MapPin,
    Bot,
    Receipt,
    Crosshair,
    TrendingDown,
    History,
    Satellite,
    ChevronRight,
} from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import {
    fmtML,
    fmtPct,
    fmtINR,
    fmtInt,
    fmtDate,
    fmtDateTime,
    zoneStatus,
} from '../lib/format'
import { zoneSeries } from '../lib/derive'
import {
    Card,
    SectionTitle,
    ErrorState,
    Spinner,
    Pill,
    EmptyState,
    StatGrid,
    InlineNotice,
    btnPrimary,
    btnSecondary,
} from '../components/ui'
import { Sparkline } from '../components/Charts'

/* =========================================================================
   Zones & DMAs — zone selector + full detail panel:
   GET /nrw/summary (history), /data/investigations (flag banner),
   /data/nrw-forecast, /revenue/payback, /audit/billing totals,
   /data/satellite/ndwi.
   ========================================================================= */

interface ZoneBundle {
    snaps: api.NRWSnapshot[]
    memory: api.InvestigationMemory
    forecast: api.NRWForecast
    payback: api.Payback
    billing: api.PaginatedBilling
    ndwi: api.NDWIResponse
}

function loadZoneBundle(zoneId: string): Promise<ZoneBundle> {
    return Promise.all([
        api.getNRWSummary(),
        api.getInvestigations(zoneId),
        api.getForecast(zoneId),
        api.getPayback(zoneId),
        api.getBilling(zoneId, 1, 0),
        api.getNDWI(zoneId),
    ]).then(([snaps, memory, forecast, payback, billing, ndwi]) => ({
        snaps,
        memory,
        forecast,
        payback,
        billing,
        ndwi,
    }))
}

export default function ZonesPage() {
    const navigate = useNavigate()
    const { zones, refresh, error: storeError } = useStore()
    const [params, setParams] = useSearchParams()
    const selected = params.get('zone') || zones[0]?.id || ''

    const anchor = 55.0
    const snapsAll = useAsync(() => api.getNRWSummary(), [])
    const bundle = useAsync<ZoneBundle | null>(
        () => (selected ? loadZoneBundle(selected) : Promise.resolve(null)),
        [selected],
    )

    const series = useMemo(() => zoneSeries(snapsAll.data ?? []), [snapsAll.data])
    const latest = useMemo(() => {
        const m = new Map<string, api.NRWSnapshot>()
        for (const [zid, zs] of series) m.set(zid, zs.latest)
        return m
    }, [series])

    const select = (zoneId: string) => setParams({ zone: zoneId })

    if (storeError) return <ErrorState error={storeError} onRetry={refresh} />
    if (zones.length === 0)
        return <Spinner label={snapsAll.loading ? 'Loading zones…' : 'No zones returned by API'} />

    const zone = zones.find((z) => z.id === selected) || zones[0]

    return (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* ---------------------------------------------- zone list */}
            <Card className="lg:col-span-1 !p-3 space-y-1 h-max">
                <div className="px-2 py-1.5 text-[10px] font-semibold tracking-wider text-stone-500 uppercase">
                    12 District Metered Areas
                </div>
                {zones.map((z) => {
                    const snap = latest.get(z.id)
                    const nrw = snap?.nrw_percentage ?? null
                    const st = zoneStatus(nrw, anchor)
                    const active = z.id === zone.id
                    return (
                        <button
                            key={z.id}
                            onClick={() => select(z.id)}
                            className={`w-full text-left px-3 py-2.5 rounded-lg transition-all ${
                                active
                                    ? 'bg-[#1c1917] text-white shadow-sm'
                                    : 'text-stone-700 hover:bg-[#dedad0]'
                            }`}
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold">{z.name}</span>
                                <span
                                    className={`px-1.5 py-0.5 text-[9px] font-bold rounded-full ${active ? 'bg-stone-700 text-stone-200' : st.cls}`}
                                >
                                    {nrw !== null ? fmtPct(nrw, 0) : '—'}
                                </span>
                            </div>
                            <div className={`text-[10px] mt-0.5 ${active ? 'text-stone-400' : 'text-stone-500'}`}>
                                {z.id} · {fmtInt(z.connection_count)} connections
                            </div>
                        </button>
                    )
                })}
            </Card>

            {/* ------------------------------------------- detail panel */}
            <div className="lg:col-span-4 space-y-6">
                {bundle.loading && <Spinner label={`Loading ${zone.name}…`} />}
                {bundle.error && <ErrorState error={bundle.error} onRetry={bundle.reload} />}

                {bundle.data && (
                    <>
                        {/* header + flag banner */}
                        <Card>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <div className="flex items-center space-x-2">
                                        <MapPin className="w-4 h-4 text-stone-500" />
                                        <h2 className="text-lg font-bold text-stone-900">{zone.name}</h2>
                                        <Pill
                                            className={zoneStatus(
                                                latest.get(zone.id)?.nrw_percentage ?? null,
                                                anchor,
                                            ).cls}
                                        >
                                            {zoneStatus(latest.get(zone.id)?.nrw_percentage ?? null, anchor).label}
                                        </Pill>
                                    </div>
                                    <div className="text-xs text-stone-500 mt-1">
                                        {zone.id} · {zone.pipe_length_km} km mains ·{' '}
                                        {fmtInt(zone.connection_count)} connections ·{' '}
                                        {zone.avg_pressure_bar} bar avg · tariff ₹{zone.tariff_rate}/L
                                    </div>
                                </div>
                                <div className="flex space-x-2">
                                    <button
                                        onClick={() => navigate(`/app/copilot?zone=${zone.id}`)}
                                        className="inline-flex items-center space-x-1.5 bg-[#1c1917] hover:bg-stone-800 text-white px-3 py-2 rounded-lg text-xs font-medium transition-all"
                                    >
                                        <Bot className="w-3.5 h-3.5" />
                                        <span>Ask Copilot</span>
                                    </button>
                                    <button
                                        onClick={() => navigate(`/app/billing?zone=${zone.id}`)}
                                        className="inline-flex items-center space-x-1.5 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] text-stone-700 px-3 py-2 rounded-lg text-xs font-medium transition-all"
                                    >
                                        <Receipt className="w-3.5 h-3.5" />
                                        <span>Billing audit</span>
                                    </button>
                                    <button
                                        onClick={() => navigate(`/app/leak?zone=${zone.id}`)}
                                        className="inline-flex items-center space-x-1.5 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] text-stone-700 px-3 py-2 rounded-lg text-xs font-medium transition-all"
                                    >
                                        <Crosshair className="w-3.5 h-3.5" />
                                        <span>PPA</span>
                                    </button>
                                </div>
                            </div>

                            {bundle.data.memory.previously_flagged && (
                                <div className="mt-4">
                                    <InlineNotice tone="amber" title="Previously flagged by AI Copilot">
                                        {bundle.data.memory.note} ({bundle.data.memory.investigation_count}{' '}
                                        investigation
                                        {bundle.data.memory.investigation_count === 1 ? '' : 's'}
                                        {bundle.data.memory.last_flagged_at
                                            ? `, last ${fmtDate(bundle.data.memory.last_flagged_at)}`
                                            : ''}
                                        )
                                    </InlineNotice>
                                </div>
                            )}
                        </Card>

                        {/* stat grid — latest snapshot */}
                        <ZoneStats zone={zone} bundle={bundle.data} anchor={anchor} />

                        {/* forecast + payback */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <ForecastCard forecast={bundle.data.forecast} />
                            <PaybackCard payback={bundle.data.payback} />
                        </div>

                        {/* history + satellite + memory */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <Card>
                                <SectionTitle icon={TrendingDown}>NRW History</SectionTitle>
                                <ZoneSpark zoneId={zone.id} snaps={bundle.data.snaps} />
                            </Card>
                            <Card>
                                <SectionTitle icon={Satellite}>Satellite Second Opinion</SectionTitle>
                                <SatelliteCard ndwi={bundle.data.ndwi} />
                            </Card>
                            <Card>
                                <SectionTitle icon={History}>Investigation History</SectionTitle>
                                {bundle.data.memory.entries.length === 0 ? (
                                    <EmptyState
                                        icon={History}
                                        title="No investigations yet"
                                        hint="Copilot runs are recorded here automatically."
                                    />
                                ) : (
                                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                                        {bundle.data.memory.entries.map((e) => (
                                            <div
                                                key={e.id}
                                                className="p-2.5 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] space-y-1"
                                            >
                                                <div className="text-[11px] text-stone-700 leading-snug">
                                                    {e.summary}
                                                </div>
                                                <div className="text-[10px] text-stone-400">
                                                    {fmtDateTime(e.timestamp)}
                                                    {e.action_taken ? ` · ${e.action_taken}` : ''}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </Card>
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}

/* -------------------------------------------------------------- widgets */

function ZoneStats({ zone, bundle, anchor }: { zone: api.Zone; bundle: ZoneBundle; anchor: number }) {
    const snaps = zoneSeries(bundle.snaps).get(zone.id)
    const snap = snaps?.latest
    const nrw = snap?.nrw_percentage ?? null
    return (
        <Card>
            <SectionTitle
                right={
                    snap ? (
                        <span className="text-[10px] text-stone-400">
                            snapshot {fmtDateTime(snap.timestamp)}
                        </span>
                    ) : null
                }
            >
                Current Water Balance
            </SectionTitle>
            <StatGrid
                items={[
                    {
                        label: 'NRW',
                        value: nrw !== null ? fmtPct(nrw) : '—',
                        sub:
                            nrw !== null
                                ? `${nrw > anchor ? '+' : ''}${(nrw - anchor).toFixed(1)} pp vs ${fmtPct(anchor)} anchor`
                                : 'no snapshot',
                    },
                    { label: 'Inflow', value: snap ? `${fmtML(snap.inflow_litres)}/d` : '—' },
                    {
                        label: 'Physical + app. loss',
                        value: snap ? `${fmtML(snap.loss_litres)}/d` : '—',
                        sub: snap ? `${fmtINR(snap.loss_litres * zone.tariff_rate)}/day at risk` : undefined,
                    },
                    {
                        label: 'Billed',
                        value: snap ? `${fmtML(snap.billed_litres)}/d` : '—',
                        sub: snap && snap.inflow_litres > 0 ? `${fmtPct((snap.billed_litres / snap.inflow_litres) * 100)} of inflow` : undefined,
                    },
                ]}
            />
        </Card>
    )
}

function ForecastCard({ forecast }: { forecast: api.NRWForecast }) {
    return (
        <Card>
            <SectionTitle icon={TrendingDown} right={<Pill className="bg-stone-800 text-stone-100">30-day</Pill>}>
                NRW Trend Forecast
            </SectionTitle>
            {!forecast.is_sufficient ? (
                <InlineNotice tone="blue" title="Insufficient history">
                    {forecast.message ||
                        `Need ${forecast.required_observations ?? '?'} observations, have ${forecast.observations}.`}
                </InlineNotice>
            ) : (
                <div className="space-y-3">
                    <div className="flex items-center space-x-3">
                        <Pill
                            className={
                                forecast.direction === 'WORSENING'
                                    ? 'bg-rose-100 text-rose-800'
                                    : forecast.direction === 'IMPROVING'
                                      ? 'bg-emerald-100 text-emerald-800'
                                      : 'bg-stone-200 text-stone-700'
                            }
                        >
                            {forecast.direction || 'FLAT'}
                        </Pill>
                        <span className="text-[11px] text-stone-500">
                            confidence: {forecast.trend_confidence || '—'} · method {forecast.method || '—'}
                        </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                            <div className="text-[10px] uppercase text-stone-500 font-semibold">Current NRW</div>
                            <div className="font-bold text-stone-900">
                                {forecast.current_nrw_pct !== null && forecast.current_nrw_pct !== undefined
                                    ? fmtPct(forecast.current_nrw_pct)
                                    : '—'}
                            </div>
                        </div>
                        <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                            <div className="text-[10px] uppercase text-stone-500 font-semibold">Projected (30d)</div>
                            <div className="font-bold text-stone-900">
                                {forecast.projected_nrw_pct !== null && forecast.projected_nrw_pct !== undefined
                                    ? fmtPct(forecast.projected_nrw_pct)
                                    : '—'}
                            </div>
                        </div>
                        <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                            <div className="text-[10px] uppercase text-stone-500 font-semibold">Projected loss</div>
                            <div className="font-bold text-rose-700">
                                {forecast.projected_loss_litres !== null && forecast.projected_loss_litres !== undefined
                                    ? `${fmtML(forecast.projected_loss_litres)} / 30d`
                                    : '—'}
                            </div>
                        </div>
                        <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                            <div className="text-[10px] uppercase text-stone-500 font-semibold">₹ at stake</div>
                            <div className="font-bold text-rose-700">
                                {forecast.projected_loss_rupees !== null && forecast.projected_loss_rupees !== undefined
                                    ? fmtINR(forecast.projected_loss_rupees, 1)
                                    : '—'}
                            </div>
                        </div>
                    </div>
                    {forecast.interpretation && (
                        <p className="text-[11px] leading-relaxed text-stone-600">{forecast.interpretation}</p>
                    )}
                </div>
            )}
        </Card>
    )
}

function PaybackCard({ payback }: { payback: api.Payback }) {
    const honest = payback.data_source !== 'DEFAULT_FALLBACK'
    return (
        <Card>
            <SectionTitle
                right={
                    <Pill
                        className={honest ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}
                        title="data_source returned by the API"
                    >
                        {payback.data_source}
                    </Pill>
                }
            >
                Repair Payback
            </SectionTitle>
            {!honest && (
                <div className="mb-3">
                    <InlineNotice tone="amber" title="Simulated input — no active alert">
                        This zone has no ACTIVE leak alert, so the engine used its default loss input.
                        Figures are illustrative until an alert exists.
                    </InlineNotice>
                </div>
            )}
            <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                    <div className="text-[10px] uppercase text-stone-500 font-semibold">Daily loss used</div>
                    <div className="font-bold text-stone-900">{fmtML(payback.daily_loss_litres)} L</div>
                </div>
                <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                    <div className="text-[10px] uppercase text-stone-500 font-semibold">Daily revenue loss</div>
                    <div className="font-bold text-rose-700">{fmtINR(payback.daily_revenue_loss)}</div>
                </div>
                <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                    <div className="text-[10px] uppercase text-stone-500 font-semibold">Est. repair cost</div>
                    <div className="font-bold text-stone-900">{fmtINR(payback.estimated_repair_cost, 2)}</div>
                </div>
                <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                    <div className="text-[10px] uppercase text-stone-500 font-semibold">Payback period</div>
                    <div className="font-bold text-emerald-700">
                        {payback.payback_period_days.toFixed(1)} days
                    </div>
                </div>
            </div>
        </Card>
    )
}

function SatelliteCard({ ndwi }: { ndwi: api.NDWIResponse }) {
    return (
        <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
                <Pill className={ndwi.status === 'OK' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}>
                    {ndwi.status}
                </Pill>
                <Pill className="bg-stone-200 text-stone-700">{ndwi.ndwi_status}</Pill>
            </div>
            <p className="text-[11px] leading-relaxed text-stone-600">{ndwi.interpretation}</p>
            {ndwi.message && <p className="text-[11px] text-stone-500">{ndwi.message}</p>}
            <div className="flex flex-wrap gap-1.5">
                {ndwi.flag_sources.map((s) => (
                    <Pill key={s} className="bg-blue-100 text-blue-800">
                        {s}
                    </Pill>
                ))}
            </div>
            <div className="text-[10px] text-stone-400">source: {ndwi.data_source}</div>
        </div>
    )
}

function ZoneSpark({ zoneId, snaps }: { zoneId: string; snaps: api.NRWSnapshot[] }) {
    const zs = zoneSeries(snaps).get(zoneId)
    if (!zs || zs.points.length < 2) {
        return <EmptyState title="No trend data" hint="Fewer than two snapshots for this zone." />
    }
    const values = zs.points.map((p) => p.nrw)
    return (
        <div className="space-y-3">
            <div className="flex items-end justify-between">
                <div>
                    <div className="text-[10px] uppercase text-stone-500 font-semibold">Latest NRW</div>
                    <div className="text-xl font-bold text-stone-900">{fmtPct(zs.latest.nrw_percentage)}</div>
                </div>
                <div className="text-right">
                    <div className="text-[10px] uppercase text-stone-500 font-semibold">First snapshot</div>
                    <div className="text-sm font-semibold text-stone-600">
                        {fmtPct(zs.first.nrw_percentage)}
                    </div>
                </div>
            </div>
            <Sparkline values={values} width={340} height={54} color="#1c1917" />
            <div className="text-[10px] text-stone-400">
                {zs.points.length} weekly snapshots · {fmtDate(zs.first.timestamp)} →{' '}
                {fmtDate(zs.latest.timestamp)}
            </div>
        </div>
    )
}
