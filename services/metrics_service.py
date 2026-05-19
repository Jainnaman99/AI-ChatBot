"""
Persistent metrics tracking for dashboard KPIs.
Uses SQLite so data survives server restarts.
Thread-safe via a single Lock around all DB operations.
"""

import time
import sqlite3
import datetime
from threading import Lock

DB_PATH = "metrics.db"


class MetricsService:
    def __init__(self):
        self._start_time = time.time()
        self._lock = Lock()
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._setup_db()

    def _setup_db(self):
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp     REAL    NOT NULL,
                    search_type   TEXT    NOT NULL,
                    response_time REAL,
                    session_id    TEXT,
                    client_ip     TEXT,
                    language      TEXT,
                    query_text    TEXT,
                    source_domain TEXT
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON requests(timestamp)"
            )
            # Migrate existing DB — add new columns if they don't exist yet
            for col, col_type in [
                ("language",      "TEXT"),
                ("query_text",    "TEXT"),
                ("source_domain", "TEXT"),
            ]:
                try:
                    self._conn.execute(f"ALTER TABLE requests ADD COLUMN {col} {col_type}")
                except Exception:
                    pass  # column already exists
            self._conn.commit()

    def record_request(
        self,
        search_type: str,
        response_time: float,
        session_id: str = None,
        client_ip: str = None,
        language: str = None,
        query_text: str = None,
        source_domain: str = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO requests "
                "(timestamp, search_type, response_time, session_id, client_ip, language, query_text, source_domain) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), search_type, response_time, session_id, client_ip,
                 language, query_text, source_domain),
            )
            self._conn.commit()

    def get_kpis(self) -> dict:
        now = time.time()
        today_dt = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_start = today_dt.timestamp()
        yesterday_start = today_start - 86_400
        window_30m = now - 1_800
        window_5m = now - 300

        # Single query covers today + yesterday (all we need for KPIs)
        with self._lock:
            cursor = self._conn.execute(
                "SELECT timestamp, search_type, response_time, session_id, client_ip "
                "FROM requests WHERE timestamp >= ?",
                (yesterday_start,),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        today_reqs = [r for r in rows if r["timestamp"] >= today_start]
        yesterday_reqs = [r for r in rows if yesterday_start <= r["timestamp"] < today_start]

        # --- 1. Total Queries ---
        total_today = len(today_reqs)
        total_yesterday = len(yesterday_reqs)
        query_change_pct = (
            round((total_today - total_yesterday) / total_yesterday * 100, 1)
            if total_yesterday > 0
            else 0.0
        )

        # --- 2. Active Users (IP-based) ---
        active_ips = {
            r["client_ip"]
            for r in rows
            if r["timestamp"] >= window_30m and r["client_ip"]
        }
        concurrent_ips = {
            r["client_ip"]
            for r in rows
            if r["timestamp"] >= window_5m and r["client_ip"]
        }

        # --- 3. Avg Response Time ---
        today_times = [r["response_time"] for r in today_reqs if r["response_time"] is not None]
        yesterday_times = [r["response_time"] for r in yesterday_reqs if r["response_time"] is not None]

        avg_rt_today = sum(today_times) / len(today_times) if today_times else 0.0
        avg_rt_yesterday = sum(yesterday_times) / len(yesterday_times) if yesterday_times else 0.0

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

        # --- 4. RAG Accuracy ---
        non_conv = [r for r in today_reqs if r["search_type"] != "conversational"]
        vector_hits = [r for r in non_conv if r["search_type"] == "vector"]
        rag_accuracy = (
            round(len(vector_hits) / len(non_conv) * 100, 1) if non_conv else 0.0
        )

        # --- 5. Chatbot Sessions ---
        today_sessions = {r["session_id"] for r in today_reqs if r["session_id"]}
        session_turn_counts: dict = {}
        for r in today_reqs:
            if r["session_id"]:
                session_turn_counts[r["session_id"]] = (
                    session_turn_counts.get(r["session_id"], 0) + 1
                )
        avg_turns = (
            round(sum(session_turn_counts.values()) / len(session_turn_counts), 1)
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
                "active_30min": len(active_ips),
                "concurrent_5min": len(concurrent_ips),
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


    # ── Topic categories for keyword matching ──────────────────────────────
    _TOPIC_CATEGORIES = {
        "Historical Monuments":  ["monument", "fort", "temple", "mahal", "minar", "palace", "ruins", "qutub", "taj", "hampi", "ajanta", "ellora", "khajuraho", "heritage site", "ancient", "archaeological"],
        "Museums & Galleries":   ["museum", "gallery", "collection", "exhibit", "artifact", "national museum", "salar jung", "victoria memorial", "ngma", "allahabad museum"],
        "Classical Dance Forms": ["dance", "bharatnatyam", "kathak", "odissi", "kuchipudi", "manipuri", "mohiniyattam", "classical dance", "folk dance", "performer", "performing arts"],
        "Vedic Heritage":        ["vedic", "veda", "upanishad", "sanskrit", "ritual", "vedic tradition", "mantra", "scripture", "rigveda", "samaveda", "yajurveda", "atharvaveda"],
        "UNESCO World Heritage": ["unesco", "world heritage", "intangible heritage", "inscription", "heritage list"],
        "National Archives":     ["archive", "manuscript", "document", "record", "abhilekh", "patal", "rare book", "inscription"],
        "Freedom Movement":      ["freedom", "independence", "gandhi", "nehru", "revolution", "1857", "struggle", "freedom fighter", "partition"],
        "Art & Craft":           ["art", "craft", "painting", "sculpture", "folk art", "handicraft", "warli", "madhubani", "pottery", "weaving", "textile"],
        "Festivals & Events":    ["festival", "event", "celebration", "mela", "utsav", "cultural event", "exhibition", "diwali", "holi", "navratri", "durga puja"],
        "Music":                 ["music", "raga", "classical music", "instrument", "carnatic", "hindustani", "tabla", "sitar", "vocalist", "musician"],
        "Schemes & Grants":      ["scheme", "grant", "scholarship", "fellowship", "award", "funding", "financial assistance", "yojana", "stipend"],
        "Tenders & Procurement": ["tender", "bid", "procurement", "rfp", "quotation", "contract", "notice inviting tender", "nit", "expression of interest", "eoi"],
        "Personalities":         ["who is", "biography", "artist", "author", "writer", "poet", "sculptor", "personality", "eminent"],
        "Architecture":          ["architecture", "architectural", "style", "structure", "building", "construction", "design", "indo-saracenic", "mughal architecture"],
        "Literature":            ["literature", "poetry", "poem", "novel", "book", "author", "writing", "literary", "language"],
    }

    def get_top_topics(self, limit: int = 10, date: str = None) -> dict:
        """Return top searched topic categories with counts."""
        rows = self._fetch_rows(date, columns="query_text")
        queries = [r["query_text"].lower() for r in rows if r["query_text"]]

        counts: dict[str, int] = {cat: 0 for cat in self._TOPIC_CATEGORIES}
        for q in queries:
            for category, keywords in self._TOPIC_CATEGORIES.items():
                if any(kw in q for kw in keywords):
                    counts[category] += 1

        sorted_topics = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        total = sum(c for _, c in sorted_topics) or 1

        return {
            "date": date or "all",
            "topics": [
                {"topic": cat, "count": cnt, "pct": round(cnt / total * 100, 1)}
                for cat, cnt in sorted_topics[:limit]
                if cnt > 0
            ],
        }

    def get_language_distribution(self, date: str = None) -> dict:
        """Return language breakdown with counts and percentages."""
        rows = self._fetch_rows(date, columns="language")
        lang_counts: dict[str, int] = {}
        for r in rows:
            lang = r["language"]
            if not lang:  # skip rows with no language data (old records)
                continue
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        total = sum(lang_counts.values()) or 1

        # Group minor languages into "Other"
        PRIMARY = {"en": "English", "hi": "Hindi"}
        result = {label: 0 for label in PRIMARY.values()}
        other = 0
        for lang, cnt in lang_counts.items():
            if lang in PRIMARY:
                result[PRIMARY[lang]] += cnt
            else:
                other += cnt

        distribution = [
            {"language": lang, "count": cnt, "pct": round(cnt / total * 100, 1)}
            for lang, cnt in result.items()
        ]
        if other:
            distribution.append({"language": "Other", "count": other, "pct": round(other / total * 100, 1)})

        distribution.sort(key=lambda x: x["count"], reverse=True)
        return {"date": date or "all", "total": total, "distribution": distribution}

    def get_portal_queries(self, date: str = None) -> dict:
        """Return source domain breakdown with counts and percentages."""
        rows = self._fetch_rows(date, columns="source_domain")
        domain_counts: dict[str, int] = {}
        for r in rows:
            domain = r["source_domain"]
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

        total = sum(domain_counts.values()) or 1
        sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "date": date or "all",
            "total": total,
            "portals": [
                {"domain": domain, "count": cnt, "pct": round(cnt / total * 100, 1)}
                for domain, cnt in sorted_domains
            ],
        }

    def _fetch_rows(self, date: str = None, columns: str = "*") -> list:
        """Fetch rows for a given date (or all time if date is None)."""
        if date:
            try:
                day_dt = datetime.datetime.strptime(date, "%Y-%m-%d")
                day_start = day_dt.timestamp()
                day_end = day_start + 86_400
                with self._lock:
                    cursor = self._conn.execute(
                        f"SELECT {columns} FROM requests WHERE timestamp >= ? AND timestamp < ?",
                        (day_start, day_end),
                    )
            except ValueError:
                with self._lock:
                    cursor = self._conn.execute(f"SELECT {columns} FROM requests")
        else:
            with self._lock:
                cursor = self._conn.execute(f"SELECT {columns} FROM requests")
        return [dict(r) for r in cursor.fetchall()]

    def get_traffic_data(self, date: str = None) -> dict:
        """
        Return hourly query count and unique user (IP) count for a given date.
        date: 'YYYY-MM-DD' string, defaults to today.
        """
        if date:
            try:
                day_dt = datetime.datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                day_dt = datetime.datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
        else:
            day_dt = datetime.datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        day_start = day_dt.timestamp()
        day_end = day_start + 86_400

        with self._lock:
            cursor = self._conn.execute(
                "SELECT timestamp, client_ip FROM requests "
                "WHERE timestamp >= ? AND timestamp < ?",
                (day_start, day_end),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        # Build 24 hourly buckets
        queries = [0] * 24
        users: list[set] = [set() for _ in range(24)]

        for r in rows:
            hour = int((r["timestamp"] - day_start) // 3600)
            if 0 <= hour < 24:
                queries[hour] += 1
                if r["client_ip"]:
                    users[hour].add(r["client_ip"])

        return {
            "date": day_dt.strftime("%Y-%m-%d"),
            "labels": [f"{h:02d}:00" for h in range(24)],
            "queries": queries,
            "users": [len(u) for u in users],
        }


    def get_response_time_data(self, date: str = None, sla_threshold: float = 3.0) -> dict:
        """
        Return hourly avg and P95 response time for a given date.
        date: 'YYYY-MM-DD' string, defaults to today.
        sla_threshold: horizontal SLA line value in seconds (default 3.0).
        """
        if date:
            try:
                day_dt = datetime.datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                day_dt = datetime.datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
        else:
            day_dt = datetime.datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        day_start = day_dt.timestamp()
        day_end = day_start + 86_400

        with self._lock:
            cursor = self._conn.execute(
                "SELECT timestamp, response_time FROM requests "
                "WHERE timestamp >= ? AND timestamp < ? AND response_time IS NOT NULL",
                (day_start, day_end),
            )
            rows = [dict(r) for r in cursor.fetchall()]

        # Build 24 hourly buckets
        buckets: list[list[float]] = [[] for _ in range(24)]

        for r in rows:
            hour = int((r["timestamp"] - day_start) // 3600)
            if 0 <= hour < 24:
                buckets[hour].append(r["response_time"])

        avg_per_hour = []
        p95_per_hour = []

        for times in buckets:
            if times:
                avg_per_hour.append(round(sum(times) / len(times), 2))
                sorted_times = sorted(times)
                p95_idx = max(0, int(0.95 * len(sorted_times)) - 1)
                p95_per_hour.append(round(sorted_times[p95_idx], 2))
            else:
                avg_per_hour.append(None)
                p95_per_hour.append(None)

        return {
            "date": day_dt.strftime("%Y-%m-%d"),
            "sla_threshold": sla_threshold,
            "labels": [f"{h:02d}:00" for h in range(24)],
            "avg": avg_per_hour,
            "p95": p95_per_hour,
        }


# Singleton used by all routes
metrics_service = MetricsService()
