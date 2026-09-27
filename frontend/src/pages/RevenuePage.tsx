import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    DollarSign,
    CheckCircle2,
    XCircle,
    PlayCircle,
    Plus,
    RefreshCw,
    History,
    Calculator,
} from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import {
    fmtINR,
    fmtML,
    fmtDateTime,
    urgencyClass,
    downloadCSV,
} from '../lib/format'
import {
    Card,
    SectionTitle,
    ErrorState,
    Spinner,
    Pill,
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
   Revenue & Actions — the officer workflow end-to-end:
   GET /actions/ (list), POST /actions/approve|reject|resolve/{id},
   GET /revenue/summary (auto-written on resolve), GET /revenue/payback/{zone}.
   ========================================================================= */

export default function RevenuePage() {
    const navigate = useNavigate()
    const { zones, refresh: refreshStore } = useStore()
    const actions = useAsync(() => api.getActions(), [])
    const revenue = useAsync(() => api.getRevenue(), [])

    const [rejectFor, setRejectFor] = useState<api.ActionLog | null>(null)
    const [resolveFor, setResolveFor] = useState<api.ActionLog | null>(null)
    const [createOpen, setCreateOpen] = useState(false)
    const [toast, setToast] = useState<string | null>(null)
    const [busyId, setBusyId] = useState<number | null>(null)

    const zoneById = useMemo(() => new Map(zones.map((z) => [z.id, z])), [zones])

    const reload = () => {
        actions.reload()
        revenue.reload()
        refreshStore()
    }

    const approve = async (a: api.ActionLog) => {
        setBusyId(a.id)
        try {
            await api.approveAction(a.id)
            setToast(`Action #${a.id} approved — it can now be executed (Resolve).`)
            reload()
        } catch (e) {
            setToast((e as Error).message)
        } finally {
            setBusyId(null)
        }
    }

    const counts = useMemo(() => {
        const list = actions.data || []
        return {
            pending: list.filter((a) => a.status === 'PENDING').length,
            approved: list.filter((a) => a.status === 'APPROVED').length,
            rejected: list.filter((a) => a.status === 'REJECTED').length,
            resolved: list.filter((a) => a.status === 'RESOLVED').length,
        }
    }, [actions.data])

    const totalRecovered = (revenue.data || []).reduce((s, r) => s + r.revenue_recovered, 0)
    const totalLitres = (revenue.data || []).reduce((s, r) => s + r.litres_recovered, 0)

    return (
    <div className="space-y-6">
        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="Pending approval" value={String(counts.pending)} sub="officer decision required" cls="text-amber-700" />
            <Kpi label="Approved (ready)" value={String(counts.approved)} sub="execute via Resolve" cls="text-emerald-700" />
            <Kpi label="Revenue recovered" value={fmtINR(totalRecovered, 2)} sub={`${(revenue.data || []).length} recovery entries`} cls="text-stone-900" />
            <Kpi label="Litres recovered" value={fmtML(totalLitres)} sub={`${counts.resolved} actions resolved`} cls="text-blue-700" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* -------------------------------------------------- action log */}
            <div className="lg:col-span-2 space-y-6">
                <Card className="!p-0 overflow-hidden">
                    <div className="px-4 pt-4 flex items-center justify-between">
                        <SectionTitle>Action Log</SectionTitle>
                        <div className="flex items-center space-x-2 pb-4">
                            <button
                                onClick={reload}
                                className="p-2 bg-white border border-[#dad6cb] rounded-lg text-stone-500 hover:text-stone-900"
                                title="Refresh"
                            >
                                <RefreshCw className="w-3.5 h-3.5" />
                            </button>
                            <button
                                onClick={() => setCreateOpen(true)}
                                className="inline-flex items-center space-x-1.5 bg-[#1c1917] hover:bg-stone-800 text-white px-3 py-2 rounded-lg text-xs font-medium"
                            >
                                <Plus className="w-3.5 h-3.5" />
                                <span>New action</span>
                            </button>
                        </div>
                    </div>

                    {actions.loading && <Spinner label="Loading actions…" />}
                    {actions.error && <ErrorState error={actions.error} onRetry={actions.reload} />}
                    {actions.data && actions.data.length === 0 && !actions.loading && (
                        <EmptyState
                            icon={DollarSign}
                            title="No actions filed yet"
                            hint="Dispatch from Live Alerts, Billing Audit or the AI Copilot — entries land here for approval."
                        />
                    )}
                    {actions.data && actions.data.length > 0 && (
                        <table className="w-full text-left text-xs">
                            <thead className="bg-[#e8e6e0] text-stone-600 font-semibold border-b border-[#dad6cb]">
                                <tr>
                                    <th className="p-3">ID</th>
                                    <th className="p-3">Zone</th>
                                    <th className="p-3">Action</th>
                                    <th className="p-3">Urgency</th>
                                    <th className="p-3">Cost</th>
                                    <th className="p-3">Payback</th>
                                    <th className="p-3">Status</th>
                                    <th className="p-3 text-right">Officer decisions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#dad6cb]">
                                {actions.data.map((a) => (
                                    <tr key={a.id} className="hover:bg-[#fbfaf8] transition-colors align-top">
                                        <td className="p-3 font-mono font-bold">#{a.id}</td>
                                        <td className="p-3">
                                            <button
                                                onClick={() => navigate(`/app/zones?zone=${a.zone_id}`)}
                                                className="text-left hover:underline"
                                            >
                                                {zoneById.get(a.zone_id)?.name || a.zone_id}
                                                {a.alert_id ? (
                                                    <div className="text-[10px] text-stone-400">
                                                        alert ALT-{a.alert_id}
                                                    </div>
                                                ) : null}
                                            </button>
                                        </td>
                                        <td className="p-3 max-w-[220px]">
                                            <div className="font-medium text-stone-800">{a.action_type}</div>
                                            {a.officer_notes && (
                                                <div className="text-[10px] text-stone-500 mt-0.5 line-clamp-2">
                                                    {a.officer_notes}
                                                </div>
                                            )}
                                            <div className="text-[10px] text-stone-400 mt-0.5">
                                                {fmtDateTime(a.created_at)}
                                            </div>
                                        </td>
                                        <td className="p-3">
                                            <Pill className={urgencyClass(a.urgency)}>{a.urgency}</Pill>
                                        </td>
                                        <td className="p-3 font-mono">{fmtINR(a.estimated_cost, 2)}</td>
                                        <td className="p-3 font-mono">{a.estimated_payback_days.toFixed(0)}d</td>
                                        <td className="p-3">
                                            <StatusPill status={a.status} />
                                        </td>
                                        <td className="p-3 text-right space-x-1.5 whitespace-nowrap">
                                            {a.status === 'PENDING' && (
                                                <>
                                                    <button
                                                        onClick={() => approve(a)}
                                                        disabled={busyId === a.id}
                                                        className="inline-flex items-center space-x-1 px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-medium rounded-lg disabled:opacity-50"
                                                    >
                                                        <CheckCircle2 className="w-3 h-3" />
                                                        <span>Approve</span>
                                                    </button>
                                                    <button
                                                        onClick={() => setRejectFor(a)}
                                                        disabled={busyId === a.id}
                                                        className="inline-flex items-center space-x-1 px-2.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-[11px] font-medium rounded-lg disabled:opacity-50"
                                                    >
                                                        <XCircle className="w-3 h-3" />
                                                        <span>Reject</span>
                                                    </button>
                                                </>
                                            )}
                                            {a.status === 'APPROVED' && (
                                                <button
                                                    onClick={() => setResolveFor(a)}
                                                    disabled={busyId === a.id}
                                                    className="inline-flex items-center space-x-1 px-2.5 py-1.5 bg-[#1c1917] hover:bg-stone-800 text-white text-[11px] font-medium rounded-lg disabled:opacity-50"
                                                >
                                                    <PlayCircle className="w-3 h-3" />
                                                    <span>Resolve</span>
                                                </button>
                                            )}
                                            {(a.status === 'REJECTED' || a.status === 'RESOLVED') && (
                                                <span className="text-[10px] text-stone-400">
                                                    {a.status === 'RESOLVED' && a.resolved_at
                                                        ? `done ${fmtDateTime(a.resolved_at)}`
                                                        : 'closed'}
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </Card>

                {/* revenue log */}
                <Card className="!p-0 overflow-hidden">
                    <div className="px-4 pt-4 flex items-center justify-between">
                        <SectionTitle icon={History}>Revenue Recovery Log</SectionTitle>
                        <button
                            onClick={() =>
                                downloadCSV(
                                    'revenue-log.csv',
                                    (revenue.data || []).map((r) => ({
                                        id: r.id,
                                        zone_id: r.zone_id,
                                        alert_id: r.alert_id,
                                        litres_recovered: r.litres_recovered,
                                        tariff_rate: r.tariff_rate,
                                        revenue_recovered: r.revenue_recovered,
                                        recovered_at: r.recovered_at,
                                        notes: r.notes,
                                    })),
                                )
                            }
                            disabled={!revenue.data?.length}
                            className="text-xs text-stone-600 hover:text-stone-900 pb-4 disabled:opacity-40"
                        >
                            Export CSV
                        </button>
                    </div>
                    {revenue.loading && <Spinner label="Loading revenue…" />}
                    {revenue.error && <ErrorState error={revenue.error} onRetry={revenue.reload} />}
                    {revenue.data && revenue.data.length === 0 && !revenue.loading && (
                        <EmptyState
                            icon={DollarSign}
                            title="No recoveries recorded yet"
                            hint="Resolve an approved action — the backend auto-writes revenue_log (litres × tariff) on resolution."
                        />
                    )}
                    {revenue.data && revenue.data.length > 0 && (
                        <table className="w-full text-left text-xs">
                            <thead className="bg-[#e8e6e0] text-stone-600 font-semibold border-b border-[#dad6cb]">
                                <tr>
                                    <th className="p-3">#</th>
                                    <th className="p-3">Zone</th>
                                    <th className="p-3">Litres recovered</th>
                                    <th className="p-3">Tariff</th>
                                    <th className="p-3">Revenue</th>
                                    <th className="p-3">When</th>
                                    <th className="p-3">Notes</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#dad6cb]">
                                {revenue.data.map((r) => (
                                    <tr key={r.id} className="hover:bg-[#fbfaf8] transition-colors">
                                        <td className="p-3 font-mono font-bold">#{r.id}</td>
                                        <td className="p-3">{zoneById.get(r.zone_id)?.name || r.zone_id}</td>
                                        <td className="p-3 font-mono">{fmtML(r.litres_recovered)}</td>
                                        <td className="p-3 font-mono">₹{r.tariff_rate}/L</td>
                                        <td className="p-3 font-mono font-bold text-emerald-700">
                                            {fmtINR(r.revenue_recovered, 2)}
                                        </td>
                                        <td className="p-3">{fmtDateTime(r.recovered_at)}</td>
                                        <td className="p-3 text-[10px] text-stone-500 max-w-[260px]">
                                            {r.notes}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </Card>
            </div>

            {/* --------------------------------------- payback calculator */}
            <PaybackCalculator zones={zones} />
        </div>

        {rejectFor && (
            <RejectModal
                action={rejectFor}
                onClose={() => setRejectFor(null)}
                onDone={(msg) => {
                    setRejectFor(null)
                    setToast(msg)
                    reload()
                }}
            />
        )}
        {resolveFor && (
            <ResolveModal
                action={resolveFor}
                onClose={() => setResolveFor(null)}
                onDone={(msg) => {
                    setResolveFor(null)
                    setToast(msg)
                    reload()
                }}
            />
        )}
        {createOpen && (
            <CreateActionModal
                zones={zones}
                onClose={() => setCreateOpen(false)}
                onDone={(msg) => {
                    setCreateOpen(false)
                    setToast(msg)
                    reload()
                }}
            />
        )}
        {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
    )
}

/* -------------------------------------------------------------- widgets */

function Kpi({ label, value, sub, cls }: { label: string; value: string; sub: string; cls: string }) {
    return (
        <div className="bg-gradient-to-br from-white to-[#f7f5f0] p-5 rounded-xl border border-[#dad6cb] shadow-sm">
            <div className="text-xs font-medium uppercase tracking-wider text-stone-500">{label}</div>
            <div className={`text-2xl font-bold mt-2 ${cls}`}>{value}</div>
            <div className="text-[11px] text-stone-500 mt-1">{sub}</div>
        </div>
    )
}

function PaybackCalculator({ zones }: { zones: api.Zone[] }) {
    const [zoneId, setZoneId] = useState(zones[0]?.id || '')
    const payback = useAsync<api.Payback | null>(
        () => (zoneId ? api.getPayback(zoneId) : Promise.resolve(null)),
        [zoneId],
    )

    return (
        <Card className="h-max">
            <SectionTitle icon={Calculator} right={<Pill className="bg-stone-800 text-stone-100">live engine</Pill>}>
                Repair Payback Calculator
            </SectionTitle>
            <select className={`${inputCls} mb-3`} value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                {zones.map((z) => (
                    <option key={z.id} value={z.id}>
                        {z.name} ({z.id})
                    </option>
                ))}
            </select>
            {payback.loading && <Spinner label="Calculating…" />}
            {payback.error && <ErrorState error={payback.error} onRetry={payback.reload} />}
            {payback.data && (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <Pill
                            className={
                                payback.data.data_source === 'DEFAULT_FALLBACK'
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-emerald-100 text-emerald-800'
                            }
                        >
                            {payback.data.data_source}
                        </Pill>
                        <span className="text-[10px] text-stone-400">GET /revenue/payback/{zoneId}</span>
                    </div>
                    <div className="space-y-2 text-xs">
                        <Row k="Daily loss input" v={`${fmtML(payback.data.daily_loss_litres)} L`} />
                        <Row k="Daily revenue loss" v={fmtINR(payback.data.daily_revenue_loss)} />
                        <Row k="Est. repair cost" v={fmtINR(payback.data.estimated_repair_cost, 2)} />
                        <Row k="Payback period" v={`${payback.data.payback_period_days.toFixed(1)} days`} />
                    </div>
                    {payback.data.data_source === 'DEFAULT_FALLBACK' && (
                        <div className="text-[10px] text-amber-700 leading-relaxed">
                            No active alert for this zone — the engine used its default loss input, so
                            these figures are illustrative.
                        </div>
                    )}
                </div>
            )}
        </Card>
    )
}

function Row({ k, v }: { k: string; v: string }) {
    return (
        <div className="flex items-center justify-between p-2 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
            <span className="text-[11px] text-stone-500">{k}</span>
            <span className="text-[11px] font-semibold text-stone-800">{v}</span>
        </div>
    )
}

function RejectModal({
    action,
    onClose,
    onDone,
}: {
    action: api.ActionLog
    onClose: () => void
    onDone: (msg: string) => void
}) {
    const [reason, setReason] = useState('')
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState<string | null>(null)

    const submit = async () => {
        if (!reason.trim()) return
        setBusy(true)
        setErr(null)
        try {
            await api.rejectAction(action.id, reason.trim())
            onDone(`Action #${action.id} rejected. Reason recorded in officer_notes.`)
        } catch (e) {
            setErr((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Reject action #${action.id}`}
            onClose={onClose}
            footer={
                <>
                    <button onClick={onClose} className={btnSecondary}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={busy || !reason.trim()} className={`${btnPrimary} !bg-rose-600 hover:!bg-rose-700`}>
                        {busy ? 'Rejecting…' : 'Reject action'}
                    </button>
                </>
            }
        >
            <div className="text-xs text-stone-600">
                <strong>{action.action_type}</strong> · {action.zone_id}
            </div>
            <Field label="Reason (required)" hint="appended to officer_notes on the action">
                <textarea
                    className={`${inputCls} h-20 resize-none`}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. budget frozen this quarter"
                />
            </Field>
            {err && <div className="text-[11px] text-rose-700">{err}</div>}
        </Modal>
    )
}

function ResolveModal({
    action,
    onClose,
    onDone,
}: {
    action: api.ActionLog
    onClose: () => void
    onDone: (msg: string) => void
}) {
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState<string | null>(null)

    const submit = async () => {
        setBusy(true)
        setErr(null)
        try {
            await api.resolveAction(action.id)
            onDone(
                `Action #${action.id} resolved — associated alert closed and a revenue recovery entry written to revenue_log.`,
            )
        } catch (e) {
            setErr((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Execute action #${action.id}`}
            onClose={onClose}
            footer={
                <>
                    <button onClick={onClose} className={btnSecondary}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={busy} className={btnPrimary}>
                        {busy ? 'Executing…' : 'Mark resolved'}
                    </button>
                </>
            }
        >
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 text-[11px] text-blue-800 leading-relaxed">
                Resolving performs the backend’s auto-recovery milestone: action → RESOLVED,
                linked alert → RESOLVED, litres × tariff written to{' '}
                <span className="font-mono">revenue_log</span>, and a post-repair NRW snapshot is
                recorded for the zone.
            </div>
            <div className="text-xs text-stone-600">
                <strong>{action.action_type}</strong> · {action.zone_id} · est.{' '}
                {fmtINR(action.estimated_cost, 2)}
            </div>
            {err && <div className="text-[11px] text-rose-700">{err}</div>}
        </Modal>
    )
}

function CreateActionModal({
    zones,
    onClose,
    onDone,
}: {
    zones: api.Zone[]
    onClose: () => void
    onDone: (msg: string) => void
}) {
    const [zoneId, setZoneId] = useState(zones[0]?.id || '')
    const [actionType, setActionType] = useState('')
    const [urgency, setUrgency] = useState('MEDIUM')
    const [cost, setCost] = useState('20000')
    const [paybackDays, setPaybackDays] = useState('30')
    const [notes, setNotes] = useState('')
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState<string | null>(null)

    const submit = async () => {
        setBusy(true)
        setErr(null)
        try {
            const created = await api.createAction({
                zone_id: zoneId,
                action_type: actionType,
                urgency,
                estimated_cost: Number(cost) || 0,
                estimated_payback_days: Number(paybackDays) || 0,
                officer_notes: notes || null,
            })
            onDone(`Action #${created.id} created — pending officer approval.`)
        } catch (e) {
            setErr((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal
            title="Create action"
            onClose={onClose}
            footer={
                <>
                    <button onClick={onClose} className={btnSecondary}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={busy || !actionType.trim()} className={btnPrimary}>
                        {busy ? 'Creating…' : 'Create action'}
                    </button>
                </>
            }
        >
            <div className="grid grid-cols-2 gap-3">
                <Field label="Zone">
                    <select className={inputCls} value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                        {zones.map((z) => (
                            <option key={z.id} value={z.id}>
                                {z.name}
                            </option>
                        ))}
                    </select>
                </Field>
                <Field label="Urgency">
                    <select className={inputCls} value={urgency} onChange={(e) => setUrgency(e.target.value)}>
                        {['URGENT', 'HIGH', 'MEDIUM', 'LOW'].map((u) => (
                            <option key={u}>{u}</option>
                        ))}
                    </select>
                </Field>
            </div>
            <Field label="Action type">
                <input
                    className={inputCls}
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    placeholder="e.g. Valve replacement — Sector D"
                />
            </Field>
            <div className="grid grid-cols-2 gap-3">
                <Field label="Est. cost (₹)">
                    <input className={inputCls} type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} />
                </Field>
                <Field label="Payback (days)">
                    <input className={inputCls} type="number" min={0} value={paybackDays} onChange={(e) => setPaybackDays(e.target.value)} />
                </Field>
            </div>
            <Field label="Officer notes (optional)">
                <textarea className={`${inputCls} h-16 resize-none`} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            {err && <div className="text-[11px] text-rose-700">{err}</div>}
        </Modal>
    )
}
