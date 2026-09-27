import React, { useRef, useState } from 'react'
import { Upload, FileText, CheckCircle2, AlertTriangle, Download, Database } from 'lucide-react'
import * as api from '../lib/api'
import { downloadText } from '../lib/format'
import {
    Card,
    SectionTitle,
    Pill,
    InlineNotice,
    btnPrimary,
    btnSecondary,
    Spinner,
} from '../components/ui'

/* =========================================================================
   Data Upload — real POST /data/upload-csv (multipart). Accepts the two
   CSV shapes the backend documents (readings / billing), shows the exact
   insert counts + per-row warnings returned by the API, and offers sample
   CSVs that are guaranteed to parse.
   ========================================================================= */

const READINGS_SAMPLE = `zone_id,inflow_litres,timestamp,night_flow_litres,pressure_bar
zone_1,51000000,2026-09-27T02:00:00,1850000,2.8
zone_2,57000000,2026-09-27T02:00:00,2400000,2.5
`

const BILLING_SAMPLE = `zone_id,consumer_id,billed_litres,benchmark_litres,billing_period,household_size,property_type
zone_1,C-90001,42000,18000,2026-09,4,residential
zone_1,C-90002,15500,16200,2026-09,3,residential
`

export default function DataUploadPage() {
    const inputRef = useRef<HTMLInputElement>(null)
    const [file, setFile] = useState<File | null>(null)
    const [busy, setBusy] = useState(false)
    const [result, setResult] = useState<api.CSVUploadResult | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [dragOver, setDragOver] = useState(false)

    const doUpload = async (f: File) => {
        setBusy(true)
        setError(null)
        setResult(null)
        try {
            const res = await api.uploadCSV(f)
            setResult(res)
        } catch (e) {
            setError((e as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const onDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setDragOver(false)
        const f = e.dataTransfer.files?.[0]
        if (f) {
            setFile(f)
            doUpload(f)
        }
    }

    return (
        <div className="space-y-6">
            <Card>
                <SectionTitle icon={Upload} right={<Pill className="bg-stone-800 text-stone-100">POST /data/upload-csv</Pill>}>
                    Smart Meter &amp; SCADA Data Upload
                </SectionTitle>

                <div
                    onDragOver={(e) => {
                        e.preventDefault()
                        setDragOver(true)
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={onDrop}
                    className={`border-2 border-dashed rounded-xl p-8 text-center space-y-3 transition-colors ${
                        dragOver ? 'border-emerald-400 bg-emerald-50/50' : 'border-[#dad6cb] bg-[#fbfaf8]'
                    }`}
                >
                    <Upload className="w-8 h-8 text-stone-400 mx-auto" />
                    <div className="text-xs font-semibold text-stone-700">
                        Drag &amp; drop a CSV, or browse for one
                    </div>
                    <div className="text-[11px] text-stone-400">
                        Accepts .csv only — bad rows are skipped with warnings, valid rows always insert
                    </div>
                    <div className="flex items-center justify-center space-x-2">
                        <button
                            onClick={() => inputRef.current?.click()}
                            className="px-4 py-2 bg-[#1c1917] text-white text-xs rounded-lg font-medium hover:bg-stone-800"
                        >
                            Browse Files
                        </button>
                        {file && (
                            <span className="text-[11px] text-stone-600 flex items-center space-x-1">
                                <FileText className="w-3.5 h-3.5" />
                                <span>{file.name}</span>
                            </span>
                        )}
                    </div>
                    <input
                        ref={inputRef}
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={(e) => {
                            const f = e.target.files?.[0]
                            if (f) {
                                setFile(f)
                                doUpload(f)
                            }
                        }}
                    />
                </div>

                {busy && <div className="mt-4"><Spinner label="Uploading and parsing…" /></div>}
                {error && (
                    <div className="mt-4">
                        <InlineNotice tone="rose" title="Upload failed">
                            {error}
                        </InlineNotice>
                    </div>
                )}

                {result && (
                    <div className="mt-4 space-y-3">
                        <div className="grid grid-cols-2 gap-3 text-xs">
                            <div className="p-3.5 rounded-lg border border-emerald-200 bg-emerald-50">
                                <div className="flex items-center space-x-1.5 text-emerald-800 font-bold">
                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                    <span>Readings inserted</span>
                                </div>
                                <div className="text-xl font-black text-emerald-900 mt-1">
                                    {result.readings_inserted}
                                </div>
                            </div>
                            <div className="p-3.5 rounded-lg border border-emerald-200 bg-emerald-50">
                                <div className="flex items-center space-x-1.5 text-emerald-800 font-bold">
                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                    <span>Billing records inserted</span>
                                </div>
                                <div className="text-xl font-black text-emerald-900 mt-1">
                                    {result.billing_records_inserted}
                                </div>
                            </div>
                        </div>
                        {result.warnings.length > 0 && (
                            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2">
                                <div className="flex items-center space-x-1.5 text-amber-800 text-xs font-bold">
                                    <AlertTriangle className="w-3.5 h-3.5" />
                                    <span>{result.warnings.length} row warning(s)</span>
                                </div>
                                <div className="max-h-40 overflow-y-auto space-y-1">
                                    {result.warnings.map((w, i) => (
                                        <div key={i} className="text-[11px] text-amber-800 font-mono">
                                            {w}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </Card>

            {/* schemas + samples */}
            <div className="grid md:grid-cols-2 gap-6">
                <Card>
                    <SectionTitle icon={FileText}>Accepted schemas</SectionTitle>
                    <div className="space-y-3 text-[11px]">
                        <div>
                            <div className="font-bold text-stone-800 mb-1">Readings CSV</div>
                            <code className="block bg-[#1c1917] text-stone-200 rounded-lg p-2.5 font-mono leading-relaxed">
                                zone_id, inflow_litres, timestamp
                                <br />
                                <span className="text-stone-500">
                                    optional: night_flow_litres, pressure_bar
                                </span>
                            </code>
                        </div>
                        <div>
                            <div className="font-bold text-stone-800 mb-1">Billing CSV</div>
                            <code className="block bg-[#1c1917] text-stone-200 rounded-lg p-2.5 font-mono leading-relaxed">
                                zone_id, consumer_id, billed_litres,
                                <br />
                                benchmark_litres, billing_period
                                <br />
                                <span className="text-stone-500">
                                    optional: household_size, property_type
                                </span>
                            </code>
                        </div>
                        <button
                            onClick={() =>
                                downloadText('sample-readings.csv', READINGS_SAMPLE)
                            }
                            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] rounded-lg font-medium text-stone-700"
                        >
                            <Download className="w-3.5 h-3.5" />
                            <span>Sample readings CSV</span>
                        </button>{' '}
                        <button
                            onClick={() => downloadText('sample-billing.csv', BILLING_SAMPLE)}
                            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] rounded-lg font-medium text-stone-700"
                        >
                            <Download className="w-3.5 h-3.5" />
                            <span>Sample billing CSV</span>
                        </button>
                    </div>
                </Card>

                <Card>
                    <SectionTitle icon={Database}>Where data lands</SectionTitle>
                    <InlineNotice tone="blue" title="Shared demo database">
                        Uploads insert into the live database used by the demo:
                        <span className="font-mono"> raw_readings</span> and{' '}
                        <span className="font-mono">billing_records</span>. Unknown zone IDs and
                        negative values are skipped row-by-row with the warnings shown above. If you
                        need a clean state afterwards, delete the rows you added or re-run the
                        documented seed.
                    </InlineNotice>
                    <div className="text-[11px] text-stone-500 mt-3 leading-relaxed">
                        Readings feed the water-balance and trend engines; billing records feed the
                        isolation-forest audit on the Billing Audit screen.
                    </div>
                </Card>
            </div>
        </div>
    )
}
