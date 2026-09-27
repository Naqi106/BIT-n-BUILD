import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import * as api from './api'

/* ------------------------------------------------------------------ store */

interface StoreValue {
    zones: api.Zone[]
    alerts: api.LeakAlert[]
    actions: api.ActionLog[]
    root: api.RootInfo | null
    loading: boolean
    error: string | null
    refresh: () => void
}

const StoreContext = createContext<StoreValue>({
    zones: [],
    alerts: [],
    actions: [],
    root: null,
    loading: true,
    error: null,
    refresh: () => {},
})

export function StoreProvider({ children }: { children: React.ReactNode }) {
    const [zones, setZones] = useState<api.Zone[]>([])
    const [alerts, setAlerts] = useState<api.LeakAlert[]>([])
    const [actions, setActions] = useState<api.ActionLog[]>([])
    const [root, setRoot] = useState<api.RootInfo | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [tick, setTick] = useState(0)

    useEffect(() => {
        let alive = true
        setLoading(true)
        Promise.allSettled([
            api.getRoot(),
            api.getZones(),
            api.getAlerts(),
            api.getActions(),
        ]).then(([r, z, a, act]) => {
            if (!alive) return
            if (r.status === 'fulfilled') setRoot(r.value)
            if (z.status === 'fulfilled') setZones(z.value)
            if (a.status === 'fulfilled') setAlerts(a.value)
            if (act.status === 'fulfilled') setActions(act.value)

            const failures = [r, z].filter((x) => x.status === 'rejected') as PromiseRejectedResult[]
            if (failures.length > 0) {
                setError(failures[0].reason?.message || 'Backend unreachable')
            } else {
                setError(null)
            }
            setLoading(false)
        })
        return () => {
            alive = false
        }
    }, [tick])

    const refresh = useCallback(() => setTick((t) => t + 1), [])

    return (
        <StoreContext.Provider
            value={{ zones, alerts, actions, root, loading, error, refresh }}
        >
            {children}
        </StoreContext.Provider>
    )
}

export function useStore(): StoreValue {
    return useContext(StoreContext)
}

/* --------------------------------------------------------------- useAsync */

export interface AsyncState<T> {
    data: T | null
    error: string | null
    loading: boolean
    reload: () => void
}

/**
 * Runs `fn` when any of `deps` changes. `reload()` re-runs it manually.
 * Errors surface as messages — every page renders them (no silent fallbacks).
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
    const [data, setData] = useState<T | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [tick, setTick] = useState(0)

    useEffect(() => {
        let alive = true
        setLoading(true)
        fn()
            .then((d) => {
                if (alive) {
                    setData(d)
                    setError(null)
                }
            })
            .catch((e) => {
                if (alive) setError(e?.message || String(e))
            })
            .finally(() => {
                if (alive) setLoading(false)
            })
        return () => {
            alive = false
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [...deps, tick])

    return { data, error, loading, reload: () => setTick((t) => t + 1) }
}
