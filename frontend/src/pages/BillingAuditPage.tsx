import React, { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Receipt, Send, Download, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import { fmtML, fmtPct, downloadCSV } from '../lib/format'
import {
    Card,
    SectionTitle,
    ErrorState,
    Spinner,
    Pill,
    EmptyState,
    StatGrid,
    Modal,
    Field,
    inputCls,
    btnPrimary,
    btnSecondary,
    Toast,
} from '../components/ui'
import { ScoreBar } from '../components/Charts'

/* =========================================================================
   Billing Audit — GET /audit/billing/{zone_id} (paginated ML scoring),
   working pagination, per-row inspector dispatch (POST /actions/create)
   and CSV export of the full audit (paged fetch).
   ========================================================================= */

const PAGE = 20

export default function BillingAuditPage() {
    const { zones } = useStore()
    const [params, setParams] = useSearchParams()
    const zoneParam = params.get('zone') || zones[0]?.id || ''
    const [offset, setOffset] = useState(0)
    const [dispatch, setDispatch] = useState<api.BillingItem | null>(null)
    const [toast, setToast] = useState<string | null>(null)
    const [exporting, setExporting] = useState(false)

    const zoneId = zoneParam || zones[0]?.id || ''
    // zoneId is '' until the store's zones arrive — skip the fetch then, or
    // the first effect fires GET /audit/billing/?… which 404s.
    const audit = useAsync<api.PaginatedBilling | null>(
        () => (zoneId ? api.getBilling(zoneId, PAGE, offset) : Promise.resolve(null)),
        [zoneId, offset],
    )

    const setZone = (zid: string) => {
        const next = new URLSearchParams(params)
        next.set('zone', zid)
        setParams(next)
        setOffset(0)
    }

    const exportAll = async () => {
        if (!zoneId) return
        setExporting(true)
        try {
            const rows: Record<string, unknown>[] = []
            let off = 0
            for (let page = 0; page < 50; page++) {
                const res = await api.getBilling(zoneId, 200, off)
                for (const it of res.items) {
                    rows.push({
                        zone_id: zoneId,
                        consumer_id: it.consumer_id,
                        household_size: it.household_size,
                        property_type: it.property_type,
                        billed_litres: it.billed_litres,
                        benchmark_litres: it.benchmark_litres,
                        suspicion_score: it.suspicion_score,
                        is_anomaly: it.is_anomaly,
                    })
                }
                if (res.items.length < 200) break
                off += 200
            }
            downloadCSV(`billing-audit-${zoneId}.csv`, rows)
            setToast(`Exported ${rows.length} billing records from ${zoneId}.`)
        } catch (e) {
            setToast((e as Error).message)
        } finally {
            setExporting(false)
        }
    }

    if (!zones.length) return <Spinner label="Loading zones…" />

    return (
    <div className="space-y-6">
        {/* controls */}
        <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
                <label className="flex items-center space-x-2 text-xs text-stone-600">
                    <span>Zone</span>
                    <select
                        className={`${inputCls} !w-64`}
                        value={zoneId}
                        onChange={(e) => setZone(e.target.value)}
                    >
                        {zones.map((z) => (
                            <option key={z.id} value={z.id}>
                                {z.name} ({z.id})
                            </option>
                        ))}
                    </select>
                </label>
                <Pill className="bg-stone-800 text-stone-100" title="Isolation-forest with rule fallback">
                    ML
                </Pill>
                <span className="text-[11px] text-stone-400">GET /audit/billing/{zoneId}</span>
            </div>
            <button
                onClick={exportAll}
                disabled={exporting}
                className="inline-flex items-center space-x-1.5 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] text-stone-700 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
            >
                <Download className="w-3.5 h-3.5" />
                <span>{exporting ? 'Exporting…' : 'Export full audit (CSV)'}</span>
            </button>
        </div>

        {audit.loading && <Spinner label="Running billing audit…" />}
        {audit.error && <ErrorState error={audit.error} onRetry={audit.reload} />}

        {audit.data && (
            <>
                <StatGrid
                    items={[
                        { label: 'Records audited', value: audit.data.total_records.toLocaleString('en-IN') },
                        {
                            label: 'Anomalies flagged',
                            value: audit.data.total_anomalies.toLocaleString('en-IN'),
                            sub:
                                audit.data.total_records > 0
                                    ? fmtPct((audit.data.total_anomalies / audit.data.total_records) * 100)
                                    : undefined,
                        },
                        {
                            label: 'This page',
                            value: `${audit.data.items.length} rows`,
                            sub: `offset ${audit.data.offset} · limit ${audit.data.limit}`,
                        },
                        {
                            label: 'Method',
                            value: 'Isolation Forest',
                            sub: 'rule-based fallback when sample is small',
                        },
                    ]}
                />

                <Card className="!p-0 overflow-hidden">
                    <div className="px-4 pt-4">
                        <SectionTitle icon={Receipt} right={<span className="text-[10px] text-stone-400">suspicion score 0–1</span>}>
                            Consumer Scoring
                        </SectionTitle>
                    </div>
                    {audit.data.items.length === 0 ? (
                        <EmptyState
                            icon={Receipt}
                            title="No billing records for this zone"
                            hint="Upload a billing CSV (Data Upload) or seed billing data to see scoring."
                        />
                    ) : (
                        <table className="w-full text-left text-xs">
                            <thead className="bg-[#e8e6e0] text-stone-600 font-semibold border-b border-[#dad6cb]">
                                <tr>
                                    <th className="p-3">Consumer</th>
                                    <th className="p-3">Type</th>
                                    <th className="p-3">HH</th>
                                    <th className="p-3">Billed</th>
                                    <th className="p-3">Benchmark</th>
                                    <th className="p-3">Deviation</th>
                                    <th className="p-3">Suspicion</th>
                                    <th className="p-3">Flag</th>
                                    <th className="p-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#dad6cb]">
                                {audit.data.items.map((it, idx) => (
                                    <tr key={`${it.consumer_id}-${audit.data!.offset + idx}`} className="hover:bg-[#fbfaf8] transition-colors">
                                        <td className="p-3 font-mono font-bold text-stone-800">
                                            {it.consumer_id}
                                        </td>
                                        <td className="p-3">{it.property_type}</td>
                                        <td className="p-3">{it.household_size}</td>
                                        <td className="p-3 font-mono">{fmtML(it.billed_litres)}</td>
                                        <td className="p-3 font-mono text-stone-500">
                                            {fmtML(it.benchmark_litres)}
                                        </td>
                                        <td className="p-3 font-mono text-rose-700 font-semibold">
                                            {it.benchmark_litres > 0
                                                ? fmtPct(
                                                      ((it.billed_litres - it.benchmark_litres) /
                                                          it.benchmark_litres) *
                                                          100,
                                                  )
                                                : '—'}
                                        </td>
                                        <td className="p-3">
                                            <ScoreBar value={it.suspicion_score} danger={it.is_anomaly} />
                                        </td>
                                        <td className="p-3">
                                            {it.is_anomaly ? (
                                                <Pill className="bg-rose-100 text-rose-800">ANOMALY</Pill>
                                            ) : (
                                                <Pill className="bg-emerald-100 text-emerald-800">OK</Pill>
                                            )}
                                        </td>
                                        <td className="p-3 text-right">
                                            <button
                                                onClick={() => setDispatch(it)}
                                                className="inline-flex items-center space-x-1 px-2.5 py-1.5 bg-[#1c1917] hover:bg-stone-800 text-white text-[11px] font-medium rounded-lg transition-all"
                                            >
                                                <Send className="w-3 h-3" />
                                                <span>Dispatch Inspector</span>
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                    {/* pagination */}
                    <div className="flex items-center justify-between px-4 py-3 border-t border-[#dad6cb] bg-[#fbfaf8]">
                        <button
                            onClick={() => setOffset(Math.max(0, offset - PAGE))}
                            disabled={offset === 0}
                            className="inline-flex items-center space-x-1 px-3 py-1.5 bg-white border border-[#dad6cb] rounded-lg text-xs disabled:opacity-40 hover:bg-[#f3f0e8]"
                        >
                            <ChevronLeft className="w-3.5 h-3.5" />
                            <span>Prev</span>
                        </button>
                        <span className="text-[11px] text-stone-500">
                            {offset + 1}–{Math.min(offset + PAGE, audit.data.total_records)} of{' '}
                            {audit.data.total_records}
                        </span>
                        <button
                            onClick={() => setOffset(offset + PAGE)}
                            disabled={offset + PAGE >= audit.data.total_records}
                            className="inline-flex items-center space-x-1 px-3 py-1.5 bg-white border border-[#dad6cb] rounded-lg text-xs disabled:opacity-40 hover:bg-[#f3f0e8]"
                        >
                            <span>Next</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </Card>
            </>
        )}

        {dispatch && zoneId && (
            <DispatchInspectorModal
                zoneId={zoneId}
                item={dispatch}
                onClose={() => setDispatch(null)}
                onDone={(msg) => {
                    setDispatch(null)
                    setToast(msg)
                }}
            />
        )}
        {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
    )
}

/* --------------------------------------------------------- dispatch modal */

function DispatchInspectorModal({
    zoneId,
    item,
    onClose,
    onDone,
}: {
    zoneId: string
    item: api.BillingItem
    onClose: () => void
    onDone: (msg: string) => void
}) {
    const [notes, setNotes] = useState(
        `Inspect ${item.consumer_id}: billed ${fmtML(item.billed_litres)} vs benchmark ${fmtML(item.benchmark_litres)} (score ${item.suspicion_score.toFixed(2)})`,
    )
    const [cost, setCost] = useState('8000')
    const [paybackDays, setPaybackDays] = useState('45')
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState<string | null>(null)

    const submit = async () => {
        setBusy(true)
        setErr(null)
        try {
            const created = await api.createAction({
                zone_id: zoneId,
                action_type: `Billing anomaly inspection — ${item.consumer_id}`,
                urgency: item.suspicion_score >= 0.7 ? 'HIGH' : 'MEDIUM',
                estimated_cost: Number(cost) || 0,
                estimated_payback_days: Number(paybackDays) || 0,
                officer_notes: notes,
            })
            onDone(`Action #${created.id} created for ${item.consumer_id} — pending officer approval.`)
        } catch (e) {
            setErr((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Dispatch inspector — ${item.consumer_id}`}
            onClose={onClose}
            footer={
                <>
                    <button onClick={onClose} className={btnSecondary}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={busy} className={btnPrimary}>
                        {busy ? 'Creating…' : 'Create inspection action'}
                    </button>
                </>
            }
        >
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-[11px] text-amber-800 flex items-start space-x-2">
                <AlertTriangle className="w-3.5 h-3.5 mt-0.5" />
                <span>
                    Creates a PENDING ActionLog entry. Nothing is executed until an officer approves
                    it in Revenue &amp; Actions.
                </span>
            </div>
            <Field label="Officer notes">
                <textarea className={`${inputCls} h-20 resize-none`} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
                <Field label="Est. cost (₹)">
                    <input className={inputCls} type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} />
                </Field>
                <Field label="Payback (days)">
                    <input
                        className={inputCls}
                        value={paybackDays}
                        onChange={(e) => setPaybackDays(e.target.value)}
                        type="number"
                        min={0}
                    />
                </Field>
            </div>
            {err && <div className="text-[11px] text-rose-700">{err}</div>}
        </Modal>
    )
}
