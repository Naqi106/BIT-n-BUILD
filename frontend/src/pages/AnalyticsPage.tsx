import React, { useMemo, useState } from 'react'
import { LineChart as LineChartIcon, BarChart3, Satellite, Bot } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import { fmtPct, fmtML, fmtINR } from '../lib/format'
import { townSeries, zoneSeries } from '../lib/derive'
import {
    Card,
    SectionTitle,
    ErrorState,
    Spinner,
    Pill,
    EmptyState,
    InlineNotice,
    inputCls,
} from '../components/ui'
import type { AsyncState } from '../lib/store'
import { LineChart, BarChart } from '../components/Charts'

/* =========================================================================
   Analytics — real trend charts from /nrw/summary + 30-day projections
   from /data/nrw-forecast (town and per-zone) + Sentinel-2 NDWI second
   opinion. Insufficient data shows the API's own message, never a guess.
   ========================================================================= */

export default function AnalyticsPage() {
    const navigate = useNavigate()
    const { zones } = useStore()
    const [zoneId, setZoneId] = useState('')

    const snaps = useAsync(() => api.getNRWSummary(), [])
    const townForecast = useAsync(() => api.getForecast(), [])
    const profile = useAsync(() => api.getTownProfile(), [])

    const activeZone = zoneId || zones[0]?.id || ''
    const zoneForecast = useAsync<api.NRWForecast | null>(
        () => (activeZone ? api.getForecast(activeZone) : Promise.resolve(null)),
        [activeZone],
    )
    const ndwi = useAsync<api.NDWIResponse | null>(
        () => (activeZone ? api.getNDWI(activeZone) : Promise.resolve(null)),
        [activeZone],
    )

    const anchor = profile.data?.total_nrw_percent ?? 55.0

    const townPts = useMemo(() => townSeries(snaps.data ?? []), [snaps.data])
    const lossPts = useMemo(
        () => townSeries(snaps.data ?? []).map((p) => ({ t: p.t, value: p.loss / 1e6 })),
        [snaps.data],
    )
    const zoneBars = useMemo(() => {
        const series = zoneSeries(snaps.data ?? [])
        return zones
            .map((z) => {
                const zs = series.get(z.id)
                return zs ? { label: z.name.split(' ')[0], value: zs.latest.nrw_percentage } : null
            })
            .filter(Boolean) as { label: string; value: number }[]
    }, [snaps.data, zones])

    if (snaps.loading) return <Spinner label="Loading analytics…" />
    if (snaps.error) return <ErrorState error={snaps.error} onRetry={snaps.reload} />

    return (
    <div className="space-y-6">
        {/* town forecast hero */}
        <ForecastBanner
            title="Town-wide 30-day projection"
            forecast={townForecast}
            anchor={anchor}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
                <SectionTitle icon={LineChartIcon} right={<span className="text-[10px] text-stone-400">GET /nrw/summary</span>}>
                    Town NRW Trend
                </SectionTitle>
                {townPts.length > 1 ? (
                    <LineChart
                        points={townPts.map((p) => ({ t: p.t, value: p.nrw }))}
                        anchor={anchor}
                        anchorLabel={`anchor ${fmtPct(anchor)}`}
                    />
                ) : (
                    <EmptyState title="Not enough snapshots" hint="Two or more weekly batches required." />
                )}
            </Card>

            <Card>
                <SectionTitle icon={BarChart3} right={<span className="text-[10px] text-stone-400">ML/day</span>}>
                    Town Physical Loss Trend
                </SectionTitle>
                {lossPts.length > 1 ? (
                    <LineChart
                        points={lossPts}
                        formatValue={(v) => `${v.toFixed(1)} ML`}
                        color="#e11d48"
                    />
                ) : (
                    <EmptyState title="Not enough snapshots" hint="Two or more weekly batches required." />
                )}
            </Card>
        </div>

        <Card>
            <SectionTitle icon={BarChart3} right={<span className="text-[10px] text-stone-400">latest snapshot per zone</span>}>
                Zone Comparison vs {fmtPct(anchor)} Anchor
            </SectionTitle>
            {zoneBars.length > 0 ? (
                <BarChart data={zoneBars} anchor={anchor} anchorLabel={`anchor ${fmtPct(anchor)}`} height={200} />
            ) : (
                <EmptyState title="No zone snapshots" />
            )}
            <div className="text-[10px] text-stone-400 mt-2">
                Rose bars exceed the Lucknow anchor; emerald bars are within it.
            </div>
        </Card>

        {/* zone-level detail */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
                <ForecastBanner
                    title={`Zone projection — ${zones.find((z) => z.id === activeZone)?.name || activeZone}`}
                    forecast={zoneForecast}
                    anchor={anchor}
                    selector={
                        <select className={`${inputCls} !w-64`} value={activeZone} onChange={(e) => setZoneId(e.target.value)}>
                            {zones.map((z) => (
                                <option key={z.id} value={z.id}>
                                    {z.name} ({z.id})
                                </option>
                            ))}
                        </select>
                    }
                />
            </div>

            <Card>
                <SectionTitle icon={Satellite} right={<Pill className="bg-stone-800 text-stone-100">NDWI</Pill>}>
                    Satellite Second Opinion
                </SectionTitle>
                {ndwi.loading && <Spinner label="Querying scene catalog…" />}
                {ndwi.error && <ErrorState error={ndwi.error} onRetry={ndwi.reload} />}
                {ndwi.data && (
                    <div className="space-y-3 text-xs">
                        <div className="flex items-center justify-between">
                            <Pill className={ndwi.data.status === 'OK' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}>
                                {ndwi.data.status}
                            </Pill>
                            <Pill className="bg-stone-200 text-stone-700">{ndwi.data.ndwi_status}</Pill>
                        </div>
                        <p className="text-[11px] leading-relaxed text-stone-600">
                            {ndwi.data.interpretation}
                        </p>
                        {ndwi.data.scene && (
                            <div className="p-2.5 rounded-lg bg-[#fbfaf8] border border-[#dad6cb] text-[11px] text-stone-600 space-y-0.5">
                                <div className="font-mono">{ndwi.data.scene.id}</div>
                                <div>
                                    {ndwi.data.scene.platform} · {ndwi.data.scene.datetime} · cloud{' '}
                                    {ndwi.data.scene.cloud_cover}%
                                </div>
                            </div>
                        )}
                        <div className="flex flex-wrap gap-1.5">
                            {ndwi.data.flag_sources.map((s) => (
                                <Pill key={s} className="bg-blue-100 text-blue-800">
                                    {s}
                                </Pill>
                            ))}
                        </div>
                        <button
                            onClick={() => navigate(`/app/copilot?zone=${activeZone}`)}
                            className="w-full inline-flex items-center justify-center space-x-1.5 bg-[#1c1917] hover:bg-stone-800 text-white px-3 py-2 rounded-lg text-xs font-medium transition-all"
                        >
                            <Bot className="w-3.5 h-3.5" />
                            <span>Investigate this zone</span>
                        </button>
                    </div>
                )}
            </Card>
        </div>
    </div>
    )
}

/* ------------------------------------------------------ forecast banner */

function ForecastBanner({
    title,
    forecast,
    anchor,
    selector,
}: {
    title: string
    forecast: AsyncState<api.NRWForecast | null>
    anchor: number
    selector?: React.ReactNode
}) {
    const f = forecast.data
    return (
        <Card>
            <SectionTitle
                icon={LineChartIcon}
                right={
                    <div className="flex items-center space-x-3">
                        {selector}
                        <span className="text-[10px] text-stone-400">GET /data/nrw-forecast</span>
                    </div>
                }
            >
                {title}
            </SectionTitle>
            {forecast.loading && <Spinner label="Projecting…" />}
            {forecast.error && <ErrorState error={forecast.error} onRetry={forecast.reload} />}
            {f && !f.is_sufficient && (
                <InlineNotice tone="blue" title="Insufficient history for a projection">
                    {f.message ||
                        `Collected ${f.observations} observation(s); the model needs ${f.required_observations ?? 'more'}.`}
                </InlineNotice>
            )}
            {f && f.is_sufficient && (
                <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                        <Pill
                            className={
                                f.direction === 'WORSENING'
                                    ? 'bg-rose-100 text-rose-800'
                                    : f.direction === 'IMPROVING'
                                      ? 'bg-emerald-100 text-emerald-800'
                                      : 'bg-stone-200 text-stone-700'
                            }
                        >
                            {f.direction || 'FLAT'} over {f.horizon_days ?? 30} days
                        </Pill>
                        <Pill className="bg-blue-100 text-blue-800">
                            confidence {f.trend_confidence || '—'}
                        </Pill>
                        <span className="text-[10px] text-stone-400">
                            {f.observations} observations · {f.method} · R²{' '}
                            {f.nrw_r2 !== null && f.nrw_r2 !== undefined ? f.nrw_r2.toFixed(2) : '—'}
                        </span>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                        <Cell label="Current NRW" value={f.current_nrw_pct ?? null} fmt={(v) => fmtPct(v)} />
                        <Cell label="Projected NRW" value={f.projected_nrw_pct ?? null} fmt={(v) => fmtPct(v)} />
                        <Cell
                            label="Projected loss / 30d"
                            value={f.projected_loss_litres ?? null}
                            fmt={(v) => fmtML(v)}
                            danger
                        />
                        <Cell
                            label="₹ at stake / 30d"
                            value={f.projected_loss_rupees ?? null}
                            fmt={(v) => fmtINR(v, 1)}
                            danger
                        />
                    </div>
                    {f.interpretation && (
                        <p className="text-[11px] leading-relaxed text-stone-600">{f.interpretation}</p>
                    )}
                    <div className="text-[10px] text-stone-400">
                        anchor reference: {fmtPct(anchor)} town NRW (Lucknow)
                    </div>
                </div>
            )}
        </Card>
    )
}

function Cell({
    label,
    value,
    fmt,
    danger,
}: {
    label: string
    value: number | null
    fmt: (v: number) => string
    danger?: boolean
}) {
    return (
        <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
            <div className="text-[10px] uppercase text-stone-500 font-semibold">{label}</div>
            <div className={`font-bold mt-0.5 ${danger ? 'text-rose-700' : 'text-stone-900'}`}>
                {value !== null && value !== undefined ? fmt(value) : '—'}
            </div>
        </div>
    )
}
