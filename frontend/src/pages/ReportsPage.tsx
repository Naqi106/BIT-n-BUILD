import React, { useState } from 'react'
import { FileText, Download, Printer, AlertTriangle, Receipt, DollarSign, MapPin } from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import { fmtINR, fmtML, fmtPct, fmtDateTime, downloadCSV, fmtInt } from '../lib/format'
import { latestPerZone } from '../lib/derive'
import { Card, SectionTitle, Pill, Spinner, ErrorState, btnPrimary, Toast } from '../components/ui'

/* =========================================================================
   Reports — every export is generated client-side from LIVE API data at
   click time (no stored/static report files). The printable brief builds
   a real document from the same payloads.
   ========================================================================= */

export default function ReportsPage() {
    const { zones, alerts, actions } = useStore()
    const snaps = useAsync(() => api.getNRWSummary(), [])
    const profile = useAsync(() => api.getTownProfile(), [])
    const revenue = useAsync(() => api.getRevenue(), [])
    const [toast, setToast] = useState<string | null>(null)
    const [busy, setBusy] = useState<string | null>(null)

    const stamp = () => new Date().toLocaleString('en-GB')

    const withBusy = async (key: string, fn: () => Promise<void>) => {
        setBusy(key)
        try {
            await fn()
        } catch (e) {
            setToast((e as Error).message)
        } finally {
            setBusy(null)
        }
    }

    const exportZones = () =>
        withBusy('zones', async () => {
            const latest = latestPerZone(snaps.data ?? [])
            const rows = zones.map((z) => {
                const s = latest.get(z.id)
                return {
                    zone_id: z.id,
                    zone_name: z.name,
                    nrw_percentage: s?.nrw_percentage ?? '',
                    inflow_litres_per_day: s?.inflow_litres ?? '',
                    billed_litres_per_day: s?.billed_litres ?? '',
                    loss_litres_per_day: s?.loss_litres ?? '',
                    connections: z.connection_count,
                    pipe_length_km: z.pipe_length_km,
                    tariff_rate_per_litre: z.tariff_rate,
                    snapshot_at: s?.timestamp ?? '',
                }
            })
            downloadCSV('altomare-zone-nrw.csv', rows)
            setToast(`Exported ${rows.length} zones from /nrw/summary.`)
        })

    const exportAlerts = () => {
        downloadCSV(
            'altomare-alerts.csv',
            alerts.map((a) => ({
                id: a.id,
                zone_id: a.zone_id,
                severity: a.severity,
                status: a.status,
                estimated_loss_litres: a.estimated_loss_litres,
                confidence_score: a.confidence_score,
                detection_methods: a.detection_methods,
                timestamp: a.timestamp,
                details: a.details,
            })),
        )
        setToast(`Exported ${alerts.length} alerts.`)
    }

    const exportActions = () => {
        downloadCSV(
            'altomare-action-log.csv',
            actions.map((a) => ({
                id: a.id,
                zone_id: a.zone_id,
                alert_id: a.alert_id ?? '',
                action_type: a.action_type,
                urgency: a.urgency,
                status: a.status,
                estimated_cost: a.estimated_cost,
                estimated_payback_days: a.estimated_payback_days,
                officer_notes: a.officer_notes ?? '',
                created_at: a.created_at,
                resolved_at: a.resolved_at ?? '',
            })),
        )
        setToast(`Exported ${actions.length} actions.`)
    }

    const printBrief = async () => {
        const latest = latestPerZone(snaps.data ?? [])
        const town = profile.data
        const zoneRows = zones
            .map((z) => {
                const s = latest.get(z.id)
                return `<tr><td>${z.name}</td><td>${s ? fmtPct(s.nrw_percentage) : '—'}</td><td>${s ? fmtML(s.loss_litres) : '—'}</td><td>${fmtInt(z.connection_count)}</td></tr>`
            })
            .join('')
        const alertRows = alerts
            .slice(0, 10)
            .map(
                (a) =>
                    `<tr><td>ALT-${a.id}</td><td>${a.zone_id}</td><td>${a.severity}</td><td>${fmtML(a.estimated_loss_litres)}</td><td>${a.status}</td></tr>`,
            )
            .join('')
        const pendingRows = actions
            .filter((a) => a.status === 'PENDING' || a.status === 'APPROVED')
            .map(
                (a) =>
                    `<tr><td>#${a.id}</td><td>${a.zone_id}</td><td>${a.action_type}</td><td>${a.urgency}</td><td>${a.status}</td></tr>`,
            )
            .join('')

        const html = `<!doctype html><html><head><title>AltoMare NRW Brief</title>
        <style>
            body{font-family:Georgia,serif;margin:40px;color:#111}
            h1{font-size:22px;margin:0} h2{font-size:14px;margin:28px 0 8px;text-transform:uppercase;letter-spacing:1px}
            .meta{color:#666;font-size:12px;margin-top:6px}
            .kpis{display:flex;gap:16px;margin-top:16px}
            .kpi{border:1px solid #ccc;padding:10px 14px;min-width:130px}
            .kpi b{display:block;font-size:18px}
            table{width:100%;border-collapse:collapse;font-size:12px}
            th,td{border:1px solid #ddd;padding:5px 7px;text-align:left}
            th{background:#f2f0eb}
            footer{margin-top:30px;font-size:11px;color:#777}
        </style></head><body>
        <h1>AltoMare TRACE — NRW Operations Brief</h1>
        <div class="meta">Generated ${stamp()} from live API (GET /data/town-profile, /nrw/summary, /alerts, /actions/)</div>
        <div class="kpis">
            <div class="kpi"><span>Town NRW</span><b>${town ? fmtPct(town.total_nrw_percent) : '—'}</b></div>
            <div class="kpi"><span>Annual revenue loss</span><b>${town ? fmtINR(town.estimated_annual_loss_inr, 1) : '—'}</b></div>
            <div class="kpi"><span>Active alerts</span><b>${alerts.filter((a) => a.status === 'ACTIVE').length}</b></div>
            <div class="kpi"><span>Pending actions</span><b>${actions.filter((a) => a.status === 'PENDING').length}</b></div>
        </div>
        <h2>Zone water balance (latest snapshot)</h2>
        <table><tr><th>Zone</th><th>NRW</th><th>Loss/day</th><th>Connections</th></tr>${zoneRows}</table>
        <h2>Recent alerts</h2>
        <table><tr><th>ID</th><th>Zone</th><th>Severity</th><th>Est. loss</th><th>Status</th></tr>${alertRows || '<tr><td colspan="5">No alerts</td></tr>'}</table>
        <h2>Approval queue</h2>
        <table><tr><th>ID</th><th>Zone</th><th>Action</th><th>Urgency</th><th>Status</th></tr>${pendingRows || '<tr><td colspan="5">Queue empty</td></tr>'}</table>
        <footer>${town ? `Anchor source: ${town.anchor_source_citation}` : ''}</footer>
        </body></html>`
        const w = window.open('', '_blank')
        if (w) {
            w.document.write(html)
            w.document.close()
            w.focus()
            setTimeout(() => w.print(), 300)
        } else {
            setToast('Popup blocked — allow popups to print the brief.')
        }
    }

    if (snaps.loading || profile.loading) return <Spinner label="Preparing reports…" />
    if (snaps.error) return <ErrorState error={snaps.error} onRetry={snaps.reload} />

    const latest = latestPerZone(snaps.data ?? [])
    const townNrw = (() => {
        let loss = 0
        let inflow = 0
        for (const s of latest.values()) {
            loss += s.loss_litres
            inflow += s.inflow_litres
        }
        return inflow > 0 ? (loss / inflow) * 100 : null
    })()

    const cards = [
        {
            key: 'zones',
            icon: MapPin,
            title: 'Zone NRW snapshot',
            desc: `All ${zones.length} DMAs with latest NRW, inflow, billed and loss figures.`,
            stat: townNrw !== null ? `town ${fmtPct(townNrw)}` : '—',
            action: exportZones,
        },
        {
            key: 'alerts',
            icon: AlertTriangle,
            title: 'Leak alerts',
            desc: 'Full alert history with severity, confidence and detection methods.',
            stat: `${alerts.length} rows`,
            action: exportAlerts,
        },
        {
            key: 'actions',
            icon: Receipt,
            title: 'Action log',
            desc: 'Approvals, rejections, resolutions with costs and payback estimates.',
            stat: `${actions.length} rows`,
            action: exportActions,
        },
        {
            key: 'revenue',
            icon: DollarSign,
            title: 'Revenue recovery',
            desc: 'Recovered litres × tariff entries written by the resolve workflow.',
            stat: `${(revenue.data || []).length} rows`,
            action: () => {
                downloadCSV(
                    'altomare-revenue.csv',
                    (revenue.data || []).map((r) => ({ ...r })),
                )
                setToast(`Exported ${(revenue.data || []).length} revenue entries.`)
            },
        },
    ]

    return (
        <div className="space-y-6">
            <Card>
                <SectionTitle
                    icon={FileText}
                    right={
                        <button onClick={printBrief} className={`${btnPrimary} inline-flex items-center space-x-1.5`}>
                            <Printer className="w-3.5 h-3.5" />
                            <span>Print full brief (PDF)</span>
                        </button>
                    }
                >
                    Full Operations Brief
                </SectionTitle>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                        <div className="text-[10px] uppercase text-stone-500 font-semibold">Town NRW</div>
                        <div className="font-bold text-lg text-stone-900">
                            {townNrw !== null ? fmtPct(townNrw) : '—'}
                        </div>
                    </div>
                    <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                        <div className="text-[10px] uppercase text-stone-500 font-semibold">
                            Annual loss
                        </div>
                        <div className="font-bold text-lg text-rose-700">
                            {fmtINR(profile.data?.estimated_annual_loss_inr ?? null, 1)}
                        </div>
                    </div>
                    <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                        <div className="text-[10px] uppercase text-stone-500 font-semibold">
                            Active alerts
                        </div>
                        <div className="font-bold text-lg text-amber-700">
                            {alerts.filter((a) => a.status === 'ACTIVE').length}
                        </div>
                    </div>
                    <div className="p-3 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
                        <div className="text-[10px] uppercase text-stone-500 font-semibold">
                            Approval queue
                        </div>
                        <div className="font-bold text-lg text-stone-900">
                            {actions.filter((a) => a.status === 'PENDING').length}
                        </div>
                    </div>
                </div>
                <p className="text-[11px] text-stone-500 mt-3 leading-relaxed">
                    Generated <strong>{stamp()}</strong> from live API payloads — nothing on this
                    page is stored or cached.
                </p>
            </Card>

            <div className="grid sm:grid-cols-2 gap-4">
                {cards.map((c) => (
                    <Card key={c.key} className="flex items-start justify-between space-x-4">
                        <div className="space-y-1.5">
                            <div className="flex items-center space-x-2">
                                <c.icon className="w-4 h-4 text-stone-600" />
                                <span className="text-sm font-bold text-stone-900">{c.title}</span>
                                <Pill className="bg-stone-200 text-stone-700">{c.stat}</Pill>
                            </div>
                            <p className="text-[11px] text-stone-500 leading-relaxed">{c.desc}</p>
                            <button
                                onClick={c.action}
                                disabled={busy === c.key}
                                className="inline-flex items-center space-x-1.5 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] text-stone-700 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all mt-2 disabled:opacity-50"
                            >
                                <Download className="w-3.5 h-3.5" />
                                <span>{busy === c.key ? 'Exporting…' : 'Export CSV'}</span>
                            </button>
                        </div>
                    </Card>
                ))}
            </div>

            {toast && <Toast message={toast} onClose={() => setToast(null)} />}
        </div>
    )
}
