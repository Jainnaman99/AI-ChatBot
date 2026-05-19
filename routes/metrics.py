"""
Metrics endpoints — real-time KPI data for the dashboard.
"""

from fastapi import APIRouter, Query
from typing import Optional
from services.metrics_service import metrics_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/kpis")
async def get_kpis():
    """
    Return real-time KPI snapshot for the dashboard:
    - Total Queries (today + % change vs yesterday)
    - Active Users (30-min window + 5-min concurrent)
    - Avg Response Time (mean + P95 + % change vs yesterday)
    - RAG Accuracy (% vector hits among non-conversational queries)
    - Chatbot Sessions (today's unique sessions + avg turns)
    - System Uptime (seconds + human-readable duration)
    """
    return metrics_service.get_kpis()


@router.get("/traffic")
async def get_traffic(
    date: Optional[str] = Query(
        default=None,
        description="Date in YYYY-MM-DD format. Defaults to today.",
    )
):
    """
    Return hourly query and user traffic for a given day.
    Suitable for rendering a dual-line chart (Queries vs Users).

    Response includes:
    - labels: ['00:00', '01:00', ..., '23:00']
    - queries: total requests per hour
    - users: unique IPs per hour
    """
    return metrics_service.get_traffic_data(date=date)


@router.get("/response-time")
async def get_response_time(
    date: Optional[str] = Query(
        default=None,
        description="Date in YYYY-MM-DD format. Defaults to today.",
    ),
    sla_threshold: float = Query(
        default=3.0,
        description="SLA threshold in seconds for the horizontal reference line.",
    ),
):
    """
    Return hourly average and P95 response time for a given day.
    Suitable for a dual-line chart with a fixed SLA reference line.

    Response includes:
    - labels: ['00:00', '01:00', ..., '23:00']
    - avg: mean response time per hour (null if no requests that hour)
    - p95: 95th percentile response time per hour (null if no requests)
    - sla_threshold: constant value for the SLA reference line
    """
    return metrics_service.get_response_time_data(date=date, sla_threshold=sla_threshold)
