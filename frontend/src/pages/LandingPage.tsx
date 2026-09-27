import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    ArrowRight,
    Activity,
    CheckCircle2,
    Bot,
    BarChart3,
    Database,
    FileText,
    Radio,
    Shield,
    Server,
} from 'lucide-react'
import * as api from '../lib/api'
import { useAsync } from '../lib/store'
import { fmtINR, fmtInt, fmtPct } from '../lib/format'
import { townFlowLitresPerMinute } from '../lib/derive'

/* =========================================================================
   Landing page — matches the approved hero design 1:1 (cream #f0eee9,
   black pill CTAs, emerald accents), plus real API status, real town
   telemetry, and working anchor navigation.
   ========================================================================= */

const SECTIONS = ['platform', 'architecture', 'capabilities', 'use-cases', 'about'] as const
type Section = (typeof SECTIONS)[number]

export default function LandingPage() {
    const navigate = useNavigate()
    const [active, setActive] = useState<Section>('platform')

    const root = useAsync(() => api.getRoot().catch(() => null), [])
    const snaps = useAsync(() => api.getNRWSummary().catch(() => [] as api.NRWSnapshot[]), [])
    const town = useAsync(() => api.getTownProfile().catch(() => null), [])

    const online = !!root.data && root.data.status === 'online'
    const flowPerMin = snaps.data ? townFlowLitresPerMinute(snaps.data) : 0
    const flowLabel =
        flowPerMin >= 1000 ? `${(flowPerMin / 1000).toFixed(1)}K` : flowPerMin.toFixed(0)

    const scrollTo = (id: Section) => {
        setActive(id)
        document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }

    return (
        <div className="min-h-screen w-full bg-[#f0eee9] text-[#111111] font-sans antialiased selection:bg-amber-200 selection:text-black">
            {/* ============================ HERO ============================ */}
            <div className="relative min-h-screen flex flex-col justify-between overflow-hidden">
                {/* background image */}
                <div className="absolute inset-0 w-full h-full z-0 overflow-hidden">
                    <img
                        src="/hero_water_sensor.jpg"
                        alt="AltoMare Background"
                        className="w-full h-full object-cover object-center scale-105 opacity-85 mix-blend-multiply"
                    />
                    <div className="absolute inset-0 bg-gradient-to-r from-[#f0eee9]/90 via-[#f0eee9]/60 to-transparent"></div>
                </div>

                {/* navbar */}
                <header className="relative z-50 backdrop-blur-md bg-[#f0eee9]/70 border-b border-neutral-300/40 px-8 py-3.5">
                    <div className="max-w-7xl mx-auto flex items-center justify-between">
                        <div
                            className="flex items-center cursor-pointer"
                            onClick={() => scrollTo('platform')}
                        >
                            <span className="font-extrabold text-2xl sm:text-3xl tracking-tighter text-neutral-900">
                                altomare
                                <span className="text-xs font-serif font-normal text-neutral-400 ml-0.5">™</span>
                            </span>
                        </div>

                        <nav className="hidden md:flex items-center space-x-1 bg-neutral-300/40 p-1 rounded-full border border-neutral-300/50 text-xs font-medium text-neutral-600">
                            {SECTIONS.map((s) => (
                                <button
                                    key={s}
                                    onClick={() => scrollTo(s)}
                                    className={`px-4 py-1 rounded-full transition-colors ${
                                        active === s
                                            ? 'bg-white/90 text-neutral-900 shadow-sm font-semibold'
                                            : 'hover:text-neutral-900'
                                    }`}
                                >
                                    {s === 'use-cases'
                                        ? 'Use Cases'
                                        : s.charAt(0).toUpperCase() + s.slice(1)}
                                </button>
                            ))}
                        </nav>

                        <div className="flex items-center space-x-4">
                            <span className="text-xs font-semibold text-neutral-700 px-2 py-1.5">
                                API Status:{' '}
                                <span
                                    className={`font-mono text-xs font-bold ${online ? 'text-emerald-600' : 'text-rose-600'}`}
                                >
                                    ● {online ? `${root.data!.version} Online` : 'Offline'}
                                </span>
                            </span>
                            <button
                                onClick={() => navigate('/app')}
                                className="px-5 py-2 rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white font-semibold text-xs shadow-sm hover:shadow-md transition-all flex items-center space-x-2 group"
                            >
                                <span>Get Started</span>
                                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                            </button>
                        </div>
                    </div>
                </header>

                {/* hero content */}
                <main className="relative z-10 max-w-7xl mx-auto px-8 my-auto w-full py-14">
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
                        <div className="lg:col-span-7 space-y-6">
                            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-100/90 border border-emerald-300/80 text-emerald-950 text-[11px] font-bold tracking-wide uppercase backdrop-blur-md shadow-sm">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span>Telemetry &amp; Intelligence Active</span>
                            </div>

                            <div className="space-y-1">
                                <p className="text-neutral-700 font-semibold text-lg sm:text-xl tracking-tight">
                                    Hello, Operator.
                                </p>
                                <h1 className="text-5xl sm:text-6xl font-black tracking-tight text-neutral-900 leading-[1.05]">
                                    Let’s plug the leaks.
                                </h1>
                            </div>

                            <p className="text-base sm:text-lg text-neutral-800 leading-relaxed font-medium max-w-xl">
                                <strong className="text-neutral-950 font-black">ALTOMARE</strong> observes how
                                your municipal water distribution network operates, understands non-revenue
                                water patterns, and turns physical &amp; billing loss into reliable revenue.
                            </p>

                            <div className="flex flex-wrap items-center gap-3 pt-1">
                                <button
                                    onClick={() => navigate('/app')}
                                    className="px-7 py-3.5 rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white font-bold text-sm shadow-xl hover:shadow-2xl transition-all flex items-center space-x-2.5 group"
                                >
                                    <span>Start Observing</span>
                                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                                </button>
                                <button
                                    onClick={() => navigate('/app/dashboard')}
                                    className="px-6 py-3.5 rounded-xl bg-white/95 hover:bg-white border border-neutral-300 text-neutral-900 font-bold text-sm shadow-sm hover:shadow-md transition-all backdrop-blur-md"
                                >
                                    Go to Dashboard
                                </button>
                                <button
                                    onClick={() => scrollTo('platform')}
                                    className="text-xs font-bold text-neutral-700 hover:text-neutral-950 transition-colors px-2 py-2 flex items-center space-x-1"
                                >
                                    <span>See How It Works</span>
                                    <span className="text-xs">→</span>
                                </button>
                            </div>

                            <div className="pt-5 border-t border-neutral-400/40 grid grid-cols-3 gap-4 text-[11px] font-extrabold text-neutral-600 uppercase tracking-widest">
                                <div className="flex items-center space-x-2">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                                    <span>OBSERVE</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-amber-700" />
                                    <span>UNDERSTAND</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-700" />
                                    <span>AUTOMATE</span>
                                </div>
                            </div>
                        </div>

                        {/* live telemetry badge — real sum of zone inflows */}
                        <div className="lg:col-span-5 relative flex justify-end items-center">
                            <div
                                className="bg-white/90 backdrop-blur-md px-6 py-4 rounded-2xl border border-neutral-200/90 shadow-2xl text-right space-y-1 transform hover:scale-105 transition-transform cursor-pointer"
                                onClick={() => navigate('/app/dashboard')}
                                title="Open the dashboard"
                            >
                                <div className="text-3xl font-black text-neutral-900 tracking-tight">
                                    {flowLabel}{' '}
                                    <span className="text-xs font-semibold text-neutral-500">L/min</span>
                                </div>
                                <div className="text-xs font-bold text-emerald-700 flex items-center justify-end space-x-1.5">
                                    <Activity className="w-4 h-4" />
                                    <span>Lucknow Grid Telemetry</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </main>

                <div className="relative z-10 pb-4"></div>
            </div>

            {/* ========================= SECTIONS ========================= */}
            <Sections online={online} town={town.data} flowLabel={flowLabel} />

            {/* footer */}
            <footer className="border-t border-[#dad6cb] bg-[#e8e6e0] px-8 py-6">
                <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-stone-600">
                    <span className="font-extrabold text-lg tracking-tighter text-[#1c1917]">
                        altomare<span className="text-[10px] font-serif font-normal text-stone-400 ml-0.5">™</span>
                    </span>
                    <span>SIH PS1288 — TRACE Non-Revenue Water Platform</span>
                    <button
                        onClick={() => navigate('/app')}
                        className="px-4 py-2 bg-[#1c1917] text-white rounded-lg font-semibold hover:bg-stone-800 transition-colors"
                    >
                        Open the platform →
                    </button>
                </div>
            </footer>
        </div>
    )
}

/* ------------------------------------------------------------ sections */

function SectionHeading({ id, kicker, title }: { id: string; kicker: string; title: string }) {
    return (
        <div id={id} className="scroll-mt-20 space-y-2 mb-8">
            <div className="text-[11px] font-black uppercase tracking-[0.2em] text-emerald-700">
                {kicker}
            </div>
            <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-neutral-900">{title}</h2>
        </div>
    )
}

function Sections({
    online,
    town,
    flowLabel,
}: {
    online: boolean
    town: api.TownProfile | null
    flowLabel: string
}) {
    const navigate = useNavigate()
    return (
        <div className="bg-[#f0eee9]">
            {/* Platform */}
            <section className="max-w-7xl mx-auto px-8 py-16">
                <SectionHeading id="platform" kicker="The Platform" title="One system, every loss stream." />
                <div className="grid md:grid-cols-3 gap-5">
                    {[
                        {
                            icon: Radio,
                            title: 'Physical loss detection',
                            body: 'Water-balance, UARL and MNF engines run against weekly NRWSnapshots for all 12 DMAs — alerts land in the database with method citations.',
                        },
                        {
                            icon: BarChart3,
                            title: 'Commercial loss audit',
                            body: 'Isolation-forest scoring (with rule fallback) flags billing anomalies per consumer; PPA localises bursts on simulated pressure grids.',
                        },
                        {
                            icon: Bot,
                            title: 'Agentic investigation',
                            body: 'A Groq tool-loop copilot reads zone evidence, explains likely cause in operator language, and files actions for officer approval.',
                        },
                    ].map((f) => (
                        <div
                            key={f.title}
                            className="bg-white/80 backdrop-blur-md p-6 rounded-xl border border-[#dad6cb] shadow-sm space-y-3"
                        >
                            <f.icon className="w-5 h-5 text-emerald-700" />
                            <div className="text-sm font-bold text-stone-900">{f.title}</div>
                            <p className="text-xs leading-relaxed text-stone-600">{f.body}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Architecture */}
            <section className="border-t border-[#dad6cb] bg-[#e8e6e0]/70">
                <div className="max-w-7xl mx-auto px-8 py-16">
                    <SectionHeading
                        id="architecture"
                        kicker="Architecture"
                        title="Deterministic engines, accountable AI."
                    />
                    <div className="grid md:grid-cols-2 gap-6">
                        <div className="space-y-3">
                            {[
                                {
                                    icon: Server,
                                    t: 'FastAPI + SQLAlchemy',
                                    d: 'Versioned REST surface (/openapi.json) over a PostgreSQL schema: zones, nrw_snapshots, leak_alerts, action_log, revenue_log, investigation_memory.',
                                },
                                {
                                    icon: Database,
                                    t: 'Lucknow-anchored seed',
                                    d: '55% town NRW and ₹650.7M/yr revenue loss cited from AMRUT 2.0 MIS and the Jal Shakti Annual Report — every figure traceable.',
                                },
                                {
                                    icon: Shield,
                                    t: 'Honest degradation',
                                    d: 'No key, no fabrication: missing sources return explicit NOT_AVAILABLE / fallback states that the UI displays verbatim.',
                                },
                            ].map((r) => (
                                <div
                                    key={r.t}
                                    className="flex items-start space-x-3 bg-white/80 p-4 rounded-xl border border-[#dad6cb]"
                                >
                                    <r.icon className="w-4 h-4 text-stone-700 mt-0.5" />
                                    <div>
                                        <div className="text-xs font-bold text-stone-800">{r.t}</div>
                                        <div className="text-[11px] text-stone-600 leading-relaxed mt-0.5">
                                            {r.d}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="bg-[#1c1917] text-stone-200 rounded-xl p-6 font-mono text-[11px] leading-relaxed overflow-x-auto">
                            <div className="text-stone-500"># live endpoints (GET /openapi.json)</div>
                            <div className="text-emerald-400">GET  /nrw/summary</div>
                            <div className="text-emerald-400">GET  /alerts</div>
                            <div className="text-emerald-400">GET  /audit/billing/&#123;zone_id&#125;</div>
                            <div className="text-emerald-400">GET  /audit/ppa/&#123;zone_id&#125;</div>
                            <div className="text-emerald-400">GET  /data/nrw-forecast/&#123;zone_id&#125;</div>
                            <div className="text-amber-400">POST /agent/investigate</div>
                            <div className="text-amber-400">POST /actions/approve/&#123;id&#125;</div>
                            <div className="text-stone-500 mt-2">
                                # status: <span className={online ? 'text-emerald-400' : 'text-rose-400'}>
                                    {online ? 'ONLINE' : 'OFFLINE'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Capabilities */}
            <section className="border-t border-[#dad6cb]">
                <div className="max-w-7xl mx-auto px-8 py-16">
                    <SectionHeading
                        id="capabilities"
                        kicker="Capabilities"
                        title="What operators do here."
                    />
                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                            { icon: AlertTriangleIcon, t: 'Live alerts', d: 'Severity, confidence, method citations, dispatch' },
                            { icon: FileText, t: 'Audit & reports', d: 'Billing anomalies, CSV exports, printable brief' },
                            { icon: Bot, t: 'Copilot workflow', d: 'Investigate → evidence → approve/reject actions' },
                            { icon: Radio, t: 'Data ingestion', d: 'CSV upload for readings & billing records' },
                        ].map((c) => (
                            <div
                                key={c.t}
                                className="bg-white/80 p-5 rounded-xl border border-[#dad6cb] shadow-sm space-y-2"
                            >
                                <c.icon className="w-4 h-4 text-emerald-700" />
                                <div className="text-xs font-bold text-stone-900">{c.t}</div>
                                <div className="text-[11px] text-stone-600">{c.d}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Use cases — real town profile */}
            <section className="border-t border-[#dad6cb] bg-[#e8e6e0]/70">
                <div className="max-w-7xl mx-auto px-8 py-16">
                    <SectionHeading
                        id="use-cases"
                        kicker="Use Cases"
                        title="Anchored to Lucknow."
                    />
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                            { v: fmtPct(town?.total_nrw_percent ?? 55), l: 'Town NRW (AMRUT 2.0 MIS)' },
                            { v: fmtINR(town?.estimated_annual_loss_inr ?? 650737500, 1), l: 'Annual revenue loss' },
                            { v: `${flowLabel} L/min`, l: 'Live network inflow' },
                            { v: fmtInt(town?.total_zones ?? 12), l: 'District metered areas' },
                        ].map((s) => (
                            <div
                                key={s.l}
                                className="bg-white/85 p-5 rounded-xl border border-[#dad6cb] shadow-sm space-y-1"
                            >
                                <div className="text-2xl font-black text-neutral-900 tracking-tight">{s.v}</div>
                                <div className="text-[11px] font-semibold text-stone-500 uppercase tracking-wider">
                                    {s.l}
                                </div>
                            </div>
                        ))}
                    </div>
                    {town && (
                        <p className="text-[11px] text-stone-500 mt-4 max-w-3xl leading-relaxed">
                            Source: {town.anchor_source_citation}
                        </p>
                    )}
                </div>
            </section>

            {/* About */}
            <section className="border-t border-[#dad6cb]">
                <div className="max-w-7xl mx-auto px-8 py-16 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div id="about" className="scroll-mt-20 max-w-2xl space-y-3">
                        <SectionHeading id="about-heading" kicker="About" title="Built for municipal water teams." />
                        <p className="text-sm text-stone-700 leading-relaxed">
                            AltoMare TRACE is a Smart India Hackathon (PS1288) build: an end-to-end NRW
                            reduction platform covering detection, investigation, approval workflow and
                            revenue recovery — designed so every number on screen is traceable to the
                            database or a cited public source.
                        </p>
                    </div>
                    <button
                        onClick={() => navigate('/app')}
                        className="px-7 py-3.5 rounded-xl bg-neutral-900 hover:bg-neutral-800 text-white font-bold text-sm shadow-xl transition-all flex items-center space-x-2.5 group"
                    >
                        <span>Enter the platform</span>
                        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </button>
                </div>
            </section>
        </div>
    )
}

function AlertTriangleIcon({ className }: { className?: string }) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
    )
}
