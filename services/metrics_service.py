"""
In-memory metrics tracking for dashboard KPIs.
Thread-safe; records are kept in a bounded deque (last 10 000 requests).
"""

import time
import datetime
from collections import deque
from threading import Lock


class MetricsService:
    def __init__(self):
        self._start_time = time.time()
        self._lock = Lock()
        # Each entry: {timestamp, search_type, response_time, session_id}
        self._requests: deque = deque(maxlen=10_000)

    def record_request(
        self,
        search_type: str,
        response_time: float,
        session_id: str = None,
    ) -> None:
        with self._lock:
            self._requests.append(
                {
                    "timestamp": time.time(),
                    "search_type": search_type,
                    "response_time": response_time,
                    "session_id": session_id,
                }
            )

    def get_kpis(self) -> dict:
        with self._lock:
            now = time.time()
            all_reqs = list(self._requests)

        today_dt = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_start = today_dt.timestamp()
        yesterday_start = today_start - 86_400

        today_reqs = [r for r in all_reqs if r["timestamp"] >= today_start]
        yesterday_reqs = [
            r for r in all_reqs if yesterday_start <= r["timestamp"] < today_start
        ]

        # --- 1. Total Queries ---
        total_today = len(today_reqs)
        total_yesterday = len(yesterday_reqs)
        query_change_pct = (
            round((total_today - total_yesterday) / total_yesterday * 100, 1)
            if total_yesterday > 0
            else 0.0
        )

        # --- 2. Active Users (session-based) ---
        window_30m = now - 1_800
        window_5m = now - 300
        active_sessions = {
            r["session_id"]
            for r in all_reqs
            if r["timestamp"] >= window_30m and r["session_id"]
        }
        concurrent_sessions = {
            r["session_id"]
            for r in all_reqs
            if r["timestamp"] >= window_5m and r["session_id"]
        }

        # --- 3. Avg Response Time ---
        today_times = [
            r["response_time"]
            for r in today_reqs
            if r["response_time"] is not None
        ]
        yesterday_times = [
            r["response_time"]
            for r in yesterday_reqs
            if r["response_time"] is not None
        ]

        avg_rt_today = sum(today_times) / len(today_times) if today_times else 0.0
        avg_rt_yesterday = (
            sum(yesterday_times) / len(yesterday_times) if yesterday_times else 0.0
        )

        p95_rt = 0.0
        if today_times:
            sorted_times = sorted(today_times)
            p95_idx = max(0, int(0.95 * len(sorted_times)) - 1)
            p95_rt = sorted_times[p95_idx]

        rt_change_pct = (
            round((avg_rt_today - avg_rt_yesterday) / avg_rt_yesterday * 100, 1)
            if avg_rt_yesterday > 0
            else 0.0
        )

        # --- 4. RAG Accuracy (vector hits / non-conversational today) ---
        non_conv = [r for r in today_reqs if r["search_type"] != "conversational"]
        vector_hits = [r for r in non_conv if r["search_type"] == "vector"]
        rag_accuracy = (
            round(len(vector_hits) / len(non_conv) * 100, 1) if non_conv else 0.0
        )

        # --- 5. Chatbot Sessions ---
        today_sessions = {r["session_id"] for r in today_reqs if r["session_id"]}
        session_turn_counts: dict[str, int] = {}
        for r in today_reqs:
            if r["session_id"]:
                session_turn_counts[r["session_id"]] = (
                    session_turn_counts.get(r["session_id"], 0) + 1
                )
        avg_turns = (
            round(
                sum(session_turn_counts.values()) / len(session_turn_counts), 1
            )
            if session_turn_counts
            else 0.0
        )

        # --- 6. System Uptime ---
        uptime_seconds = now - self._start_time
        days, remainder = divmod(int(uptime_seconds), 86_400)
        hours, remainder = divmod(remainder, 3_600)
        minutes, seconds = divmod(remainder, 60)

        return {
            "total_queries": {
                "today": total_today,
                "yesterday": total_yesterday,
                "change_pct": query_change_pct,
            },
            "active_users": {
                "active_30min": len(active_sessions),
                "concurrent_5min": len(concurrent_sessions),
            },
            "avg_response_time": {
                "mean_seconds": round(avg_rt_today, 2),
                "p95_seconds": round(p95_rt, 2),
                "change_pct": rt_change_pct,
            },
            "rag_accuracy": {
                "pct": rag_accuracy,
                "vector_hits": len(vector_hits),
                "total_non_conversational": len(non_conv),
            },
            "chatbot_sessions": {
                "today": len(today_sessions),
                "avg_turns": avg_turns,
            },
            "system_uptime": {
                "uptime_seconds": round(uptime_seconds),
                "uptime_human": f"{days}d {hours}h {minutes}m {seconds}s",
                "started_at": datetime.datetime.fromtimestamp(
                    self._start_time
                ).isoformat(),
            },
        }


# Singleton used by all routes
metrics_service = MetricsService()
