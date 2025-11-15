"""Data models for pipeline layers."""
from datetime import date
from pydantic import BaseModel


class TicketAnalysis(BaseModel):
    """Extracted data from individual ticket."""
    ticket_id: str
    category: str
    product_area: str
    sentiment: str
    priority: str
    themes: list[str]
    summary: str


class DailySummary(BaseModel):
    """Aggregated summary for one day."""
    date: date
    ticket_count: int
    key_themes: list[str]
    trend_analysis: str
    critical_issues: list[str]


class HealthSnapshot(BaseModel):
    """System health metrics."""
    overall_health: str
    ticket_volume_trend: str
    complaint_rate_trend: str
    top_3_drivers: list[str]


class KeyInsight(BaseModel):
    """Notable pattern or finding."""
    insight: str
    severity: str
    evidence: str
    customer_impact: str


class RecommendedAction(BaseModel):
    """Actionable recommendation."""
    action: str
    priority: str
    estimated_impact: str
    suggested_owner: str
    success_metrics: str


class CustomerVoice(BaseModel):
    """Customer quotes and feedback."""
    quotes: list[str]


class WeekOverWeekComparison(BaseModel):
    """Trends across time periods."""
    improved: list[str]
    deteriorated: list[str]
    stayed_same: list[str]


class Report(BaseModel):
    """Executive summary report."""
    period: str
    executive_summary: str
    health_snapshot: HealthSnapshot
    key_insights: list[KeyInsight]
    recommended_actions: list[RecommendedAction]
    customer_voice: CustomerVoice
    week_over_week_comparison: WeekOverWeekComparison

