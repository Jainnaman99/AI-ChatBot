"""
Metrics endpoints — real-time KPI data for the dashboard.
"""

from fastapi import APIRouter
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
