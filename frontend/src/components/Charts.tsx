import React from 'react'
import { fmtCompact, fmtDayMonth, fmtPct } from '../lib/format'

/* =========================================================================
   Dependency-free SVG charts, themed to match the app (stone / emerald /
   rose). Every series rendered here comes from live /nrw/summary data.
   ========================================================================= */

export interface ChartPoint {
    label: string
    value: number
}

export function LineChart({
    points,
    height = 180,
    anchor,
    anchorLabel,
    formatValue = (v: number) => fmtPct(v),
    color = '#1c1917',
}: {
    points: { t: string; value: number }[]
    height?: number
    anchor?: number
    anchorLabel?: string
    formatValue?: (v: number) => string
    color?: string
}) {
    if (points.length === 0) return null

    const w = 720
    const h = height
    const padL = 44
    const padR = 12
    const padT = 12
    const padB = 24

    const values = points.map((p) => p.value)
    if (anchor !== undefined) values.push(anchor)
    let min = Math.min(...values)
    let max = Math.max(...values)
    if (min === max) {
        min -= 1
        max += 1
    }
    const range = max - min

    const x = (i: number) =>
        padL + (points.length === 1 ? (w - padL - padR) / 2 : (i / (points.length - 1)) * (w - padL - padR))
    const y = (v: number) => padT + (1 - (v - min) / range) * (h - padT - padB)

    const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')
    const areaPath = `${path} L${x(points.length - 1).toFixed(1)},${h - padB} L${x(0).toFixed(1)},${h - padB} Z`

    const ticks = [min, min + range / 2, max]

    return (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }} role="img">
            {ticks.map((tv, i) => (
                <g key={i}>
                    <line
                        x1={padL}
                        x2={w - padR}
                        y1={y(tv)}
                        y2={y(tv)}
                        stroke="#e7e3da"
                        strokeDasharray="3,3"
                    />
                    <text x={padL - 6} y={y(tv) + 3} textAnchor="end" fontSize="9" fill="#8a857b">
                        {fmtCompact(tv)}
                    </text>
                </g>
            ))}

            {anchor !== undefined && (
                <g>
                    <line
                        x1={padL}
                        x2={w - padR}
                        y1={y(anchor)}
                        y2={y(anchor)}
                        stroke="#059669"
                        strokeWidth="1.5"
                        strokeDasharray="6,4"
                    />
                    <text x={w - padR - 4} y={y(anchor) - 5} textAnchor="end" fontSize="9" fill="#059669" fontWeight="700">
                        {anchorLabel || `anchor ${formatValue(anchor)}`}
                    </text>
                </g>
            )}

            <path d={areaPath} fill={color} opacity="0.06" />
            <path d={path} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" />

            {points.map((p, i) => (
                <circle key={i} cx={x(i)} cy={y(p.value)} r="2.6" fill={color} />
            ))}

            <text x={padL} y={h - 6} fontSize="9" fill="#8a857b">
                {fmtDayMonth(points[0].t)}
            </text>
            {points.length > 1 && (
                <text x={w - padR} y={h - 6} fontSize="9" fill="#8a857b" textAnchor="end">
                    {fmtDayMonth(points[points.length - 1].t)}
                </text>
            )}
        </svg>
    )
}

export function BarChart({
    data,
    height = 180,
    anchor,
    anchorLabel,
    formatValue = (v: number) => fmtPct(v),
}: {
    data: ChartPoint[]
    height?: number
    anchor?: number
    anchorLabel?: string
    formatValue?: (v: number) => string
}) {
    if (data.length === 0) return null

    const w = 720
    const h = height
    const padL = 40
    const padR = 10
    const padT = 14
    const padB = 30

    const values = data.map((d) => d.value)
    if (anchor !== undefined) values.push(anchor)
    const max = Math.max(...values) * 1.1

    const bw = (w - padL - padR) / data.length
    const y = (v: number) => padT + (1 - v / max) * (h - padT - padB)

    return (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }} role="img">
            <line x1={padL} x2={w - padR} y1={h - padB} y2={h - padB} stroke="#dad6cb" />

            {data.map((d, i) => {
                const cx = padL + i * bw
                const barH = Math.max(2, h - padB - y(d.value))
                const above = anchor !== undefined && d.value > anchor
                return (
                    <g key={d.label}>
                        <rect
                            x={cx + bw * 0.15}
                            y={y(d.value)}
                            width={bw * 0.7}
                            height={barH}
                            rx="3"
                            fill={above ? '#e11d48' : '#059669'}
                            opacity={above ? 0.85 : 0.8}
                        >
                            <title>{`${d.label}: ${formatValue(d.value)}`}</title>
                        </rect>
                        <text
                            x={cx + bw / 2}
                            y={y(d.value) - 4}
                            textAnchor="middle"
                            fontSize="8.5"
                            fill="#57534e"
                            fontWeight="700"
                        >
                            {d.value.toFixed(1)}
                        </text>
                        <text x={cx + bw / 2} y={h - padB + 11} textAnchor="middle" fontSize="8" fill="#8a857b">
                            {d.label.length > 9 ? `${d.label.slice(0, 8)}…` : d.label}
                        </text>
                    </g>
                )
            })}

            {anchor !== undefined && (
                <g>
                    <line
                        x1={padL}
                        x2={w - padR}
                        y1={y(anchor)}
                        y2={y(anchor)}
                        stroke="#1c1917"
                        strokeWidth="1.5"
                        strokeDasharray="6,4"
                    />
                    <text x={padL + 4} y={y(anchor) - 4} fontSize="9" fill="#1c1917" fontWeight="700">
                        {anchorLabel || `anchor ${formatValue(anchor)}`}
                    </text>
                </g>
            )}
        </svg>
    )
}

export function Sparkline({
    values,
    width = 140,
    height = 32,
    color = '#1c1917',
}: {
    values: number[]
    width?: number
    height?: number
    color?: string
}) {
    if (values.length < 2) return <div className="text-[10px] text-stone-400">no history</div>
    let min = Math.min(...values)
    let max = Math.max(...values)
    if (min === max) {
        min -= 1
        max += 1
    }
    const pts = values
        .map((v, i) => {
            const x = (i / (values.length - 1)) * (width - 4) + 2
            const y = 2 + (1 - (v - min) / (max - min)) * (height - 4)
            return `${x.toFixed(1)},${y.toFixed(1)}`
        })
        .join(' ')
    return (
        <svg width={width} height={height} className="inline-block align-middle">
            <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
        </svg>
    )
}

/** Horizontal probability/confidence bar used in audit tables. */
export function ScoreBar({ value, danger }: { value: number; danger?: boolean }) {
    const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
    return (
        <div className="flex items-center space-x-2">
            <div className="w-20 h-1.5 bg-stone-200 rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full ${danger ? 'bg-rose-500' : 'bg-emerald-500'}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
            <span className="text-[11px] font-mono text-stone-600">{pct}%</span>
        </div>
    )
}
