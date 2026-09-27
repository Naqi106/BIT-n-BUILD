import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, RefreshCw, Search, Send, ChevronDown, ChevronUp, Shield } from 'lucide-react'
import * as api from '../lib/api'
import { useStore } from '../lib/store'
import {
    fmtML,
    fmtINR,
    fmtPct,
    fmtDateTime,
    severityClass,
} from '../lib/format'
import {
    Card,
    Pill,
    ErrorState,
    EmptyState,
    Modal,
    Field,
    inputCls,
    btnPrimary,
    btnSecondary,
    Toast,
    StatusPill,
} from '../components/ui'

/* =========================================================================
   Live Alerts — GET /alerts (real LeakAlert rows), client-side search,
   and a working "Dispatch Team" that files an ActionLog entry for
   officer approval (POST /actions/create).
   ========================================================================= */

const SEVERITY_URGENCY: Record<string, string> = {
    CRITICAL: 'URGENT',
    HIGH: 'HIGH',
    MEDIUM: 'MEDIUM',
    LOW: 'LOW',
}

export default function AlertsPage() {
    const navigate = useNavigate()
    const { alerts, zones, refresh, loading, error } = useStore()
    const [query, setQuery] = useState('')
    const [expanded, setExpanded] = useState<number | null>(null)
    const [dispatchFor, setDispatchFor] = useState<api.LeakAlert | null>(null)
    const [toast, setToast] = useState<string | null>(null)

    const zoneById = useMemo(() => new Map(zones.map((z) => [z.id, z])), [zones])

    const counts = useMemo(() => {
        const c: Record<string, number> = {}
        for (const a of alerts) {
            const sev = a.severity.toUpperCase()
            c[sev] = (c[sev] || 0) + 1
        }
        return c
    }, [alerts])

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase()
        if (!q) return alerts
        return alerts.filter((a) => {
            const zoneName = zoneById.get(a.zone_id)?.name || a.zone_id
            return (
                `alt-${a.id}`.includes(q) ||
                String(a.id).includes(q) ||
                a.zone_id.toLowerCase().includes(q) ||
                zoneName.toLowerCase().includes(q) ||
                a.severity.toLowerCase().includes(q) ||
                a.status.toLowerCase().includes(q) ||
                (a.detection_methods || '').toLowerCase().includes(q)
            )
        })
    }, [alerts, query, zoneById])

    if (loading && alerts.length === 0) return <div className="text-xs text-stone-500 py-10 text-center">Loading alerts…</div>
    if (error) return <ErrorState error={error} onRetry={refresh} />

    return (
        <div className="space-y-6">
            {/* severity pills + search */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center space-x-3">
                    {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((sev) => (
                        <span
                            key={sev}
                            className={`px-3 py-1 rounded-full text-xs font-semibold ${
                                counts[sev]
                                    ? sev === 'CRITICAL'
                                        ? 'bg-rose-100 text-rose-800'
                                        : sev === 'HIGH'
                                          ? 'bg-amber-100 text-amber-800'
                                          : sev === 'MEDIUM'
                                            ? 'bg-blue-100 text-blue-800'
                                            : 'bg-stone-200 text-stone-700'
                                    : 'bg-stone-100 text-stone-400'
                            }`}
                        >
                            {counts[sev] || 0} {sev}
                        </span>
                    ))}
                    <span className="text-[11px] text-stone-400">GET /alerts · live</span>
                </div>
                <div className="flex items-center space-x-2">
                    <div className="relative">
                        <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-stone-400" />
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search alerts by zone or ID…"
                            className="pl-8 pr-3 py-1.5 bg-white border border-[#dad6cb] rounded-lg text-xs w-64 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        />
                    </div>
                    <button
                        onClick={refresh}
                        className="p-2 bg-white border border-[#dad6cb] rounded-lg text-stone-500 hover:text-stone-900 transition-colors"
                        title="Refresh"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* alerts table */}
            <Card className="!p-0 overflow-hidden">
                {filtered.length === 0 ? (
                    <EmptyState
                        icon={AlertTriangle}
                        title={alerts.length === 0 ? 'No alerts in the database' : 'No alerts match your search'}
                        hint={
                            alerts.length === 0
                                ? 'Run detection from the API or wait for scheduled water-balance alerts.'
                                : 'Try a different zone name or alert number.'
                        }
                    />
                ) : (
                    <table className="w-full text-left text-xs">
                        <thead className="bg-[#e8e6e0] text-stone-600 font-semibold border-b border-[#dad6cb]">
                            <tr>
                                <th className="p-3">Alert</th>
                                <th className="p-3">Zone / DMA</th>
                                <th className="p-3">Severity</th>
                                <th className="p-3">Est. Loss</th>
                                <th className="p-3">Daily Revenue Loss</th>
                                <th className="p-3">Confidence</th>
                                <th className="p-3">Status</th>
                                <th className="p-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#dad6cb]">
                            {filtered.map((a) => {
                                const zone = zoneById.get(a.zone_id)
                                const tariff = zone?.tariff_rate ?? 0.005
                                const dailyLoss = a.estimated_loss_litres * tariff
                                const isOpen = expanded === a.id
                                return (
                                    <React.Fragment key={a.id}>
                                        <tr
                                            className="hover:bg-[#fbfaf8] transition-colors cursor-pointer"
                                            onClick={() => setExpanded(isOpen ? null : a.id)}
                                        >
                                            <td className="p-3 font-mono font-bold text-stone-800">
                                                <span className="flex items-center space-x-1">
                                                    {isOpen ? (
                                                        <ChevronDown className="w-3 h-3" />
                                                    ) : (
                                                        <ChevronUp className="w-3 h-3" />
                                                    )}
                                                    <span>ALT-{a.id}</span>
                                                </span>
                                            </td>
                                            <td className="p-3 font-medium">
                                                <div>{zone?.name || a.zone_id}</div>
                                                <div className="text-[10px] text-stone-400">{a.zone_id}</div>
                                            </td>
                                            <td className="p-3">
                                                <Pill className={severityClass(a.severity)}>{a.severity}</Pill>
                                            </td>
                                            <td className="p-3 font-mono">{fmtML(a.estimated_loss_litres)}</td>
                                            <td className="p-3 font-mono font-semibold text-rose-700">
                                                {fmtINR(dailyLoss)}/day
                                            </td>
                                            <td className="p-3 font-mono">
                                                {fmtPct(a.confidence_score * 100, 1)}
                                            </td>
                                            <td className="p-3">
                                                <StatusPill status={a.status} />
                                            </td>
                                            <td className="p-3 text-right">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        setDispatchFor(a)
                                                    }}
                                                    className="inline-flex items-center space-x-1 px-3 py-1.5 bg-[#1c1917] hover:bg-stone-800 text-white text-[11px] font-medium rounded-lg transition-all"
                                                >
                                                    <Send className="w-3 h-3" />
                                                    <span>Dispatch Team</span>
                                                </button>
                                            </td>
                                        </tr>
                                        {isOpen && a.details && (
                                            <tr className="bg-[#fbfaf8]">
                                                <td colSpan={8} className="p-3 pt-0">
                                                    <div className="rounded-lg border border-[#dad6cb] bg-white p-3 space-y-2">
                                                        <div className="flex flex-wrap items-center gap-2 text-[10px]">
                                                            <Pill className="bg-stone-800 text-stone-100">
                                                                {a.detection_methods}
                                                            </Pill>
                                                            <span className="text-stone-500">
                                                                {fmtDateTime(a.timestamp)}
                                                            </span>
                                                        </div>
                                                        <p className="text-[11px] leading-relaxed text-stone-700">
                                                            {a.details}
                                                        </p>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                )
                            })}
                        </tbody>
                    </table>
                )}
            </Card>

            <div className="text-[10px] text-stone-400">
                Daily revenue loss = estimated_loss × zone tariff_rate · click a row for detection
                method details
            </div>

            {dispatchFor && (
                <DispatchModal
                    alert={dispatchFor}
                    zoneName={zoneById.get(dispatchFor.zone_id)?.name || dispatchFor.zone_id}
                    onClose={() => setDispatchFor(null)}
                    onDone={(msg) => {
                        setDispatchFor(null)
                        setToast(msg)
                        refresh()
                    }}
                />
            )}
            {toast && <Toast message={toast} onClose={() => setToast(null)} />}
        </div>
    )
}

/* -------------------------------------------------------- dispatch modal */

function DispatchModal({
    alert,
    zoneName,
    onClose,
    onDone,
}: {
    alert: api.LeakAlert
    zoneName: string
    onClose: () => void
    onDone: (msg: string) => void
}) {
    const [actionType, setActionType] = useState('Emergency acoustic survey & repair dispatch')
    const [urgency, setUrgency] = useState(SEVERITY_URGENCY[alert.severity.toUpperCase()] || 'MEDIUM')
    const [cost, setCost] = useState('25000')
    const [payback, setPayback] = useState('30')
    const [notes, setNotes] = useState(`Dispatched for ALT-${alert.id} (${alert.severity})`)
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState<string | null>(null)

    const submit = async () => {
        setBusy(true)
        setErr(null)
        try {
            const created = await api.createAction({
                zone_id: alert.zone_id,
                alert_id: alert.id,
                action_type: actionType,
                urgency,
                estimated_cost: Number(cost) || 0,
                estimated_payback_days: Number(payback) || 0,
                officer_notes: notes,
            })
            onDone(
                `Action #${created.id} created for ${zoneName} — pending officer approval. See Revenue & Actions.`,
            )
        } catch (e) {
            setErr((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Dispatch team — ALT-${alert.id} · ${zoneName}`}
            onClose={onClose}
            footer={
                <>
                    <button onClick={onClose} className={btnSecondary}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={busy || !actionType.trim()} className={btnPrimary}>
                        {busy ? 'Creating…' : 'Create dispatch action'}
                    </button>
                </>
            }
        >
            <div className="rounded-lg bg-[#fbfaf8] border border-[#dad6cb] p-3 text-[11px] text-stone-600 flex items-start space-x-2">
                <Shield className="w-3.5 h-3.5 mt-0.5 text-stone-400" />
                <span>
                    Files a PENDING entry in <span className="font-mono">action_log</span> linked to
                    alert ALT-{alert.id} (loss {fmtML(alert.estimated_loss_litres)},{' '}
                    {fmtPct(alert.confidence_score * 100)} confidence). An officer must approve it in
                    Revenue &amp; Actions before it is executed.
                </span>
            </div>
            <Field label="Action type">
                <input className={inputCls} value={actionType} onChange={(e) => setActionType(e.target.value)} />
            </Field>
            <div className="grid grid-cols-3 gap-3">
                <Field label="Urgency" hint="prefilled from severity">
                    <select className={inputCls} value={urgency} onChange={(e) => setUrgency(e.target.value)}>
                        {['URGENT', 'HIGH', 'MEDIUM', 'LOW'].map((u) => (
                            <option key={u}>{u}</option>
                        ))}
                    </select>
                </Field>
                <Field label="Est. cost (₹)">
                    <input
                        className={inputCls}
                        type="number"
                        min={0}
                        value={cost}
                        onChange={(e) => setCost(e.target.value)}
                    />
                </Field>
                <Field label="Payback (days)">
                    <input
                        className={inputCls}
                        type="number"
                        min={0}
                        value={payback}
                        onChange={(e) => setPayback(e.target.value)}
                    />
                </Field>
            </div>
            <Field label="Officer notes">
                <textarea
                    className={`${inputCls} h-16 resize-none`}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                />
            </Field>
            {err && <div className="text-[11px] text-rose-700">{err}</div>}
        </Modal>
    )
}
