import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Crosshair, Send, Download, Satellite } from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import { fmtPct, downloadCSV, fmtInt } from '../lib/format'
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
    InlineNotice,
} from '../components/ui'
import { ScoreBar } from '../components/Charts'

/* =========================================================================
   Leak Location — GET /audit/ppa/{zone_id}. PPA runs on a SIMULATED
   pressure grid (no physical sensors deployed); the roadmap requires that
   labelling to be visible, so it is banner-level here.
   ========================================================================= */

export default function LeakLocationPage() {
    const { zones } = useStore()
    const [params, setParams] = useSearchParams()
    const zoneParam = params.get('zone') || ''
    const zoneId = zoneParam || zones[0]?.id || ''
    const [dispatch, setDispatch] = useState<api.PPAItem | null>(null)
    const [toast, setToast] = useState<string | null>(null)

    // zoneId is '' until the store's zones arrive — skip the fetch then, or
    // the first effect fires GET /audit/ppa/ which 404s.
    const nodes = useAsync<api.PPAItem[]>(
        () => (zoneId ? api.getPPA(zoneId) : Promise.resolve([])),
        [zoneId],
    )

    const setZone = (zid: string) => {
        const next = new URLSearchParams(params)
        next.set('zone', zid)
        setParams(next)
    }

    if (!zones.length) return <Spinner label="Loading zones…" />

    const highProb = (nodes.data || []).filter((n) => n.leak_probability >= 0.7).length
    const maxDrop = (nodes.data || []).reduce((m, n) => Math.max(m, n.pressure_drop_bar), 0)

    return (
        <div className="space-y-6">
            {/* controls + SIM banner */}
            <div className="flex flex-wrap items-center justify-between gap-3">
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
                <div className="flex items-center space-x-2">
                    <Pill className="bg-stone-800 text-stone-100" title="Pressure Profile Analysis">
                        SIM
                    </Pill>
                    <span className="text-[11px] text-stone-400">GET /audit/ppa/{zoneId}</span>
                    <button
                        onClick={() => {
                            downloadCSV(
                                `ppa-${zoneId}.csv`,
                                (nodes.data || []).map((n) => ({ ...n })),
                            )
                            setToast(`Exported ${(nodes.data || []).length} PPA nodes from ${zoneId}.`)
                        }}
                        disabled={!nodes.data?.length}
                        className="inline-flex items-center space-x-1.5 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] text-stone-700 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
                    >
                        <Download className="w-3.5 h-3.5" />
                        <span>Export CSV</span>
                    </button>
                </div>
            </div>

            <InlineNotice tone="amber" title="Simulated sensor data">
                PPA runs on a <strong>simulated pressure grid</strong> — no physical pressure sensors
                are deployed in the network. Every row below carries <span className="font-mono">
                is_simulated=true</span> from the API so results are never mistaken for field
                telemetry.
            </InlineNotice>

            {nodes.loading && <Spinner label="Running pressure profile analysis…" />}
            {nodes.error && <ErrorState error={nodes.error} onRetry={nodes.reload} />}

            {nodes.data && (
                <>
                    <StatGrid
                        items={[
                            { label: 'Nodes scanned', value: fmtInt(nodes.data.length) },
                            {
                                label: 'High leak probability',
                                value: fmtInt(highProb),
                                sub: 'probability ≥ 0.70',
                            },
                            { label: 'Max pressure drop', value: `${maxDrop.toFixed(2)} bar` },
                            {
                                label: 'Data type',
                                value: 'Simulated',
                                sub: 'declared per-row by the API',
                            },
                        ]}
                    />

                    <Card className="!p-0 overflow-hidden">
                        <div className="px-4 pt-4">
                            <SectionTitle icon={Crosshair} right={<Satellite className="w-4 h-4 text-stone-400" />}>
                                Pressure Nodes
                            </SectionTitle>
                        </div>
                        {nodes.data.length === 0 ? (
                            <EmptyState
                                icon={Crosshair}
                                title="No PPA nodes for this zone"
                                hint="The audit returns an empty list when the simulated grid has no nodes seeded."
                            />
                        ) : (
                            <table className="w-full text-left text-xs">
                                <thead className="bg-[#e8e6e0] text-stone-600 font-semibold border-b border-[#dad6cb]">
                                    <tr>
                                        <th className="p-3">Node</th>
                                        <th className="p-3">Distance from source</th>
                                        <th className="p-3">Baseline</th>
                                        <th className="p-3">Observed</th>
                                        <th className="p-3">Drop</th>
                                        <th className="p-3">Leak probability</th>
                                        <th className="p-3">Data</th>
                                        <th className="p-3 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-[#dad6cb]">
                                    {nodes.data.map((n) => (
                                        <tr key={n.node_id} className="hover:bg-[#fbfaf8] transition-colors">
                                            <td className="p-3 font-mono font-bold text-stone-800">
                                                {n.node_id}
                                            </td>
                                            <td className="p-3 font-mono">
                                                {n.distance_from_source_km.toFixed(2)} km
                                            </td>
                                            <td className="p-3 font-mono text-stone-500">
                                                {n.baseline_pressure_bar.toFixed(2)} bar
                                            </td>
                                            <td className="p-3 font-mono">
                                                {n.observed_pressure_bar.toFixed(2)} bar
                                            </td>
                                            <td className="p-3 font-mono font-semibold text-rose-700">
                                                {n.pressure_drop_bar.toFixed(2)} bar
                                            </td>
                                            <td className="p-3">
                                                <ScoreBar
                                                    value={n.leak_probability}
                                                    danger={n.leak_probability >= 0.7}
                                                />
                                            </td>
                                            <td className="p-3">
                                                {n.is_simulated ? (
                                                    <Pill className="bg-amber-100 text-amber-800">SIMULATED</Pill>
                                                ) : (
                                                    <Pill className="bg-emerald-100 text-emerald-800">SENSOR</Pill>
                                                )}
                                            </td>
                                            <td className="p-3 text-right">
                                                <button
                                                    onClick={() => setDispatch(n)}
                                                    className="inline-flex items-center space-x-1 px-2.5 py-1.5 bg-[#1c1917] hover:bg-stone-800 text-white text-[11px] font-medium rounded-lg transition-all"
                                                >
                                                    <Send className="w-3 h-3" />
                                                    <span>Dispatch</span>
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </Card>
                </>
            )}

            {dispatch && zoneId && (
                <DispatchNodeModal
                    zoneId={zoneId}
                    node={dispatch}
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

function DispatchNodeModal({
    zoneId,
    node,
    onClose,
    onDone,
}: {
    zoneId: string
    node: api.PPAItem
    onClose: () => void
    onDone: (msg: string) => void
}) {
    const [notes, setNotes] = useState(
        `Pin-point check at ${node.node_id} (${node.distance_from_source_km.toFixed(1)} km, drop ${node.pressure_drop_bar.toFixed(2)} bar, P=${node.leak_probability.toFixed(2)})`,
    )
    const [cost, setCost] = useState('15000')
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState<string | null>(null)

    const submit = async () => {
        setBusy(true)
        setErr(null)
        try {
            const created = await api.createAction({
                zone_id: zoneId,
                action_type: `Acoustic leak pin-pointing — ${node.node_id}`,
                urgency: node.leak_probability >= 0.7 ? 'HIGH' : 'MEDIUM',
                estimated_cost: Number(cost) || 0,
                estimated_payback_days: 30,
                officer_notes: notes,
            })
            onDone(`Action #${created.id} created for ${node.node_id} — pending officer approval.`)
        } catch (e) {
            setErr((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Dispatch survey crew — ${node.node_id}`}
            onClose={onClose}
            footer={
                <>
                    <button onClick={onClose} className={btnSecondary}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={busy} className={btnPrimary}>
                        {busy ? 'Creating…' : 'Create dispatch action'}
                    </button>
                </>
            }
        >
            <div className="rounded-lg bg-[#fbfaf8] border border-[#dad6cb] p-3 text-[11px] text-stone-600">
                Files a PENDING action for a physical verification of this simulated PPA node.
                Pressure values above are <strong>not</strong> from field sensors.
            </div>
            <Field label="Officer notes">
                <textarea className={`${inputCls} h-20 resize-none`} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
                <Field label="Est. cost (₹)">
                    <input className={inputCls} type="number" min={0} value={cost} onChange={(e) => setCost(e.target.value)} />
                </Field>
                <Field label="Urgency">
                    <select className={inputCls} defaultValue={node.leak_probability >= 0.7 ? 'HIGH' : 'MEDIUM'}>
                        {['URGENT', 'HIGH', 'MEDIUM', 'LOW'].map((u) => (
                            <option key={u}>{u}</option>
                        ))}
                    </select>
                </Field>
            </div>
            {err && <div className="text-[11px] text-rose-700">{err}</div>}
        </Modal>
    )
}
