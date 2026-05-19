"""
Generate architecture diagram for Ministry of Culture Chatbot.
Run: python generate_architecture_diagram.py
Output: architecture_diagram.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Canvas ──────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(28, 20))
ax.set_xlim(0, 28)
ax.set_ylim(0, 20)
ax.axis("off")
fig.patch.set_facecolor("#F0F4F8")

# ── Color Palette ────────────────────────────────────────────────────────────
C = {
    "client":     "#2C3E50",
    "gateway":    "#1A237E",
    "routes":     "#1565C0",
    "nlp":        "#E65100",
    "search":     "#2E7D32",
    "llm":        "#6A1B9A",
    "storage":    "#37474F",
    "external":   "#B71C1C",
    "pipeline":   "#00695C",
    "layer_bg":   "#FFFFFF",
    "arrow":      "#546E7A",
    "title_bg":   "#0D47A1",
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def box(ax, x, y, w, h, label, sublabel=None, color="#1565C0", fontsize=8.5,
        text_color="white", alpha=0.92, radius=0.18):
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle=f"round,pad=0.05,rounding_size={radius}",
                          linewidth=1.2, edgecolor=color,
                          facecolor=color, alpha=alpha, zorder=3)
    ax.add_patch(rect)
    cy = y + h / 2 + (0.1 if sublabel else 0)
    ax.text(x + w / 2, cy, label, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=text_color, zorder=4,
            wrap=True)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.18, sublabel, ha="center", va="center",
                fontsize=6.5, color=text_color, alpha=0.85, zorder=4, style="italic")

def layer_bg(ax, y, h, label, color, text_color="white"):
    rect = FancyBboxPatch((0.15, y), 27.7, h,
                          boxstyle="round,pad=0.05,rounding_size=0.2",
                          linewidth=1.5, edgecolor=color,
                          facecolor=color, alpha=0.10, zorder=1)
    ax.add_patch(rect)
    ax.text(0.42, y + h / 2, label, ha="left", va="center",
            fontsize=7.5, fontweight="bold", color=color,
            rotation=90, zorder=2)

def arrow(ax, x1, y1, x2, y2, color="#546E7A", style="->", lw=1.4):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color,
                                lw=lw, connectionstyle="arc3,rad=0.0"),
                zorder=5)

def curved_arrow(ax, x1, y1, x2, y2, color="#546E7A", rad=0.25, lw=1.2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color,
                                lw=lw, connectionstyle=f"arc3,rad={rad}"),
                zorder=5)

# ════════════════════════════════════════════════════════════════════════════
# TITLE
# ════════════════════════════════════════════════════════════════════════════
title_rect = FancyBboxPatch((0.15, 19.1), 27.7, 0.75,
                             boxstyle="round,pad=0.05,rounding_size=0.15",
                             linewidth=0, facecolor=C["title_bg"], zorder=3)
ax.add_patch(title_rect)
ax.text(14, 19.47, "Ministry of Culture India — Chatbot Architecture",
        ha="center", va="center", fontsize=16, fontweight="bold",
        color="white", zorder=4)
ax.text(14, 19.17, "End-to-End Layered Architecture  |  RAG + Hybrid Search + Multilingual",
        ha="center", va="center", fontsize=9, color="#BBDEFB", zorder=4)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 1 — CLIENT  (y 17.9 – 18.85)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 17.85, 1.05, "CLIENT", C["client"])
box(ax, 5.5,  18.1, 3.2, 0.65, "Web Browser / Frontend", color=C["client"])
box(ax, 10.5, 18.1, 2.8, 0.65, "Mobile App",             color=C["client"])
box(ax, 15.0, 18.1, 3.2, 0.65, "API Consumer (Postman)", color=C["client"])

# ════════════════════════════════════════════════════════════════════════════
# LAYER 2 — API GATEWAY  (y 16.6 – 17.7)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 16.55, 1.15, "API GATEWAY", C["gateway"])
box(ax, 4.0, 16.75, 4.5, 0.7, "FastAPI Application", "main.py + CORS Middleware", color=C["gateway"])
box(ax, 9.5, 16.75, 4.0, 0.7, "Uvicorn ASGI Server",  "uvicorn[standard]",         color=C["gateway"])
box(ax, 14.8, 16.75, 4.5, 0.7, "Pydantic Validation",  "ChatContextRequest / SearchRequest", color=C["gateway"])

# ════════════════════════════════════════════════════════════════════════════
# LAYER 3 — ROUTES  (y 15.2 – 16.4)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 15.15, 1.25, "ROUTES", C["routes"])
bw = 3.8
gap = 0.28
starts = [0.7, 0.7 + bw + gap, 0.7 + 2*(bw+gap), 0.7 + 3*(bw+gap), 0.7 + 4*(bw+gap), 0.7 + 5*(bw+gap)]
labels = [
    ("POST /chat-hybrid-context", "Primary — Hybrid + Context (chat.py)"),
    ("POST /search",              "Semantic Search + Pagination"),
    ("GET  /metrics/kpis",        "Real-time Dashboard KPIs"),
    ("POST /chat-vector-context", "Vector DB + Conversation"),
    ("POST /chat/stream",         "SSE Streaming Response"),
    ("DELETE /chat-context",      "Session Management"),
]
for i, (lbl, sub) in enumerate(labels):
    bx = 0.85 + i * (bw + gap)
    box(ax, bx, 15.3, bw, 0.72, lbl, sub, color=C["routes"], fontsize=7.8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 4 — NLP / PROCESSING  (y 13.8 – 15.0)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 13.75, 1.25, "LANGUAGE &\nNLP", C["nlp"])
nlp_boxes = [
    ("Language Detection",     "langdetect\n13 Indian languages"),
    ("Intent Detection",       "Greeting / Thanks\nFarewell / Help"),
    ("Translation Service",    "deep_translator\nQuery → English"),
    ("Query Enhancement",      "Vague query expansion\nwith history context"),
    ("Query Classifier",       "location / list\n/ general"),
]
bw2 = 4.5
for i, (lbl, sub) in enumerate(nlp_boxes):
    box(ax, 0.85 + i*(bw2+0.35), 13.9, bw2, 0.72, lbl, sub,
        color=C["nlp"], fontsize=8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 5a — SEARCH SERVICES  (y 12.35 – 13.6)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 12.3, 1.3, "SEARCH\nSERVICES", C["search"])
box(ax, 0.85, 12.45, 6.0, 0.8,
    "Vector Search Service",
    "vector_search_service.py\nChromaDB semantic search | min_similarity=0.50 | top_k retrieval",
    color=C["search"], fontsize=8)
box(ax, 7.5, 12.45, 5.5, 0.8,
    "Web Search Service",
    "web_search.py | Serper API\nTrusted domains only | LRU cache (100 items)",
    color=C["search"], fontsize=8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 5b — LLM SERVICES  (right side of layer 5)
# ════════════════════════════════════════════════════════════════════════════
box(ax, 13.7, 12.45, 4.2, 0.8,
    "Vector LLM Service",
    "vector_llm_service.py\nFast prompt | junk cleaning | cache",
    color=C["llm"], fontsize=8)
box(ax, 18.5, 12.45, 4.0, 0.8,
    "Context LLM Service",
    "context_llm_service.py\nConversation history | last 6 msgs",
    color=C["llm"], fontsize=8)
box(ax, 23.1, 12.45, 4.6, 0.8,
    "Streaming LLM",
    "streaming_llm_service.py\nSSE | token buffering",
    color=C["llm"], fontsize=8)

ax.text(14.0, 13.55, "LLM GENERATION SERVICES", ha="left", va="center",
        fontsize=7.5, fontweight="bold", color=C["llm"], zorder=2)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 6 — STORAGE & EXTERNAL  (y 10.8 – 12.1)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 10.75, 1.4, "STORAGE &\nEXTERNAL", C["storage"])

box(ax, 0.85,  10.92, 4.0, 0.88,
    "ChromaDB Vector Store",
    "vector_store.py\nall-MiniLM-L6-v2 | 384-dim\n./data/chroma_db (persistent)",
    color=C["storage"], fontsize=7.8)
box(ax, 5.5,   10.92, 3.8, 0.88,
    "Conversation Manager",
    "conversation_manager.py\nIn-memory sessions | UUID\n60-min TTL | 20 msg max",
    color=C["storage"], fontsize=7.8)
box(ax, 9.95,  10.92, 3.8, 0.88,
    "SQLite — metrics.db",
    "metrics_service.py\nPersistent KPI tracking\nWAL mode | thread-safe",
    color=C["storage"], fontsize=7.8)
box(ax, 14.4,  10.92, 3.8, 0.88,
    "Serper API  [cloud]",
    "google.serper.dev\nWeb search fallback\nTrusted gov. sites only",
    color=C["external"], fontsize=7.8)
box(ax, 18.85, 10.92, 3.8, 0.88,
    "Google Translate  [cloud]",
    "deep_translator\nQuery → English\nAnswer → User language",
    color=C["external"], fontsize=7.8)
box(ax, 23.3,  10.92, 4.35, 0.88,
    "Ollama — Qwen2.5:3b  [local]",
    "Local LLM inference\ntemp=0.1 | 500 tokens\n8 CPU threads | no GPU",
    color="#4A148C", fontsize=7.8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 7 — EMBEDDING SERVICE  (y 9.35 – 10.6)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 9.3, 1.3, "EMBEDDING", C["pipeline"])
box(ax, 0.85, 9.45, 5.5, 0.78,
    "Embedding Service",
    "embedding_service.py\nsentence-transformers/all-MiniLM-L6-v2\n384-dim vectors | batch processing",
    color=C["pipeline"], fontsize=8)
box(ax, 7.1, 9.45, 4.5, 0.78,
    "Prompt Services",
    "prompt_service.py\ncontext_prompt_service.py\nSystem + user prompt builder",
    color=C["llm"], fontsize=8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 8 — DATA INGESTION PIPELINE  (y 7.6 – 9.1)
# ════════════════════════════════════════════════════════════════════════════
layer_bg(ax, 7.55, 1.6, "DATA\nINGESTION\nPIPELINE", C["pipeline"])
pipe = [
    ("Web Scraper",      "web_scraper.py\n4 ministry sites\nmax 500 pages/domain\n2s rate limit"),
    ("Text Processor",   "text_processor.py\nHTML cleaning\nChunk: 800 chars\nOverlap: 100 chars"),
    ("Embedding Gen.",   "embedding_service.py\nall-MiniLM-L6-v2\n384-dim | batch 5000"),
    ("Vector Store",     "vector_store.py\nChromaDB upsert\nPersist ./data/chroma_db\nCollection stats"),
]
pw = 5.2
for i, (lbl, sub) in enumerate(pipe):
    bx = 0.85 + i * (pw + 0.8)
    box(ax, bx, 7.72, pw, 1.1, lbl, sub, color=C["pipeline"], fontsize=8)
    if i < len(pipe) - 1:
        arrow(ax, bx + pw, 7.72 + 0.55, bx + pw + 0.82, 7.72 + 0.55,
              color=C["pipeline"], lw=2.2)

# ════════════════════════════════════════════════════════════════════════════
# MAIN FLOW ARROWS (vertical, layer to layer)
# ════════════════════════════════════════════════════════════════════════════
# Client → Gateway
arrow(ax, 11.0, 18.1, 11.0, 17.45, color=C["arrow"], lw=1.8)
# Gateway → Routes
arrow(ax, 11.0, 16.75, 11.0, 16.4, color=C["arrow"], lw=1.8)
# Routes → NLP
arrow(ax, 11.0, 15.3, 11.0, 15.0, color=C["arrow"], lw=1.8)
# NLP → Search / LLM
arrow(ax, 6.0,  13.9, 6.0,  13.6, color=C["search"], lw=1.8)
arrow(ax, 17.0, 13.9, 17.0, 13.6, color=C["llm"],    lw=1.8)
# Search → Storage
arrow(ax, 4.0,  12.45, 2.85, 11.8, color=C["storage"], lw=1.5)
# Web Search → Serper
arrow(ax, 10.0, 12.45, 16.3, 11.8, color=C["external"], lw=1.5)
# LLM → Ollama
arrow(ax, 25.2, 12.45, 25.5, 11.8, color="#4A148C", lw=1.5)
# LLM → Prompt Services
arrow(ax, 17.0, 12.45, 9.0,  10.23, color=C["llm"], lw=1.3)
# Vector Search → ChromaDB
arrow(ax, 3.0,  12.45, 2.85, 11.8, color=C["storage"], lw=1.5)
# Translation → Google Translate
curved_arrow(ax, 7.6, 13.9, 20.75, 11.8, color=C["external"], rad=-0.15, lw=1.3)
# Embedding → Vector Store
arrow(ax, 3.6, 9.45, 2.85, 10.23, color=C["pipeline"], lw=1.5)

# ════════════════════════════════════════════════════════════════════════════
# RESPONSE FLOW ARROW (right side feedback)
# ════════════════════════════════════════════════════════════════════════════
ax.annotate("", xy=(27.0, 17.8), xytext=(27.0, 12.5),
            arrowprops=dict(arrowstyle="->", color="#1B5E20", lw=2.0,
                            connectionstyle="arc3,rad=0.0"), zorder=5)
ax.text(27.3, 15.2, "Response\nto Client", ha="left", va="center",
        fontsize=8, fontweight="bold", color="#1B5E20", rotation=90)

# ════════════════════════════════════════════════════════════════════════════
# DECISION DIAMOND — Hybrid Logic
# ════════════════════════════════════════════════════════════════════════════
dx, dy, dw, dh = 11.5, 14.3, 3.0, 0.6
diamond = plt.Polygon(
    [[dx + dw/2, dy + dh], [dx + dw, dy + dh/2],
     [dx + dw/2, dy],       [dx,      dy + dh/2]],
    closed=True, facecolor="#FFF9C4", edgecolor="#F57F17", linewidth=1.5, zorder=3)
ax.add_patch(diamond)
ax.text(dx + dw/2, dy + dh/2, "Similarity\n≥ 0.50?", ha="center", va="center",
        fontsize=7, fontweight="bold", color="#E65100", zorder=4)
ax.text(dx - 0.1, dy + dh/2 + 0.05, "No → Web", ha="right", va="center",
        fontsize=7, color=C["search"], style="italic")
ax.text(dx + dw + 0.1, dy + dh/2 + 0.05, "Yes → Vector", ha="left", va="center",
        fontsize=7, color=C["search"], style="italic")

# ════════════════════════════════════════════════════════════════════════════
# SUPPORTED LANGUAGES BOX
# ════════════════════════════════════════════════════════════════════════════
box(ax, 14.8, 13.9, 12.8, 0.72,
    "13 Supported Languages:  English · Hindi · Tamil · Telugu · Bengali · Marathi · Gujarati · Kannada · Malayalam · Punjabi · Odia · Assamese · Urdu",
    color=C["nlp"], fontsize=7.5)

# ════════════════════════════════════════════════════════════════════════════
# LEGEND
# ════════════════════════════════════════════════════════════════════════════
legend_items = [
    (C["client"],   "Client Layer"),
    (C["gateway"],  "API Gateway"),
    (C["routes"],   "Routes / Endpoints"),
    (C["nlp"],      "NLP & Language"),
    (C["search"],   "Search Services"),
    (C["llm"],      "LLM Generation"),
    (C["storage"],  "Storage (local)"),
    (C["external"], "External APIs"),
    (C["pipeline"], "Ingestion Pipeline"),
]
lx, ly = 0.85, 7.0
ax.text(lx, ly + 0.25, "LEGEND", fontsize=8, fontweight="bold", color="#37474F")
for i, (col, label) in enumerate(legend_items):
    rx = lx + i * 3.0
    patch = FancyBboxPatch((rx, ly - 0.35), 0.45, 0.3,
                           boxstyle="round,pad=0.02", facecolor=col,
                           edgecolor=col, zorder=3)
    ax.add_patch(patch)
    ax.text(rx + 0.55, ly - 0.2, label, fontsize=7.5, va="center", color="#37474F")

# ════════════════════════════════════════════════════════════════════════════
# FOOTNOTES
# ════════════════════════════════════════════════════════════════════════════
ax.text(14.0, 0.25,
        "Trusted Sources: culture.gov.in  |  indianculture.gov.in  |  vedicheritage.gov.in  |  museumsofindia.gov.in    "
        "·    Vector DB: ChromaDB (all-MiniLM-L6-v2, 384-dim)    ·    LLM: Ollama Qwen2.5:3b (local CPU)",
        ha="center", va="center", fontsize=8, color="#607D8B", style="italic")

plt.tight_layout(pad=0.5)
plt.savefig("architecture_diagram.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved: architecture_diagram.png")
