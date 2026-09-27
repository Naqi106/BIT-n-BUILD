/* =========================================================================
   AltoMare frontend — typed client for the live FastAPI backend.

   Base URL is overridable with VITE_API_BASE at build time.
   The backend runs CORS allow_origins=["*"], so direct calls work.
   ========================================================================= */

export const API_BASE: string =
    (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8000'

export class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
        super(message)
        this.status = status
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response
    try {
        res = await fetch(`${API_BASE}${path}`, init)
    } catch {
        throw new ApiError(0, 'Cannot reach the backend API. Is the FastAPI server running?')
    }
    if (!res.ok) {
        let detail = `HTTP ${res.status} ${res.statusText}`
        try {
            const body = await res.json()
            if (body && body.detail !== undefined) {
                detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
            }
        } catch {
            /* keep the HTTP status message */
        }
        throw new ApiError(res.status, detail)
    }
    return (await res.json()) as T
}

function post<T>(path: string, data?: unknown): Promise<T> {
    const init: RequestInit = { method: 'POST' }
    if (data !== undefined) {
        init.headers = { 'Content-Type': 'application/json' }
        init.body = JSON.stringify(data)
    }
    return request<T>(path, init)
}

/* ------------------------------------------------------------------ types */

export interface RootInfo {
    platform: string
    status: string
    version: string
    docs: string
}

export interface Zone {
    id: string
    name: string
    pipe_length_km: number
    connection_count: number
    avg_pressure_bar: number
    tariff_rate: number
    data_level?: number
}

export interface NRWSnapshot {
    id: number
    zone_id: string
    timestamp: string
    nrw_percentage: number
    inflow_litres: number
    billed_litres: number
    loss_litres: number
}

export interface LeakAlert {
    id: number
    zone_id: string
    timestamp: string
    severity: string
    estimated_loss_litres: number
    confidence_score: number
    detection_methods: string
    status: string
    details?: string | null
}

export interface ActionLog {
    id: number
    zone_id: string
    alert_id?: number | null
    action_type: string
    status: string
    urgency: string
    estimated_cost: number
    estimated_payback_days: number
    officer_notes?: string | null
    created_at: string
    updated_at: string
    resolved_at?: string | null
}

export interface RevenueLog {
    id: number
    zone_id: string
    alert_id?: number | null
    litres_recovered: number
    tariff_rate: number
    revenue_recovered: number
    recovered_at: string
    notes?: string | null
}

export interface Payback {
    zone_id: string
    daily_loss_litres: number
    tariff_rate_per_litre: number
    daily_revenue_loss: number
    estimated_repair_cost: number
    payback_period_days: number
    is_simulated: boolean
    data_source: string
}

export interface BillingItem {
    consumer_id: string
    household_size: number
    property_type: string
    billed_litres: number
    benchmark_litres: number
    suspicion_score: number
    is_anomaly: boolean
}

export interface PaginatedBilling {
    total_records: number
    total_anomalies: number
    limit: number
    offset: number
    items: BillingItem[]
}

export interface PPAItem {
    node_id: string
    distance_from_source_km: number
    baseline_pressure_bar: number
    observed_pressure_bar: number
    pressure_drop_bar: number
    leak_probability: number
    is_simulated: boolean
}

export interface TownProfile {
    town_name: string
    total_nrw_percent: number
    estimated_annual_loss_inr: number
    total_zones: number
    population_covered: number
    data_source: string
    anchor_source_citation: string
}

export interface NRWForecast {
    zone_id?: string | null
    is_sufficient: boolean
    observations: number
    required_observations?: number | null
    message?: string | null
    method?: string | null
    window_days?: number | null
    horizon_days?: number | null
    tariff_rate?: number | null
    current_loss_litres_per_day?: number | null
    projected_loss_litres_per_day?: number | null
    loss_slope_litres_per_day_per_day?: number | null
    loss_change_pct?: number | null
    loss_r2?: number | null
    trend_confidence?: string | null
    direction?: string | null
    projected_loss_litres?: number | null
    projected_loss_rupees?: number | null
    current_nrw_pct?: number | null
    projected_nrw_pct?: number | null
    nrw_slope_pp_per_day?: number | null
    nrw_r2?: number | null
    interpretation?: string | null
}

export interface InvestigationEntry {
    id: number
    zone_id: string
    summary: string
    action_taken?: string | null
    outcome?: string | null
    timestamp?: string | null
}

export interface InvestigationMemory {
    zone_id: string
    previously_flagged: boolean
    note?: string | null
    investigation_count: number
    last_flagged_at?: string | null
    days_since_last?: number | null
    entries: InvestigationEntry[]
}

export interface AgentMemoryItem {
    id: number
    zone_id: string
    summary: string
    action_taken?: string | null
    outcome?: string | null
    timestamp?: string | null
}

export interface EvidenceItem {
    source: string
    metric: string
    value: unknown
    unit?: string | null
    explanation?: string | null
}

export interface Recommendation {
    action: string
    priority: string
    reason: string
}

export interface AgentInvestigation {
    zone_id: string
    risk_level: string
    likely_cause: string
    confidence: number
    summary: string
    evidence: EvidenceItem[]
    recommendations: Recommendation[]
    missing_data: string[]
    ai_available: boolean
}

export interface NDWIResponse {
    zone_id: string
    coordinates?: { lat: number; lng: number } | null
    status: string
    is_simulated: boolean
    data_source: string
    scene?: {
        id?: string | null
        datetime?: string | null
        cloud_cover?: number | null
        platform?: string | null
    } | null
    ndwi_score?: number | null
    ndwi_status: string
    anomaly_threshold?: number | null
    surface_moisture_anomaly?: boolean | null
    zone_flagged: boolean
    flag_sources: string[]
    billing_flagged_records: number
    billing_detection_method?: string | null
    nrw_trend?: string | null
    interpretation: string
    message?: string | null
}

export interface CSVUploadResult {
    readings_inserted: number
    billing_records_inserted: number
    warnings: string[]
}

export interface ActionCreatePayload {
    zone_id: string
    alert_id?: number | null
    action_type: string
    urgency?: string
    estimated_cost: number
    estimated_payback_days: number
    officer_notes?: string | null
}

export interface AgentActionPayload {
    zone_id: string
    alert_id?: number | null
    action: string
    priority: string
    reason: string
    daily_loss_litres: number
    tariff_rate?: number | null
    pipe_age_years?: number | null
}

export interface AgentActionResponse {
    action_id: number
    zone_id: string
    action_type: string
    urgency: string
    estimated_cost: number
    estimated_payback_days: number
    officer_notes?: string | null
    status: string
    message: string
}

/* ------------------------------------------------------------------- GETs */

export const getRoot = () => request<RootInfo>('/')
export const getZones = () => request<Zone[]>('/zones')
export const getNRWSummary = () => request<NRWSnapshot[]>('/nrw/summary')
export const getAlerts = (zoneId?: string) =>
    request<LeakAlert[]>(`/alerts${zoneId ? `?zone_id=${encodeURIComponent(zoneId)}` : ''}`)
export const getActions = (zoneId?: string) =>
    request<ActionLog[]>(
        `/actions/${zoneId ? `?zone_id=${encodeURIComponent(zoneId)}` : ''}`,
    )
export const getRevenue = () => request<RevenueLog[]>('/revenue/summary')
export const getPayback = (zoneId: string) => request<Payback>(`/revenue/payback/${zoneId}`)
export const getBilling = (zoneId: string, limit = 20, offset = 0) =>
    request<PaginatedBilling>(`/audit/billing/${zoneId}?limit=${limit}&offset=${offset}`)
export const getPPA = (zoneId: string) => request<PPAItem[]>(`/audit/ppa/${zoneId}`)
export const getTownProfile = () => request<TownProfile>('/data/town-profile')
export const getForecast = (zoneId?: string) =>
    request<NRWForecast>(zoneId ? `/data/nrw-forecast/${zoneId}` : '/data/nrw-forecast')
export const getNDWI = (zoneId: string) =>
    request<NDWIResponse>(`/data/satellite/ndwi/${zoneId}`)
export const getInvestigations = (zoneId: string) =>
    request<InvestigationMemory>(`/data/investigations/${zoneId}`)
export const getMemory = (zoneId: string) =>
    request<AgentMemoryItem[]>(`/agent/memory/${zoneId}`)
export const getOpenAPI = () => request<Record<string, unknown>>('/openapi.json')

/* ------------------------------------------------------------------ POSTs */

export const agentInvestigate = (zone_id: string, question: string) =>
    post<AgentInvestigation>('/agent/investigate', { zone_id, question })

export const agentCreateAction = (payload: AgentActionPayload) =>
    post<AgentActionResponse>('/agent/create-action', payload)

export const createAction = (payload: ActionCreatePayload) =>
    post<ActionLog>('/actions/create', payload)

export const approveAction = (id: number, officerNotes?: string) =>
    post<ActionLog>(
        `/actions/approve/${id}` +
            (officerNotes ? `?officer_notes=${encodeURIComponent(officerNotes)}` : ''),
    )

export const rejectAction = (id: number, reason: string) =>
    post<ActionLog>(`/actions/reject/${id}?reason=${encodeURIComponent(reason)}`)

export const resolveAction = (id: number) => post<ActionLog>(`/actions/resolve/${id}`)

export async function uploadCSV(file: File): Promise<CSVUploadResult> {
    const fd = new FormData()
    fd.append('file', file)
    return request<CSVUploadResult>('/data/upload-csv', { method: 'POST', body: fd })
}
