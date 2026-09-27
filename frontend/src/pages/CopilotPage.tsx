import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
    Bot,
    Play,
    Send,
    AlertTriangle,
    Lightbulb,
    Database,
    Clock,
    FileText,
    CheckCircle2,
    Zap,
} from 'lucide-react'
import * as api from '../lib/api'
import { useAsync, useStore } from '../lib/store'
import { fmtPct, fmtML, fmtINR, fmtDateTime, severityClass } from '../lib/format'
import {
    Card,
    SectionTitle,
    ErrorState,
    Spinner,
    Pill,
    EmptyState,
    InlineNotice,
    btnPrimary,
    inputCls,
    Toast,
} from '../components/ui'

/* =========================================================================
   AI Copilot — POST /agent/investigate (live Groq tool-loop),
   rendered evidence + recommendations, POST /agent/create-action per
   recommendation (deterministic financial inputs from /data/nrw-forecast
   or /revenue/payback), history from GET /agent/memory/{zone_id}.
   ai_available=false falls back to an explicit honest banner.
   ========================================================================= */

const SUGGESTIONS = [
    'Why is this zone at risk?',
    'Which loss type dominates here — physical or commercial?',
    'What should the field team do first?',
    'Is there any water-quality contamination correlation in this zone?',
]

export default function CopilotPage() {
    const { zones, refresh } = useStore()
    const [params, setParams] = useSearchParams()
    const zoneParam = params.get('zone') || zones[0]?.id || ''
    const questionParam = params.get('q') || ''

    const [question, setQuestion] = useState(questionParam || SUGGESTIONS[0])
    const [running, setRunning] = useState(false)
    const [result, setResult] = useState<api.AgentInvestigation | null>(null)
    const [runError, setRunError] = useState<string | null>(null)
    const [elapsed, setElapsed] = useState<number | null>(null)
    const [toast, setToast] = useState<string | null>(null)
    const [creatingIdx, setCreatingIdx] = useState<number | null>(null)
    const resultRef = useRef<HTMLDivElement>(null)

    const memory = useAsync<api.AgentMemoryItem[]>(
        () => (zoneParam ? api.getMemory(zoneParam) : Promise.resolve([])),
        [zoneParam],
    )
    // deterministic financial inputs for action creation
    const financials = useAsync<{ forecast: api.NRWForecast; payback: api.Payback } | null>(
        () =>
            zoneParam
                ? Promise.all([api.getForecast(zoneParam), api.getPayback(zoneParam)]).then(
                      ([forecast, payback]) => ({ forecast, payback }),
                  )
                : Promise.resolve(null),
        [zoneParam],
    )

    const zone = zones.find((z) => z.id === zoneParam)

    const setZone = (zid: string) => {
        const next = new URLSearchParams(params)
        next.set('zone', zid)
        setParams(next)
        setResult(null)
        setRunError(null)
    }

    const run = async () => {
        if (!zoneParam) return
        setRunning(true)
        setRunError(null)
        setResult(null)
        const started = performance.now()
        try {
            const res = await api.agentInvestigate(zoneParam, question)
            setResult(res)
            setElapsed((performance.now() - started) / 1000)
            memory.reload()
            refresh() // sidebar badge / investigations banner elsewhere
        } catch (e) {
            setRunError((e as Error).message)
        } finally {
            setRunning(false)
        }
    }

    useEffect(() => {
        if (result) resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, [result])

    const dailyLoss = useMemo(() => {
        if (!financials.data) return null
        return (
            financials.data.forecast.current_loss_litres_per_day ??
            financials.data.payback.daily_loss_litres
        )
    }, [financials.data])

    const createFromRecommendation = async (r: api.Recommendation, idx: number) => {
        if (!zoneParam || dailyLoss === null) return
        setCreatingIdx(idx)
        try {
            const res = await api.agentCreateAction({
                zone_id: zoneParam,
                action: r.action,
                priority: r.priority,
                reason: r.reason,
                daily_loss_litres: dailyLoss,
            })
            setToast(
                `Action #${res.action_id} created — ${res.message} Open Revenue & Actions to approve.`,
            )
        } catch (e) {
            setToast((e as Error).message)
        } finally {
            setCreatingIdx(null)
        }
    }

    if (zones.length === 0) return <Spinner label="Loading zones…" />

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* ------------------------------------------------ runner */}
            <div className="lg:col-span-2 space-y-6">
                <Card>
                    <SectionTitle
                        icon={Bot}
                        right={<Pill className="bg-stone-800 text-stone-100">AGENT</Pill>}
                    >
                        Investigate a zone
                    </SectionTitle>

                    <div className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <label className="block space-y-1.5">
                                <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                                    Zone
                                </span>
                                <select
                                    className={inputCls}
                                    value={zoneParam}
                                    onChange={(e) => setZone(e.target.value)}
                                >
                                    {zones.map((z) => (
                                        <option key={z.id} value={z.id}>
                                            {z.name} ({z.id})
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="block space-y-1.5">
                                <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                                    Status
                                </span>
                                <div
                                    className={`${inputCls} flex items-center space-x-2 text-stone-500`}
                                >
                                    <span
                                        className={`w-2 h-2 rounded-full ${running ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'}`}
                                    ></span>
                                    <span>{running ? 'Investigating…' : 'Ready'}</span>
                                </div>
                            </label>
                        </div>

                        <div className="space-y-2">
                            <textarea
                                className={`${inputCls} h-20 resize-none`}
                                value={question}
                                onChange={(e) => setQuestion(e.target.value)}
                                placeholder="Ask the copilot about this zone…"
                            />
                            <div className="flex flex-wrap gap-1.5">
                                {SUGGESTIONS.map((s) => (
                                    <button
                                        key={s}
                                        onClick={() => setQuestion(s)}
                                        className="px-2.5 py-1 bg-[#fbfaf8] border border-[#dad6cb] rounded-full text-[10px] text-stone-600 hover:bg-[#f3f0e8] transition-colors"
                                    >
                                        {s}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="flex items-center space-x-3">
                            <button
                                onClick={run}
                                disabled={running || !zoneParam}
                                className="inline-flex items-center space-x-2 bg-[#1c1917] hover:bg-stone-800 text-white px-4 py-2.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
                            >
                                <Play className="w-3.5 h-3.5" />
                                <span>{running ? 'Running investigation…' : 'Run Investigation'}</span>
                            </button>
                            {elapsed !== null && (
                                <span className="text-[11px] text-stone-500 flex items-center space-x-1">
                                    <Clock className="w-3 h-3" />
                                    <span>last run took {elapsed.toFixed(1)}s (server-side LLM)</span>
                                </span>
                            )}
                        </div>
                    </div>
                </Card>

                {/* run error — honest, with retry */}
                {runError && <ErrorState error={runError} onRetry={run} />}
                {running && <Card><Spinner label="Agent is reading zone evidence — this takes ~6–10 seconds" /></Card>}

                {/* ------------------------------------------------ result */}
                <div ref={resultRef}>
                    {result && (
                        <div className="space-y-4">
                            {/* header + fallback banner */}
                            <Card>
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <div className="flex items-center space-x-2">
                                            <Pill
                                                className={
                                                    result.risk_level.toUpperCase() === 'CRITICAL' || result.risk_level.toUpperCase() === 'HIGH'
                                                        ? severityClass(result.risk_level)
                                                        : result.risk_level.toUpperCase() === 'MEDIUM'
                                                          ? severityClass('MEDIUM')
                                                          : 'bg-stone-200 text-stone-700'
                                                }
                                            >
                                                RISK: {result.risk_level}
                                            </Pill>
                                            <span className="text-[11px] text-stone-500">
                                                confidence {fmtPct(result.confidence * 100)}
                                            </span>
                                        </div>
                                        <div className="text-[11px] text-stone-500">
                                            likely cause:{' '}
                                            <span className="font-semibold text-stone-700">
                                                {result.likely_cause}
                                            </span>
                                        </div>
                                    </div>
                                    <Pill className={result.ai_available ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}>
                                        {result.ai_available ? 'AI MODEL RESPONDED' : 'AI UNAVAILABLE — FALLBACK'}
                                    </Pill>
                                </div>

                                {!result.ai_available && (
                                    <div className="mt-3">
                                        <InlineNotice tone="rose" title="The language model was not reached">
                                            This is the deterministic fallback response — evidence and
                                            recommendations may be empty. Check GROQ_API_KEY in
                                            backend/.env and that outbound HTTPS to Groq is allowed, then
                                            re-run.
                                        </InlineNotice>
                                    </div>
                                )}

                                <p className="text-sm leading-relaxed text-stone-700 mt-3">
                                    {result.summary}
                                </p>
                            </Card>

                            {/* evidence */}
                            <Card>
                                <SectionTitle icon={Database} right={<Pill className="bg-blue-100 text-blue-800">trace</Pill>}>
                                    Evidence trace ({result.evidence.length})
                                </SectionTitle>
                                {result.evidence.length === 0 ? (
                                    <EmptyState
                                        icon={Database}
                                        title="No evidence items returned"
                                        hint="The model returned no structured evidence for this run."
                                    />
                                ) : (
                                    <div className="space-y-2">
                                        {result.evidence.map((ev, i) => (
                                            <div
                                                key={i}
                                                className="p-3 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] flex flex-wrap items-start justify-between gap-2"
                                            >
                                                <div className="space-y-0.5">
                                                    <div className="text-xs font-semibold text-stone-800">
                                                        {ev.metric}
                                                    </div>
                                                    {ev.explanation && (
                                                        <div className="text-[11px] text-stone-500 leading-snug">
                                                            {ev.explanation}
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="text-right">
                                                    <div className="font-mono text-sm font-bold text-stone-900">
                                                        {typeof ev.value === 'number'
                                                            ? ev.value.toLocaleString('en-IN')
                                                            : String(ev.value)}
                                                        {ev.unit ? ` ${ev.unit}` : ''}
                                                    </div>
                                                    <Pill className="bg-stone-200 text-stone-600">{ev.source}</Pill>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </Card>

                            {/* recommendations */}
                            <Card>
                                <SectionTitle icon={Lightbulb} right={<Pill className="bg-amber-100 text-amber-800">approve flow</Pill>}>
                                    Recommendations ({result.recommendations.length})
                                </SectionTitle>
                                {result.recommendations.length === 0 ? (
                                    <EmptyState
                                        icon={Lightbulb}
                                        title="No recommendations returned"
                                        hint="The model returned an empty recommendation list for this run."
                                    />
                                ) : (
                                    <div className="space-y-3">
                                        {result.recommendations.map((r, i) => (
                                            <div
                                                key={i}
                                                className="p-4 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] space-y-2"
                                            >
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="text-xs font-bold text-stone-800">
                                                        {r.action}
                                                    </div>
                                                    <Pill className={severityClass((r.priority || '').toUpperCase())}>
                                                        {r.priority}
                                                    </Pill>
                                                </div>
                                                <div className="text-[11px] text-stone-500 leading-relaxed">
                                                    {r.reason}
                                                </div>
                                                <div className="flex items-center justify-between pt-1">
                                                    <span className="text-[10px] text-stone-400">
                                                        {dailyLoss !== null
                                                            ? `cost/payback computed from real daily loss ${fmtML(dailyLoss)} L`
                                                            : 'financial inputs loading…'}
                                                    </span>
                                                    <button
                                                        onClick={() => createFromRecommendation(r, i)}
                                                        disabled={creatingIdx !== null || dailyLoss === null}
                                                        className="inline-flex items-center space-x-1.5 bg-[#1c1917] hover:bg-stone-800 text-white px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all disabled:opacity-50"
                                                    >
                                                        <Send className="w-3 h-3" />
                                                        <span>
                                                            {creatingIdx === i
                                                                ? 'Creating…'
                                                                : 'Create Action'}
                                                        </span>
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </Card>

                            {/* missing data */}
                            {result.missing_data.length > 0 && (
                                <Card>
                                    <SectionTitle icon={AlertTriangle}>Declared Missing Data</SectionTitle>
                                    <div className="flex flex-wrap gap-1.5">
                                        {result.missing_data.map((m) => (
                                            <Pill key={m} className="bg-amber-100 text-amber-800">
                                                {m}
                                            </Pill>
                                        ))}
                                    </div>
                                    <p className="text-[10px] text-stone-400 mt-2">
                                        Declared by the model during this run (not derived by the
                                        frontend).
                                    </p>
                                </Card>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* ------------------------------------------ memory history */}
            <div className="space-y-6">
                <Card>
                    <SectionTitle icon={FileText} right={<Pill className="bg-stone-800 text-stone-100">memory</Pill>}>
                        Investigation Memory
                    </SectionTitle>
                    <div className="text-[10px] text-stone-400 mb-3">
                        GET /agent/memory/{zoneParam || '{zone_id}'}
                    </div>
                    {memory.loading && <Spinner label="Loading memory…" />}
                    {memory.error && <ErrorState error={memory.error} onRetry={memory.reload} />}
                    {memory.data && memory.data.length === 0 && !memory.loading && (
                        <EmptyState
                            icon={FileText}
                            title="No memory for this zone yet"
                            hint="Every successful investigation appends a memory row that future runs read as context."
                        />
                    )}
                    {memory.data && memory.data.length > 0 && (
                        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                            {memory.data.map((m) => (
                                <div
                                    key={m.id}
                                    className="p-3 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] space-y-1"
                                >
                                    <div className="flex items-center justify-between">
                                        <Pill className="bg-stone-200 text-stone-700">#{m.id}</Pill>
                                        <span className="text-[10px] text-stone-400">
                                            {fmtDateTime(m.timestamp)}
                                        </span>
                                    </div>
                                    <div className="text-[11px] text-stone-700 leading-snug">
                                        {m.summary}
                                    </div>
                                    {m.action_taken && (
                                        <div className="text-[10px] text-stone-500 flex items-start space-x-1">
                                            <CheckCircle2 className="w-3 h-3 mt-0.5 text-emerald-600" />
                                            <span>{m.action_taken}</span>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </Card>

                <Card>
                    <SectionTitle icon={Zap}>Zone context</SectionTitle>
                    <div className="space-y-2 text-xs">
                        <Row k="Zone" v={zone ? zone.name : zoneParam} />
                        <Row
                            k="Daily loss (real)"
                            v={dailyLoss !== null ? `${fmtML(dailyLoss)} L` : 'loading…'}
                        />
                        <Row
                            k="Est. daily ₹ at risk"
                            v={
                                dailyLoss !== null && zone
                                    ? fmtINR(dailyLoss * zone.tariff_rate)
                                    : '—'
                            }
                        />
                        <Row
                            k="Payback source"
                            v={financials.data?.payback.data_source ?? '—'}
                        />
                    </div>
                </Card>
            </div>

            {toast && (
                <Toast
                    message={toast}
                    tone={toast.startsWith('Action #') ? 'emerald' : 'rose'}
                    onClose={() => setToast(null)}
                />
            )}
        </div>
    )
}

function Row({ k, v }: { k: string; v: string }) {
    return (
        <div className="flex items-center justify-between p-2 rounded-lg bg-[#fbfaf8] border border-[#dad6cb]">
            <span className="text-[11px] text-stone-500">{k}</span>
            <span className="text-[11px] font-semibold text-stone-800 text-right">{v}</span>
        </div>
    )
}
