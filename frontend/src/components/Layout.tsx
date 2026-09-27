import React from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
    LayoutDashboard,
    AlertTriangle,
    MapPin,
    Bot,
    Receipt,
    Crosshair,
    Activity,
    LineChart,
    FileText,
    DollarSign,
    Upload,
    Settings,
    ArrowLeft,
    Radio,
    AlertCircle,
} from 'lucide-react'
import { useStore } from '../lib/store'

/* =========================================================================
   Application shell — sidebar + topbar. Badges and status pills show LIVE
   counts from the store (active alerts, API version), never hard-coded.
   ========================================================================= */

interface NavItem {
    path: string
    label: string
    icon: React.ComponentType<{ className?: string }>
    badge?: string
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
    {
        title: 'Core Operations',
        items: [
            { path: '/app/dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { path: '/app/alerts', label: 'Live Alerts', icon: AlertTriangle, badge: 'count:alerts' },
            { path: '/app/zones', label: 'Zones & DMAs', icon: MapPin },
            { path: '/app/copilot', label: 'AI Copilot', icon: Bot, badge: 'AGENT' },
        ],
    },
    {
        title: 'Loss Detection & Audit',
        items: [
            { path: '/app/billing', label: 'Billing Audit', icon: Receipt, badge: 'ML' },
            { path: '/app/leak', label: 'Leak Location', icon: Crosshair, badge: 'SIM' },
            { path: '/app/contamination', label: 'Contamination', icon: Activity },
        ],
    },
    {
        title: 'Analytics & Reports',
        items: [
            { path: '/app/analytics', label: 'Analytics', icon: LineChart },
            { path: '/app/reports', label: 'Reports', icon: FileText },
        ],
    },
    {
        title: 'Financial & Pipeline',
        items: [
            { path: '/app/revenue', label: 'Revenue & Actions', icon: DollarSign, badge: 'count:pending' },
            { path: '/app/upload', label: 'Data Upload', icon: Upload },
        ],
    },
    {
        title: 'System',
        items: [{ path: '/app/settings', label: 'Settings & Status', icon: Settings }],
    },
]

const TITLES: Record<string, { title: string; crumb: string }> = {
    '/app/dashboard': { title: 'Dashboard', crumb: 'Municipal Water Management Platform' },
    '/app/alerts': { title: 'Live Alerts', crumb: 'Non-Revenue Water Detection' },
    '/app/zones': { title: 'Zones & DMAs', crumb: 'District Metered Areas' },
    '/app/copilot': { title: 'AI Copilot', crumb: 'Agentic Investigation' },
    '/app/billing': { title: 'Billing Audit', crumb: 'Commercial Loss Detection' },
    '/app/leak': { title: 'Leak Location', crumb: 'Pressure Profile Analysis' },
    '/app/contamination': { title: 'Contamination', crumb: 'Water Quality Correlation' },
    '/app/analytics': { title: 'Analytics', crumb: 'Trend Forecasting' },
    '/app/reports': { title: 'Reports', crumb: 'Exports & Briefings' },
    '/app/revenue': { title: 'Revenue & Actions', crumb: 'Approval Workflow' },
    '/app/upload': { title: 'Data Upload', crumb: 'CSV Ingestion' },
    '/app/settings': { title: 'Settings & Status', crumb: 'System Health' },
}

export function Layout() {
    const navigate = useNavigate()
    const location = useLocation()
    const { alerts, actions, root, error, refresh } = useStore()

    const activeAlerts = alerts.filter((a) => a.status === 'ACTIVE')
    const pendingActions = actions.filter((a) => a.status === 'PENDING')
    const online = root !== null && !error

    const meta = TITLES[location.pathname] || TITLES['/app/dashboard']

    const badgeFor = (item: NavItem): string | null => {
        if (item.badge === 'count:alerts') return activeAlerts.length > 0 ? String(activeAlerts.length) : null
        if (item.badge === 'count:pending') return pendingActions.length > 0 ? String(pendingActions.length) : null
        return item.badge || null
    }

    return (
        <div className="flex h-screen w-screen overflow-hidden bg-[#f0eee9] text-[#1c1917] font-sans antialiased">
            {/* ---------------------------------------------------- sidebar */}
            <aside className="w-64 flex-shrink-0 bg-[#e8e6e0] border-r border-[#dad6cb] flex flex-col justify-between select-none">
                <div>
                    <div className="p-5 border-b border-[#dad6cb] flex items-center justify-between">
                        <span className="text-xl font-serif font-bold tracking-tight text-[#1c1917]">
                            altomare
                            <span className="text-xs align-super font-sans font-normal text-stone-500">™</span>
                        </span>
                        <button
                            onClick={() => navigate('/')}
                            className="p-1.5 rounded-lg text-stone-600 hover:text-stone-900 hover:bg-[#dedad0] transition-colors flex items-center space-x-1 text-xs"
                            title="Back to Landing Page"
                        >
                            <ArrowLeft className="w-4 h-4" />
                        </button>
                    </div>

                    <nav className="p-3 space-y-6 overflow-y-auto max-h-[calc(100vh-140px)]">
                        {NAV_SECTIONS.map((section) => (
                            <div key={section.title} className="space-y-1">
                                <h3 className="px-3 text-[10px] font-semibold tracking-wider text-stone-500 uppercase">
                                    {section.title}
                                </h3>
                                {section.items.map((item) => {
                                    const Icon = item.icon
                                    const badge = badgeFor(item)
                                    return (
                                        <NavLink
                                            key={item.path}
                                            to={item.path}
                                            className={({ isActive }) =>
                                                `w-full flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg transition-all ${
                                                    isActive
                                                        ? 'bg-[#1c1917] text-white shadow-sm'
                                                        : 'text-stone-700 hover:bg-[#dedad0] hover:text-stone-900'
                                                }`
                                            }
                                        >
                                            {({ isActive }) => (
                                                <>
                                                    <div className="flex items-center space-x-2.5">
                                                        <Icon
                                                            className={`w-4 h-4 ${isActive ? 'text-stone-200' : 'text-stone-500'}`}
                                                        />
                                                        <span>{item.label}</span>
                                                    </div>
                                                    {badge && (
                                                        <span
                                                            className={`px-1.5 py-0.5 text-[9px] font-semibold rounded-full ${
                                                                isActive
                                                                    ? 'bg-stone-700 text-stone-200'
                                                                    : 'bg-[#dedad0] text-stone-600'
                                                            }`}
                                                        >
                                                            {badge}
                                                        </span>
                                                    )}
                                                </>
                                            )}
                                        </NavLink>
                                    )
                                })}
                            </div>
                        ))}
                    </nav>
                </div>

                {/* sidebar footer — live engine status */}
                <div className="p-4 border-t border-[#dad6cb] bg-[#e4e1db]">
                    <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                            <span
                                className={`w-2 h-2 rounded-full ${online ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`}
                            ></span>
                            <span className="text-stone-600 font-medium">FastAPI Engine</span>
                        </div>
                        <span className="text-[10px] text-stone-500 uppercase font-mono">
                            {root ? `v${root.version} Online` : error ? 'Offline' : 'Checking…'}
                        </span>
                    </div>
                </div>
            </aside>

            {/* -------------------------------------------------- main area */}
            <main className="flex-1 flex flex-col overflow-hidden bg-[#f0eee9]">
                <header className="h-14 border-b border-[#dad6cb] bg-[#f0eee9]/80 backdrop-blur-md px-6 flex items-center justify-between flex-shrink-0">
                    <div className="flex items-center space-x-3">
                        <h1 className="text-sm font-semibold text-stone-800">{meta.title}</h1>
                        <span className="text-stone-400">/</span>
                        <span className="text-xs text-stone-500">{meta.crumb}</span>
                    </div>

                    <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-2 bg-white/70 px-3 py-1 rounded-full border border-[#dad6cb] text-xs">
                            <Radio
                                className={`w-3.5 h-3.5 ${online ? 'text-emerald-600 animate-pulse' : 'text-rose-500'}`}
                            />
                            <span className="text-stone-600">{online ? 'DMA Telemetry Live' : 'API Offline'}</span>
                        </div>
                        <button
                            onClick={() => navigate('/app/copilot')}
                            className="flex items-center space-x-1.5 bg-[#1c1917] hover:bg-stone-800 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-all shadow-sm"
                        >
                            <Bot className="w-3.5 h-3.5" />
                            <span>Ask Copilot</span>
                        </button>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {error && (
                        <div className="bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 flex items-center space-x-3 text-xs">
                            <AlertCircle className="w-4 h-4 text-rose-600" />
                            <span className="text-rose-800 flex-1">{error}</span>
                            <button
                                onClick={refresh}
                                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium rounded-lg"
                            >
                                Retry
                            </button>
                        </div>
                    )}
                    <Outlet />
                </div>
            </main>
        </div>
    )
}

export default Layout
