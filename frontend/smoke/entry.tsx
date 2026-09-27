/* =========================================================================
   Render smoke test — mounts the REAL App (all routes) in jsdom against the
   LIVE backend on 127.0.0.1:8000, and asserts each screen renders its real
   data markers. Dev-only tool; excluded from the app build (lives outside
   src/, tsconfig includes only src/).

   Run:
     npx vite build --ssr smoke/entry.tsx --outDir smoke-dist
     node smoke-dist/entry.js
   ========================================================================= */

type Marker = { route: string; wait: string; also?: string[]; timeoutMs?: number }

const ROUTES: Marker[] = [
    { route: '/', wait: 'plug the leaks', also: ['Lucknow Grid Telemetry'] },
    { route: '/app/dashboard', wait: 'Town NRW Loss Rate', also: ['Hazratganj', '%'] },
    { route: '/app/alerts', wait: 'ALT-1', also: ['Aliganj', 'CRITICAL'] },
    { route: '/app/zones', wait: 'District Metered Areas' },
    { route: '/app/copilot', wait: 'Run Investigation' },
    { route: '/app/billing', wait: 'Consumer Scoring' },
    { route: '/app/leak', wait: 'Simulated sensor data' },
    { route: '/app/contamination', wait: 'NOT CONFIGURED' },
    { route: '/app/analytics', wait: 'Town NRW Trend' },
    { route: '/app/reports', wait: 'Full Operations Brief' },
    { route: '/app/revenue', wait: 'Repair Payback Calculator' },
    { route: '/app/upload', wait: 'Browse Files' },
    { route: '/app/settings', wait: 'Endpoint inventory' },
]

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function waitFor(fn: () => boolean, timeoutMs: number): Promise<boolean> {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
        try {
            if (fn()) return true
        } catch {
            /* keep polling */
        }
        await sleep(120)
    }
    return fn()
}

async function main() {
    const { JSDOM } = await import('jsdom')

    const dom = new JSDOM(
        '<!doctype html><html><body><div id="root"></div></body></html>',
        { url: 'http://localhost:5173/', pretendToBeVisual: true },
    )
    const w = dom.window as unknown as Record<string, unknown>

    const g = globalThis as Record<string, unknown>
    g.window = w
    g.document = w.document
    g.HTMLIFrameElement = w.HTMLIFrameElement
    g.HTMLElement = w.HTMLElement
    g.Element = w.Element
    g.Node = w.Node
    g.Event = w.Event
    g.MouseEvent = w.MouseEvent
    g.KeyboardEvent = w.KeyboardEvent
    g.getComputedStyle = (w as { getComputedStyle: unknown }).getComputedStyle
    g.requestAnimationFrame = (w as { requestAnimationFrame: unknown }).requestAnimationFrame
    g.cancelAnimationFrame = (w as { cancelAnimationFrame: unknown }).cancelAnimationFrame
    g.localStorage = (w as { localStorage: unknown }).localStorage
    try {
        Object.defineProperty(globalThis, 'navigator', {
            value: (w as { navigator: unknown }).navigator,
            configurable: true,
        })
    } catch {
        /* Node's own navigator is fine */
    }
    // jsdom does not implement these; the app only uses them in click handlers
    ;(w.Element.prototype as unknown as { scrollIntoView: () => void }).scrollIntoView = () => {}
    ;(w.Element.prototype as unknown as { scrollTo: () => void }).scrollTo = () => {}

    const React = (await import('react')).default
    const { createRoot } = await import('react-dom/client')
    const { MemoryRouter } = await import('react-router-dom')
    const { default: App } = await import('../src/App')

    const doc = w.document as Document
    const results: { route: string; ok: boolean; detail: string }[] = []

    for (const { route, wait, also = [], timeoutMs = 8000 } of ROUTES) {
        const container = doc.createElement('div')
        doc.body.appendChild(container)
        const root = createRoot(container as unknown as Parameters<typeof createRoot>[0])
        let renderError: string | null = null
        try {
            root.render(
                React.createElement(
                    MemoryRouter,
                    { initialEntries: [route] },
                    React.createElement(App),
                ),
            )
            const found = await waitFor(
                () => (container.textContent || '').includes(wait),
                timeoutMs,
            )
            const alsoOk = found
                ? await waitFor(
                      () => also.every((m) => (container.textContent || '').includes(m)),
                      5000,
                  )
                : false
            const text = container.textContent || ''
            results.push({
                route,
                ok: found && alsoOk,
                detail: found
                    ? alsoOk
                        ? `markers [${[wait, ...also].join(' | ')}] present (${text.length} chars)`
                        : `extra markers missing: [${also.join(', ')}] — head: ${text.slice(0, 240)}`
                    : `marker "${wait}" NOT found — DOM head: ${text.slice(0, 220)}`,
            })
        } catch (e) {
            renderError = (e as Error).message
            results.push({ route, ok: false, detail: `render threw: ${renderError}` })
        }
        try {
            root.unmount()
        } catch {
            /* ignore */
        }
        container.remove()
        await sleep(80)
    }

    // ------------------------------------------------ interaction test:
    // Alerts page — open the Dispatch modal, then cancel it.
    {
        const container = doc.createElement('div')
        doc.body.appendChild(container)
        const root = createRoot(container as unknown as Parameters<typeof createRoot>[0])
        try {
            root.render(
                React.createElement(
                    MemoryRouter,
                    { initialEntries: ['/app/alerts'] },
                    React.createElement(App),
                ),
            )
            const ready = await waitFor(() => (container.textContent || '').includes('ALT-1'), 8000)
            let ok = false
            let detail = 'alerts never loaded'
            if (ready) {
                const btns = Array.from(container.querySelectorAll('button'))
                const dispatch = btns.find((b) => (b.textContent || '').includes('Dispatch Team'))
                if (!dispatch) {
                    detail = 'Dispatch Team button not found'
                } else {
                    ;(dispatch as HTMLElement).click()
                    const modalShown = await waitFor(
                        () => (container.textContent || '').includes('Dispatch team —'),
                        3000,
                    )
                    if (!modalShown) {
                        detail = 'modal did not open after click'
                    } else {
                        const hasInput = !!container.querySelector('input[type="number"]')
                        const cancel = Array.from(container.querySelectorAll('button')).find(
                            (b) => (b.textContent || '').trim() === 'Cancel',
                        )
                        ;(cancel as HTMLElement | undefined)?.click()
                        const modalClosed = await waitFor(
                            () => !(container.textContent || '').includes('Dispatch team —'),
                            3000,
                        )
                        ok = hasInput && modalClosed
                        detail = `modal opened=${modalShown} costInput=${hasInput} closed=${modalClosed}`
                    }
                }
            }
            results.push({ route: 'INTERACTION /app/alerts dispatch modal', ok, detail })
        } catch (e) {
            results.push({
                route: 'INTERACTION /app/alerts dispatch modal',
                ok: false,
                detail: `threw: ${(e as Error).message}`,
            })
        }
        try {
            root.unmount()
        } catch {
            /* ignore */
        }
        container.remove()
    }

    let failed = 0
    console.log('='.repeat(78))
    for (const r of results) {
        if (!r.ok) failed++
        console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.route.padEnd(46)} ${r.detail}`)
    }
    console.log('='.repeat(78))
    console.log(`RESULT: ${results.length - failed}/${results.length} passed`)
    process.exit(failed > 0 ? 1 : 0)
}

main().catch((e) => {
    console.error('SMOKE CRASHED:', e)
    process.exit(2)
})
