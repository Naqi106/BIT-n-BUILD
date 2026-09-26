from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# Zones & Telemetry Readings
class ZoneBase(BaseModel):
    id: str
    name: str
    pipe_length_km: float = 10.0
    connection_count: int = 500
    avg_pressure_bar: float = 2.5
    tariff_rate: float = 0.005
    data_level: int = 0

class ZoneCreate(ZoneBase):
    pass

class ZoneResponse(ZoneBase):
    model_config = ConfigDict(from_attributes=True)

class ReadingCreate(BaseModel):
    zone_id: str
    inflow_litres: float
    night_flow_litres: Optional[float] = None
    pressure_bar: Optional[float] = None

class ReadingResponse(ReadingCreate):
    id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# Alerts & Payback
class LeakAlertResponse(BaseModel):
    id: int
    zone_id: str
    timestamp: datetime
    severity: str
    estimated_loss_litres: float
    confidence_score: float
    detection_methods: str
    status: str
    details: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class PaybackResponse(BaseModel):
    zone_id: str
    daily_loss_litres: float
    tariff_rate_per_litre: float
    daily_revenue_loss: float
    estimated_repair_cost: float
    payback_period_days: float
    is_simulated: bool = False
    data_source: str = "ACTIVE_ALERT"

# Actions & Recovery Workflow
class ActionCreate(BaseModel):
    zone_id: str
    alert_id: Optional[int] = None
    action_type: str = Field(..., description="e.g. Acoustic leak pin-pointing, Main valve replacement")
    urgency: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, URGENT")
    estimated_cost: float = Field(..., ge=0.0)
    estimated_payback_days: float = Field(..., ge=0.0)
    officer_notes: Optional[str] = None

class ActionUpdateStatus(BaseModel):
    status: str = Field(..., description="APPROVED, REJECTED, or RESOLVED")
    officer_notes: Optional[str] = None

class ActionResponse(BaseModel):
    id: int
    zone_id: str
    alert_id: Optional[int]
    action_type: str
    status: str
    urgency: str
    estimated_cost: float
    estimated_payback_days: float
    officer_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

class RevenueLogResponse(BaseModel):
    id: int
    zone_id: str
    alert_id: Optional[int]
    litres_recovered: float
    tariff_rate: float
    revenue_recovered: float
    recovered_at: datetime
    notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)

# Audit Responses
class BillingAuditItem(BaseModel):
    consumer_id: str
    household_size: int
    property_type: str
    billed_litres: float
    benchmark_litres: float
    suspicion_score: float
    is_anomaly: bool

class PaginatedBillingAudit(BaseModel):
    total_records: int
    total_anomalies: int
    limit: int
    offset: int
    items: List[BillingAuditItem]

class PPAAuditItem(BaseModel):
    node_id: str
    distance_from_source_km: float
    baseline_pressure_bar: float
    observed_pressure_bar: float
    pressure_drop_bar: float
    leak_probability: float
    is_simulated: bool = True  # Always explicitly declared per roadmap

class NRWSnapshotResponse(BaseModel):
    id: int
    zone_id: str
    timestamp: datetime
    nrw_percentage: float
    inflow_litres: float
    billed_litres: float
    loss_litres: float
    model_config = ConfigDict(from_attributes=True)