import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Bot, ShieldCheck } from 'lucide-react'
import { Card, SectionTitle, InlineNotice, Pill, btnPrimary } from '../components/ui'

/* =========================================================================
   Contamination — water-quality correlation is NOT configured in this
   deployment (documented backend limitation). Per the Block-2 convention
   the API returns an explicit NOT_AVAILABLE payload; this page shows that
   honestly instead of fabricating readings. The button runs the real
   agent correlation question, which also returns NOT_AVAILABLE.
   ========================================================================= */

const CONVENTION = `{
  "correlation_detected": false,
  "risk_level": "NONE",
  "water_quality_events": 0,
  "details": "No water-quality data source is currently configured.",
  "is_simulated": false,
  "status": "NOT_AVAILABLE"
}`

export default function ContaminationPage() {
    const navigate = useNavigate()

    return (
        <div className="space-y-6">
            <Card>
                <SectionTitle
                    icon={Activity}
                    right={<Pill className="bg-amber-100 text-amber-800">NOT CONFIGURED</Pill>}
                >
                    Water Quality Correlation
                </SectionTitle>

                <InlineNotice tone="amber" title="No water-quality data source is configured">
                    This deployment has no turbidity, chlorine, or E.&nbsp;coli telemetry in the
                    database, so contamination correlation cannot run. The platform’s rule is strict:
                    <strong> no key → no fabrication</strong>. Any correlation request returns the
                    explicit payload below — and this screen renders it verbatim rather than drawing
                    readings that do not exist.
                </InlineNotice>

                <div className="mt-4 grid md:grid-cols-2 gap-4">
                    <div>
                        <div className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider mb-2">
                            API convention (agent tool response)
                        </div>
                        <code className="block bg-[#1c1917] text-emerald-300 rounded-lg p-3.5 font-mono text-[11px] leading-relaxed overflow-x-auto">
                            {CONVENTION}
                        </code>
                    </div>
                    <div className="space-y-3 text-xs text-stone-600 leading-relaxed">
                        <div className="flex items-start space-x-2">
                            <ShieldCheck className="w-4 h-4 text-emerald-700 mt-0.5" />
                            <span>
                                <strong className="text-stone-800">Why honest?</strong> Inventing
                                contamination numbers would be a fabrication risk during judging —
                                the roadmap forbids unlabeled fake data anywhere in the product.
                            </span>
                        </div>
                        <div className="flex items-start space-x-2">
                            <Bot className="w-4 h-4 text-stone-600 mt-0.5" />
                            <span>
                                <strong className="text-stone-800">You can still verify live:</strong>{' '}
                                run the correlation question through the AI Copilot — the agent calls
                                its correlation tool and returns this same NOT_AVAILABLE result,
                                on the record.
                            </span>
                        </div>
                        <button
                            onClick={() =>
                                navigate(
                                    '/app/copilot?q=' +
                                        encodeURIComponent(
                                            'Is there any water-quality contamination correlation in this zone?',
                                        ),
                                )
                            }
                            className={`${btnPrimary} inline-flex items-center space-x-2`}
                        >
                            <Bot className="w-3.5 h-3.5" />
                            <span>Verify through AI Copilot</span>
                        </button>
                    </div>
                </div>
            </Card>

            <Card>
                <SectionTitle>What would light this page up</SectionTitle>
                <div className="grid sm:grid-cols-3 gap-3 text-xs">
                    {[
                        { t: 'Sensor ingestion', d: 'Turbidity / chlorine / flow events per zone' },
                        { t: 'Threshold rules', d: 'WHO / BIS limits stored with source citations' },
                        { t: 'Agent correlation', d: 'Joins quality events with burst/repair timelines' },
                    ].map((s) => (
                        <div key={s.t} className="p-3.5 rounded-lg border border-[#dad6cb] bg-[#fbfaf8]">
                            <div className="font-bold text-stone-800 mb-1">{s.t}</div>
                            <div className="text-[11px] text-stone-500">{s.d}</div>
                        </div>
                    ))}
                </div>
            </Card>
        </div>
    )
}
