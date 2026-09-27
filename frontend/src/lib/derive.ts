/* =========================================================================
   Pure derivations over /nrw/summary snapshots.
   The endpoint returns the FULL history (ascending by timestamp);
   everything the dashboard shows is computed from it — no mock arrays.
   ========================================================================= */

import type { NRWSnapshot } from './api'

export interface SeriesPoint {
    t: string
    nrw: number
    loss: number
    inflow: number
}

export interface ZoneSeries {
    zoneId: string
    points: SeriesPoint[]
    latest: NRWSnapshot
    first: NRWSnapshot
}

/** Latest snapshot per zone, keyed by zone_id. */
export function latestPerZone(snapshots: NRWSnapshot[]): Map<string, NRWSnapshot> {
    const map = new Map<string, NRWSnapshot>()
    for (const s of snapshots) {
        const prev = map.get(s.zone_id)
        if (!prev || new Date(s.timestamp).getTime() >= new Date(prev.timestamp).getTime()) {
            map.set(s.zone_id, s)
        }
    }
    return map
}

/**
 * Town-wide series aggregated per timestamp: loss / inflow across all zones
 * sharing a snapshot batch (the weekly seed writes all zones together).
 */
export function townSeries(snapshots: NRWSnapshot[]): SeriesPoint[] {
    const byTime = new Map<string, NRWSnapshot[]>()
    for (const s of snapshots) {
        const key = new Date(s.timestamp).getTime().toString()
        const arr = byTime.get(key)
        if (arr) arr.push(s)
        else byTime.set(key, [s])
    }
    const points: SeriesPoint[] = []
    for (const [key, rows] of byTime) {
        const inflow = rows.reduce((a, r) => a + r.inflow_litres, 0)
        const loss = rows.reduce((a, r) => a + r.loss_litres, 0)
        points.push({
            t: key,
            nrw: inflow > 0 ? (loss / inflow) * 100 : 0,
            loss,
            inflow,
        })
    }
    points.sort((a, b) => Number(a.t) - Number(b.t))
    return points
}

/** Per-zone ordered series with its latest/first snapshots attached. */
export function zoneSeries(snapshots: NRWSnapshot[]): Map<string, ZoneSeries> {
    const grouped = new Map<string, NRWSnapshot[]>()
    for (const s of snapshots) {
        const arr = grouped.get(s.zone_id)
        if (arr) arr.push(s)
        else grouped.set(s.zone_id, [s])
    }
    const out = new Map<string, ZoneSeries>()
    for (const [zoneId, rows] of grouped) {
        rows.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        out.set(zoneId, {
            zoneId,
            points: rows.map((r) => ({
                t: new Date(r.timestamp).getTime().toString(),
                nrw: r.nrw_percentage,
                loss: r.loss_litres,
                inflow: r.inflow_litres,
            })),
            latest: rows[rows.length - 1],
            first: rows[0],
        })
    }
    return out
}

/** Town inflow in litres/minute across zones with a snapshot in the last batch. */
export function townFlowLitresPerMinute(snapshots: NRWSnapshot[]): number {
    const latest = latestPerZone(snapshots)
    let total = 0
    for (const s of latest.values()) total += s.inflow_litres
    return total / 1440 // litres/day → litres/minute
}
