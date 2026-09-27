import React from 'react'
import { AlertCircle, Inbox, Loader2, X } from 'lucide-react'
import { statusClass } from '../lib/format'

/* ------------------------------------------------------------------ cards */

export function Card({
    children,
    className = '',
}: {
    children: React.ReactNode
    className?: string
}) {
    return (
        <div
            className={`bg-white/80 backdrop-blur-md p-5 rounded-xl border border-[#dad6cb] shadow-sm ${className}`}
        >
            {children}
        </div>
    )
}

export function SectionTitle({
    icon: Icon,
    children,
    right,
}: {
    icon?: React.ComponentType<{ className?: string }>
    children: React.ReactNode
    right?: React.ReactNode
}) {
    return (
        <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-stone-800 flex items-center space-x-2">
                {Icon && <Icon className="w-4 h-4 text-stone-600" />}
                <span>{children}</span>
            </h2>
            {right}
        </div>
    )
}

/* ------------------------------------------------------------------ pills */

export function Pill({
    children,
    className = 'bg-stone-200 text-stone-700',
    title,
}: {
    children: React.ReactNode
    className?: string
    title?: string
}) {
    return (
        <span
            title={title}
            className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold whitespace-nowrap ${className}`}
        >
            {children}
        </span>
    )
}

export function StatusPill({ status, title }: { status: string; title?: string }) {
    return (
        <Pill className={statusClass(status)} title={title}>
            {status}
        </Pill>
    )
}

/* --------------------------------------------------------- loading / error */

export function Spinner({ label }: { label?: string }) {
    return (
        <div className="flex items-center justify-center space-x-2 py-14 text-stone-500 text-xs font-medium">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>{label || 'Loading live data…'}</span>
        </div>
    )
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
    return (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-5 flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
                <div className="text-xs font-bold text-rose-800">Failed to load live data</div>
                <div className="text-xs text-rose-700">{error}</div>
            </div>
            {onRetry && (
                <button
                    onClick={onRetry}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium rounded-lg transition-colors"
                >
                    Retry
                </button>
            )}
        </div>
    )
}

export function EmptyState({
    icon: Icon = Inbox,
    title,
    hint,
}: {
    icon?: React.ComponentType<{ className?: string }>
    title: string
    hint?: string
}) {
    return (
        <div className="py-12 text-center space-y-2">
            <Icon className="w-7 h-7 text-stone-300 mx-auto" />
            <div className="text-xs font-semibold text-stone-600">{title}</div>
            {hint && <div className="text-[11px] text-stone-400 max-w-md mx-auto">{hint}</div>}
        </div>
    )
}

export function InlineNotice({
    tone = 'amber',
    title,
    children,
}: {
    tone?: 'amber' | 'emerald' | 'rose' | 'blue'
    title?: string
    children: React.ReactNode
}) {
    const tones = {
        amber: 'bg-amber-50 border-amber-200 text-amber-800',
        emerald: 'bg-emerald-50 border-emerald-200 text-emerald-800',
        rose: 'bg-rose-50 border-rose-200 text-rose-800',
        blue: 'bg-blue-50 border-blue-200 text-blue-800',
    }
    return (
        <div className={`rounded-xl border p-4 text-xs space-y-1 ${tones[tone]}`}>
            {title && <div className="font-bold">{title}</div>}
            <div className="leading-relaxed">{children}</div>
        </div>
    )
}

/* ------------------------------------------------------------------ modal */

export function Modal({
    title,
    onClose,
    children,
    footer,
}: {
    title: string
    onClose: () => void
    children: React.ReactNode
    footer?: React.ReactNode
}) {
    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#fbfbf9] rounded-xl border border-[#dad6cb] shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#dad6cb]">
                    <h3 className="text-sm font-bold text-stone-900">{title}</h3>
                    <button
                        onClick={onClose}
                        className="p-1 rounded-lg text-stone-500 hover:text-stone-900 hover:bg-[#dedad0] transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="p-5 space-y-4">{children}</div>
                {footer && (
                    <div className="px-5 py-3.5 border-t border-[#dad6cb] flex justify-end space-x-2">
                        {footer}
                    </div>
                )}
            </div>
        </div>
    )
}

/* ----------------------------------------------------------------- fields */

export function Field({
    label,
    children,
    hint,
}: {
    label: string
    children: React.ReactNode
    hint?: string
}) {
    return (
        <label className="block space-y-1.5">
            <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                {label}
            </span>
            {children}
            {hint && <span className="block text-[10px] text-stone-400">{hint}</span>}
        </label>
    )
}

export const inputCls =
    'w-full px-3 py-2 bg-white border border-[#dad6cb] rounded-lg text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-stone-400'

export const btnPrimary =
    'px-4 py-2 bg-[#1c1917] hover:bg-stone-800 text-white text-xs font-medium rounded-lg transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed'

export const btnSecondary =
    'px-4 py-2 bg-white hover:bg-[#f3f0e8] border border-[#dad6cb] text-stone-700 text-xs font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed'

/* ------------------------------------------------------------------ toast */

export function Toast({
    message,
    tone = 'emerald',
    onClose,
}: {
    message: string
    tone?: 'emerald' | 'amber' | 'rose'
    onClose: () => void
}) {
    const tones = {
        emerald: 'border-emerald-300 bg-emerald-50 text-emerald-900',
        amber: 'border-amber-300 bg-amber-50 text-amber-900',
        rose: 'border-rose-300 bg-rose-50 text-rose-900',
    }
    return (
        <div
            className={`fixed bottom-5 right-5 z-50 max-w-md rounded-xl border shadow-lg px-4 py-3 text-xs font-medium flex items-start space-x-2 ${tones[tone]}`}
        >
            <span className="flex-1 leading-relaxed">{message}</span>
            <button onClick={onClose} className="font-bold opacity-60 hover:opacity-100">
                ✕
            </button>
        </div>
    )
}

/* ------------------------------------------------------------ stat helper */

export function StatGrid({ items }: { items: { label: string; value: React.ReactNode; sub?: React.ReactNode }[] }) {
    return (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {items.map((it) => (
                <div
                    key={it.label}
                    className="p-3.5 rounded-lg border border-[#dad6cb] bg-[#fbfaf8] space-y-1"
                >
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-stone-500">
                        {it.label}
                    </div>
                    <div className="text-lg font-bold text-stone-900">{it.value}</div>
                    {it.sub && <div className="text-[11px] text-stone-500">{it.sub}</div>}
                </div>
            ))}
        </div>
    )
}
