/* =========================================================================
   Formatting helpers — INR (Indian) number formats, litres/ML, dates,
   CSV export. All display of backend figures flows through here so the
   numbers on screen always match the database.
   ========================================================================= */

/** ₹650.7M / ₹1.84L / ₹85,000 — M for millions (>= ₹1 Cr), L for lakhs. */
export function fmtINR(n: number | null | undefined, decimals = 1): string {
    if (n === null || n === undefined || Number.isNaN(n)) return '—'
    const abs = Math.abs(n)
    if (abs >= 1e7) return `₹${(n / 1e6).toFixed(decimals)}M`
    if (abs >= 1e5) return `₹${(n / 1e5).toFixed(2)}L`
    return `₹${Math.round(n).toLocaleString('en-IN')}`
}

export function fmtInt(n: number | null | undefined): string {
    if (n === null || n === undefined || Number.isNaN(n)) return '—'
    return Math.round(n).toLocaleString('en-IN')
}

export function fmtPct(n: number | null | undefined, decimals = 1): string {
    if (n === null || n === undefined || Number.isNaN(n)) return '—'
    return `${n.toFixed(decimals)}%`
}

/** Litres → compact display: 37,548,643 L or 37.55 ML */
export function fmtLitres(l: number | null | undefined): string {
    if (l === null || l === undefined || Number.isNaN(l)) return '—'
    const abs = Math.abs(l)
    if (abs >= 1e6) return `${(l / 1e6).toFixed(2)} ML`
    return `${Math.round(l).toLocaleString('en-IN')} L`
}

export function fmtML(l: number | null | undefined, decimals = 2): string {
    if (l === null || l === undefined || Number.isNaN(l)) return '—'
    return `${(l / 1e6).toFixed(decimals)} ML`
}

/** Axis-label compaction for chart ticks (12000 → 12K). */
export function fmtCompact(n: number): string {
    const abs = Math.abs(n)
    if (abs >= 1e9) return `${(n / 1e9).toFixed(1)}B`
    if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`
    if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`
    return `${Math.round(n)}`
}

export function fmtDate(iso: string | null | undefined): string {
    if (!iso) return '—'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return '—'
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateTime(iso: string | null | undefined): string {
    if (!iso) return '—'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return '—'
    return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
}

export function fmtDayMonth(iso: string | number | Date): string {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

/* ------------------------------------------------------------- CSV export */

function csvEscape(v: unknown): string {
    if (v === null || v === undefined) return ''
    const s = String(v)
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
    return s
}

export function downloadText(filename: string, text: string, mime = 'text/csv;charset=utf-8') {
    const blob = new Blob([text], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export function toCSV(rows: Record<string, unknown>[]): string {
    if (rows.length === 0) return ''
    const headers = Object.keys(rows[0])
    const lines = [headers.join(',')]
    for (const row of rows) lines.push(headers.map((h) => csvEscape(row[h])).join(','))
    return lines.join('\r\n')
}

export function downloadCSV(filename: string, rows: Record<string, unknown>[]) {
    downloadText(filename, toCSV(rows))
}

/* --------------------------------------------------------- status display */

const SEVERITY_CLASS: Record<string, string> = {
    CRITICAL: 'bg-rose-100 text-rose-800',
    HIGH: 'bg-amber-100 text-amber-800',
    MEDIUM: 'bg-blue-100 text-blue-800',
    LOW: 'bg-stone-200 text-stone-700',
    NONE: 'bg-stone-200 text-stone-700',
}

export function severityClass(sev: string): string {
    return SEVERITY_CLASS[(sev || '').toUpperCase()] || 'bg-stone-200 text-stone-700'
}

const STATUS_CLASS: Record<string, string> = {
    ACTIVE: 'bg-rose-100 text-rose-800',
    RESOLVED: 'bg-emerald-100 text-emerald-800',
    PENDING: 'bg-amber-100 text-amber-800',
    APPROVED: 'bg-emerald-100 text-emerald-800',
    REJECTED: 'bg-rose-100 text-rose-800',
    ONLINE: 'bg-emerald-100 text-emerald-800',
}

export function statusClass(status: string): string {
    return STATUS_CLASS[(status || '').toUpperCase()] || 'bg-stone-200 text-stone-700'
}

const URGENCY_CLASS: Record<string, string> = {
    URGENT: 'bg-rose-100 text-rose-800',
    HIGH: 'bg-amber-100 text-amber-800',
    MEDIUM: 'bg-blue-100 text-blue-800',
    LOW: 'bg-stone-200 text-stone-700',
}

export function urgencyClass(urgency: string): string {
    return URGENCY_CLASS[(urgency || '').toUpperCase()] || 'bg-stone-200 text-stone-700'
}

/** Zone status relative to the 55% Lucknow NRW anchor — honest labels only. */
export function zoneStatus(nrw: number | null, anchor: number) {
    if (nrw === null || Number.isNaN(nrw)) {
        return { label: 'NO DATA', cls: 'bg-stone-200 text-stone-700' }
    }
    if (nrw > anchor + 10) return { label: 'SEVERELY ABOVE ANCHOR', cls: 'bg-rose-100 text-rose-800' }
    if (nrw > anchor) return { label: 'ABOVE ANCHOR', cls: 'bg-amber-100 text-amber-800' }
    return { label: 'WITHIN ANCHOR', cls: 'bg-emerald-100 text-emerald-800' }
}
