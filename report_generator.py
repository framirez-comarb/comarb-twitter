"""
Generador de reporte HTML para el análisis de sentimiento.
Crea un dashboard interactivo con los datos scrapados.
"""

import json as _json
from collections import defaultdict
from datetime import datetime


def generate_html_report(data, output_file):
    """Genera un reporte HTML completo a partir de los datos."""

    # ── Calcular estadísticas globales ──
    total_tweets = sum(k["total_found"] for k in data["keywords"])
    total_pos = sum(k["sentiment_summary"]["positivo"] for k in data["keywords"])
    total_neg = sum(k["sentiment_summary"]["negativo"] for k in data["keywords"])
    total_neu = sum(k["sentiment_summary"]["neutro"] for k in data["keywords"])

    # Keyword más activo y más negativo
    kw_most_active = max(data["keywords"], key=lambda k: k["total_found"])
    kw_most_negative = max(data["keywords"], key=lambda k: k["sentiment_summary"]["negativo"])

    # Timeline: todos los posts ordenados por fecha
    all_posts = []
    for kw in data["keywords"]:
        for p in kw["posts"]:
            all_posts.append({**p, "keyword": kw["keyword"]})
    all_posts.sort(key=lambda x: x.get("date", ""), reverse=True)
    recent_posts = all_posts[:50]

    # ── Generar tarjetas de keywords ──
    keyword_sections = ""
    for kw in data["keywords"]:
        s = kw["sentiment_summary"]
        total = s["positivo"] + s["negativo"] + s["neutro"]
        pct_pos = round((s["positivo"] / total * 100) if total > 0 else 0)
        pct_neg = round((s["negativo"] / total * 100) if total > 0 else 0)
        pct_neu = 100 - pct_pos - pct_neg if total > 0 else 0

        dominant = "neutro"
        if s["negativo"] >= s["positivo"] and s["negativo"] >= s["neutro"]:
            dominant = "negativo"
        elif s["positivo"] >= s["neutro"]:
            dominant = "positivo"

        posts_html = ""
        for i, post in enumerate(kw["posts"]):
            sent_class = post["sentiment"]
            url_html = ""
            if post.get("url"):
                url_html = f'<a href="{post["url"]}" target="_blank" class="post-link">🔗 Ver en Twitter/X</a>'

            posts_html += f"""
            <div class="post-card {sent_class}" style="animation-delay: {i * 0.05}s">
                <div class="post-header">
                    <div class="post-user">
                        <span class="post-avatar">@</span>
                        <div>
                            <span class="post-name">{post.get('user', 'Desconocido')}</span>
                            <span class="post-handle">@{post.get('username', 'unknown')}</span>
                        </div>
                    </div>
                    <div class="post-meta">
                        <span class="sentiment-pill {sent_class}">{post['sentiment']}</span>
                        <span class="post-date">{post.get('date', 'Sin fecha')[:10]}</span>
                    </div>
                </div>
                <p class="post-text">{post['text']}</p>
                <div class="post-footer">
                    <div class="post-stats">
                        <span>❤️ {post.get('likes', 0)}</span>
                        <span>🔁 {post.get('retweets', 0)}</span>
                        <span>💬 {post.get('replies', 0)}</span>
                    </div>
                    {url_html}
                </div>
            </div>
            """

        error_html = ""
        if kw.get("error"):
            error_html = f'<div class="error-badge">⚠️ {kw["error"][:100]}</div>'

        keyword_sections += f"""
        <div class="keyword-section" id="kw-{kw['keyword']}">
            <div class="kw-header" onclick="toggleSection('{kw['keyword']}')">
                <div class="kw-title-area">
                    <div class="kw-icon {dominant}">#</div>
                    <div>
                        <h3 class="kw-title">{kw['keyword'].upper()}</h3>
                        <div class="kw-subtitle">
                            <span>{kw['total_found']} tweets</span>
                            <div class="mini-bar">
                                <div class="mini-pos" style="width:{pct_pos}%"></div>
                                <div class="mini-neu" style="width:{pct_neu}%"></div>
                                <div class="mini-neg" style="width:{pct_neg}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="kw-stats-right">
                    <span class="stat-pos">{s['positivo']}+</span>
                    <span class="stat-neu">{s['neutro']}~</span>
                    <span class="stat-neg">{s['negativo']}−</span>
                    <span class="toggle-arrow" id="arrow-{kw['keyword']}">▾</span>
                </div>
            </div>
            {error_html}
            <div class="kw-posts" id="posts-{kw['keyword']}">
                {posts_html if posts_html else '<div class="no-posts">No se encontraron tweets para esta palabra clave.</div>'}
            </div>
        </div>
        """

    # ── Timeline reciente ──
    timeline_html = ""
    for i, p in enumerate(recent_posts):
        timeline_html += f"""
        <div class="timeline-item" style="animation-delay: {i * 0.03}s">
            <div class="timeline-dot {p['sentiment']}"></div>
            <div class="timeline-content">
                <div class="timeline-top">
                    <span class="timeline-kw">#{p['keyword'].upper()}</span>
                    <span class="timeline-user">@{p.get('username', 'unknown')}</span>
                    <span class="timeline-date">{p.get('date', '')[:10]}</span>
                </div>
                <p class="timeline-text">{p['text'][:180]}{'...' if len(p.get('text','')) > 180 else ''}</p>
            </div>
        </div>
        """

    # ── Daily evolution data ──
    daily_counts = defaultdict(lambda: {"positivo": 0, "negativo": 0, "neutro": 0})
    for kw in data["keywords"]:
        for p in kw["posts"]:
            day = p.get("date", "")[:10]
            if day:
                daily_counts[day][p["sentiment"]] += 1
    sorted_days = sorted(daily_counts.keys())
    daily_labels_json = _json.dumps(sorted_days)
    daily_pos_json = _json.dumps([daily_counts[d]["positivo"] for d in sorted_days])
    daily_neg_json = _json.dumps([daily_counts[d]["negativo"] for d in sorted_days])
    daily_neu_json = _json.dumps([daily_counts[d]["neutro"] for d in sorted_days])

    # ── Stacked bar chart data ──
    sorted_kws = sorted(data["keywords"], key=lambda k: k["total_found"], reverse=True)
    stacked_labels = []
    stacked_pos = []
    stacked_neu = []
    stacked_neg = []
    for kw in sorted_kws:
        s = kw["sentiment_summary"]
        total = s["positivo"] + s["negativo"] + s["neutro"]
        stacked_labels.append(kw["keyword"].upper())
        stacked_pos.append(round((s["positivo"] / total * 100), 1) if total > 0 else 0)
        stacked_neu.append(round((s["neutro"] / total * 100), 1) if total > 0 else 0)
        stacked_neg.append(round((s["negativo"] / total * 100), 1) if total > 0 else 0)
    stacked_labels_json = _json.dumps(stacked_labels)
    stacked_pos_json = _json.dumps(stacked_pos)
    stacked_neu_json = _json.dumps(stacked_neu)
    stacked_neg_json = _json.dumps(stacked_neg)

    # ── HTML completo ──
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    period_from = data["period"]["from"]
    period_to = data["period"]["to"]

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>COMARB — Análisis de Sentimiento Twitter/X</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(145deg, #020617 0%, #0f172a 40%, #1e1b4b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            line-height: 1.6;
        }}

        /* ── Ambient effects ── */
        body::before, body::after {{
            content: '';
            position: fixed;
            border-radius: 50%;
            pointer-events: none;
            z-index: 0;
        }}
        body::before {{
            top: -200px; right: -200px;
            width: 500px; height: 500px;
            background: radial-gradient(circle, rgba(56,189,248,0.06) 0%, transparent 70%);
        }}
        body::after {{
            bottom: -150px; left: -150px;
            width: 400px; height: 400px;
            background: radial-gradient(circle, rgba(139,92,246,0.05) 0%, transparent 70%);
        }}

        .container {{
            max-width: 980px;
            margin: 0 auto;
            padding: 40px 24px 60px;
            position: relative;
            z-index: 1;
        }}

        /* ── Header ── */
        .header {{ margin-bottom: 36px; animation: fadeUp 0.5s both; }}

        .status-line {{
            display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
        }}
        .status-dot {{
            width: 8px; height: 8px; border-radius: 50%;
            background: #22c55e;
        }}
        .status-text {{
            font-size: 11px; color: #64748b; letter-spacing: 2px;
            font-weight: 600; font-family: 'JetBrains Mono', monospace;
        }}

        h1 {{
            font-size: 30px; font-weight: 800; letter-spacing: -0.5px;
            background: linear-gradient(135deg, #f1f5f9, #94a3b8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .subtitle {{
            font-size: 16px; font-weight: 400; color: #64748b; margin-top: 4px;
        }}
        .meta-line {{
            display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap;
            font-size: 12px; color: #475569; font-family: 'JetBrains Mono', monospace;
        }}

        /* ── Stats grid ── */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px; margin-bottom: 32px;
        }}
        .stat-card {{
            background: rgba(15,23,42,0.5);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(148,163,184,0.06);
            border-radius: 12px;
            padding: 14px 16px;
            animation: fadeUp 0.4s both;
        }}
        .stat-label {{
            font-size: 10px; color: #64748b; letter-spacing: 1px;
            font-weight: 700; text-transform: uppercase; margin-bottom: 6px;
        }}
        .stat-value {{
            font-size: 22px; font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
        }}
        .c-white {{ color: #e2e8f0; }}
        .c-green {{ color: #22c55e; }}
        .c-red {{ color: #ef4444; }}
        .c-gray {{ color: #94a3b8; }}
        .c-blue {{ color: #38bdf8; }}
        .c-orange {{ color: #f97316; }}

        /* ── Section titles ── */
        .section-title {{
            font-size: 13px; color: #64748b; letter-spacing: 1.5px;
            font-weight: 700; text-transform: uppercase; margin-bottom: 16px;
        }}

        /* ── Timeline ── */
        .timeline-section {{ margin-bottom: 32px; }}
        .timeline-item {{
            display: flex; align-items: flex-start; gap: 12px;
            padding: 10px 14px; background: rgba(15,23,42,0.35);
            border-radius: 10px; margin-bottom: 6px;
            animation: fadeUp 0.3s both;
        }}
        .timeline-dot {{
            width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex-shrink: 0;
        }}
        .timeline-dot.positivo {{ background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.4); }}
        .timeline-dot.negativo {{ background: #ef4444; box-shadow: 0 0 6px rgba(239,68,68,0.4); }}
        .timeline-dot.neutro {{ background: #94a3b8; box-shadow: 0 0 6px rgba(148,163,184,0.3); }}
        .timeline-content {{ flex: 1; min-width: 0; }}
        .timeline-top {{
            display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 3px;
        }}
        .timeline-kw {{
            font-size: 10px; font-weight: 800; color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            padding: 1px 6px; border-radius: 4px; background: rgba(56,189,248,0.1);
        }}
        .timeline-user {{
            font-size: 11px; color: #94a3b8; font-family: 'JetBrains Mono', monospace;
        }}
        .timeline-date {{
            font-size: 10px; color: #475569; margin-left: auto;
            font-family: 'JetBrains Mono', monospace;
        }}
        .timeline-text {{
            font-size: 12px; color: #b0b8c8; line-height: 1.5;
            overflow: hidden; display: -webkit-box;
            -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        }}

        /* ── Keyword sections ── */
        .keyword-section {{
            background: rgba(15,23,42,0.55);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(148,163,184,0.08);
            border-radius: 16px; overflow: hidden;
            margin-bottom: 16px;
            animation: fadeUp 0.5s both;
        }}
        .kw-header {{
            padding: 18px 22px; cursor: pointer;
            display: flex; align-items: center; justify-content: space-between; gap: 16px;
            border-bottom: 1px solid rgba(148,163,184,0.06);
            transition: background 0.2s;
        }}
        .kw-header:hover {{ background: rgba(56,189,248,0.03); }}
        .kw-title-area {{ display: flex; align-items: center; gap: 14px; }}
        .kw-icon {{
            width: 40px; height: 40px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 16px; font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
        }}
        .kw-icon.positivo {{ color: #22c55e; background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.19); }}
        .kw-icon.negativo {{ color: #ef4444; background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.19); }}
        .kw-icon.neutro {{ color: #94a3b8; background: rgba(148,163,184,0.06); border: 1px solid rgba(148,163,184,0.12); }}
        .kw-title {{
            font-size: 18px; font-weight: 800; color: #f1f5f9;
            font-family: 'JetBrains Mono', monospace; letter-spacing: 0.5px;
        }}
        .kw-subtitle {{
            display: flex; align-items: center; gap: 10px; margin-top: 4px;
            font-size: 12px; color: #64748b;
        }}
        .mini-bar {{
            display: flex; width: 100px; height: 5px; border-radius: 3px; overflow: hidden;
        }}
        .mini-pos {{ background: #22c55e; }}
        .mini-neu {{ background: #94a3b8; }}
        .mini-neg {{ background: #ef4444; }}
        .kw-stats-right {{
            display: flex; align-items: center; gap: 10px;
            font-size: 12px; font-family: 'JetBrains Mono', monospace;
        }}
        .stat-pos {{ color: #22c55e; }}
        .stat-neu {{ color: #94a3b8; }}
        .stat-neg {{ color: #ef4444; }}
        .toggle-arrow {{
            font-size: 14px; color: #475569; transition: transform 0.3s;
        }}
        .toggle-arrow.collapsed {{ transform: rotate(-90deg); }}

        .kw-posts {{
            padding: 12px 16px 16px;
            display: flex; flex-direction: column; gap: 8px;
            transition: max-height 0.4s ease, opacity 0.3s;
            overflow: hidden;
        }}
        .kw-posts.hidden {{
            max-height: 0 !important; padding: 0 16px; opacity: 0;
        }}

        /* ── Post cards ── */
        .post-card {{
            padding: 14px 16px;
            background: rgba(15,23,42,0.4);
            border-radius: 0 10px 10px 0;
            transition: background 0.2s;
            animation: fadeUp 0.35s both;
        }}
        .post-card:hover {{ background: rgba(15,23,42,0.65); }}
        .post-card.positivo {{ border-left: 3px solid #22c55e; }}
        .post-card.negativo {{ border-left: 3px solid #ef4444; }}
        .post-card.neutro {{ border-left: 3px solid #94a3b8; }}

        .post-header {{
            display: flex; align-items: center; justify-content: space-between;
            gap: 8px; margin-bottom: 8px; flex-wrap: wrap;
        }}
        .post-user {{ display: flex; align-items: center; gap: 8px; }}
        .post-avatar {{
            width: 28px; height: 28px; border-radius: 50%;
            background: rgba(56,189,248,0.1); display: flex;
            align-items: center; justify-content: center;
            font-size: 12px; font-weight: 800; color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
        }}
        .post-name {{
            font-size: 13px; font-weight: 700; color: #cbd5e1; display: block;
        }}
        .post-handle {{
            font-size: 11px; color: #64748b;
            font-family: 'JetBrains Mono', monospace;
        }}
        .post-meta {{ display: flex; align-items: center; gap: 8px; }}
        .sentiment-pill {{
            display: inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: 10px; font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase;
        }}
        .sentiment-pill.positivo {{ color: #22c55e; background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.2); }}
        .sentiment-pill.negativo {{ color: #ef4444; background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.2); }}
        .sentiment-pill.neutro {{ color: #94a3b8; background: rgba(148,163,184,0.1); border: 1px solid rgba(148,163,184,0.15); }}
        .post-date {{
            font-size: 11px; color: #64748b; font-family: 'JetBrains Mono', monospace;
        }}
        .post-text {{
            font-size: 13px; color: #c8d0dc; line-height: 1.6; margin-bottom: 8px;
            word-break: break-word;
        }}
        .post-footer {{
            display: flex; justify-content: space-between; align-items: center;
        }}
        .post-stats {{
            display: flex; gap: 14px; font-size: 12px; color: #64748b;
        }}
        .post-link {{
            font-size: 11px; color: #38bdf8; text-decoration: none; opacity: 0.7;
            transition: opacity 0.2s;
        }}
        .post-link:hover {{ opacity: 1; }}

        .no-posts {{
            padding: 24px; text-align: center; color: #475569; font-size: 13px;
        }}
        .error-badge {{
            padding: 8px 16px; background: rgba(239,68,68,0.08);
            border-top: 1px solid rgba(239,68,68,0.15);
            color: #fca5a5; font-size: 12px;
        }}

        /* ── Footer ── */
        .footer {{
            margin-top: 48px; padding-top: 20px;
            border-top: 1px solid rgba(148,163,184,0.06);
            text-align: center;
        }}
        .footer p {{
            font-size: 11px; color: #475569; line-height: 1.6;
        }}

        /* ── Animations ── */
        @keyframes fadeUp {{
            from {{ opacity: 0; transform: translateY(14px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* ── Responsive ── */
        @media (max-width: 640px) {{
            .container {{ padding: 24px 16px 40px; }}
            h1 {{ font-size: 22px; }}
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
            .stat-value {{ font-size: 18px; }}
            .kw-header {{ padding: 14px 16px; }}
            .kw-title {{ font-size: 15px; }}
            .kw-stats-right {{ gap: 6px; font-size: 11px; }}
        }}

        /* ── Scrollbar ── */
        ::-webkit-scrollbar {{ width: 5px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,0.2); border-radius: 3px; }}

        /* ── Print ── */
        @media print {{
            body {{ background: white; color: #1e293b; }}
            .kw-posts {{ max-height: none !important; opacity: 1 !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">

        <!-- Header -->
        <div class="header">
            <div class="status-line">
                <div class="status-dot"></div>
                <span class="status-text">REPORTE GENERADO</span>
            </div>
            <h1>Análisis de Sentimiento — Twitter/X</h1>
            <div class="subtitle">Sistemas Tributarios COMARB · Últimos 10 tweets por palabra clave</div>
            <div class="meta-line">
                <span>📅 {period_from} — {period_to}</span>
                <span>🔄 {generated_at}</span>
            </div>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card" style="animation-delay:0s">
                <div class="stat-label">Total Tweets</div>
                <div class="stat-value c-white">{total_tweets}</div>
            </div>
            <div class="stat-card" style="animation-delay:0.05s">
                <div class="stat-label">Positivos</div>
                <div class="stat-value c-green">{total_pos}</div>
            </div>
            <div class="stat-card" style="animation-delay:0.1s">
                <div class="stat-label">Negativos</div>
                <div class="stat-value c-red">{total_neg}</div>
            </div>
            <div class="stat-card" style="animation-delay:0.15s">
                <div class="stat-label">Neutros</div>
                <div class="stat-value c-gray">{total_neu}</div>
            </div>
            <div class="stat-card" style="animation-delay:0.2s">
                <div class="stat-label">Más Activo</div>
                <div class="stat-value c-blue">#{kw_most_active['keyword'].upper()}</div>
            </div>
            <div class="stat-card" style="animation-delay:0.25s">
                <div class="stat-label">Más Criticado</div>
                <div class="stat-value c-orange">#{kw_most_negative['keyword'].upper()}</div>
            </div>
        </div>

        <!-- Chart -->
        <div style="margin-bottom: 32px;">
            <div class="section-title">📊 Distribución de sentimiento por sistema</div>
            <div style="background: rgba(15,23,42,0.5); border-radius: 12px; padding: 20px; border: 1px solid rgba(148,163,184,0.06);">
                <canvas id="stackedChart" height="180"></canvas>
            </div>
        </div>

        <!-- Daily evolution chart -->
        <div style="margin-bottom: 32px;">
            <div class="section-title">📈 Evolución diaria de sentimiento (todas las palabras)</div>
            <div style="background: rgba(15,23,42,0.5); border-radius: 12px; padding: 20px; border: 1px solid rgba(148,163,184,0.06);">
                <canvas id="dailyChart" height="100"></canvas>
            </div>
        </div>

        <!-- Recent timeline -->
        <div class="timeline-section">
            <div class="section-title">⏱ Publicaciones más recientes (todas las palabras)</div>
            {timeline_html}
        </div>

        <!-- Keyword detail sections -->
        <div class="section-title" style="margin-top: 8px;">📋 Últimos 10 tweets por palabra clave</div>
        {keyword_sections}

        <!-- Footer -->
        <div class="footer">
            <p>
                Análisis generado con Twikit + TextBlob · Datos reales de Twitter/X<br>
                Período: {period_from} — {period_to} · Generado: {generated_at}
            </p>
        </div>
    </div>

    <script>
        function toggleSection(keyword) {{
            const posts = document.getElementById('posts-' + keyword);
            const arrow = document.getElementById('arrow-' + keyword);
            posts.classList.toggle('hidden');
            arrow.classList.toggle('collapsed');
        }}

        // Stacked 100% bar chart
        const ctxStacked = document.getElementById('stackedChart').getContext('2d');
        new Chart(ctxStacked, {{
            type: 'bar',
            data: {{
                labels: {stacked_labels_json},
                datasets: [
                    {{
                        label: 'Positivo',
                        data: {stacked_pos_json},
                        backgroundColor: '#22c55e',
                        borderRadius: 4
                    }},
                    {{
                        label: 'Neutro',
                        data: {stacked_neu_json},
                        backgroundColor: '#94a3b8',
                        borderRadius: 0
                    }},
                    {{
                        label: 'Negativo',
                        data: {stacked_neg_json},
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }}
                ]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#94a3b8', font: {{ family: "'DM Sans', sans-serif", size: 12 }} }}
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(ctx) {{ return ctx.dataset.label + ': ' + ctx.raw + '%'; }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        stacked: true,
                        max: 100,
                        ticks: {{ color: '#64748b', callback: function(v) {{ return v + '%'; }}, font: {{ family: "'JetBrains Mono', monospace", size: 11 }} }},
                        grid: {{ color: 'rgba(148,163,184,0.06)' }}
                    }},
                    y: {{
                        stacked: true,
                        ticks: {{ color: '#cbd5e1', font: {{ family: "'JetBrains Mono', monospace", size: 12, weight: 'bold' }} }},
                        grid: {{ display: false }}
                    }}
                }},
                animation: {{
                    duration: 1000,
                    easing: 'easeOutQuart'
                }}
            }},
            plugins: [{{
                afterDatasetsDraw: function(chart) {{
                    const ctx2 = chart.ctx;
                    chart.data.datasets.forEach(function(dataset, i) {{
                        const meta = chart.getDatasetMeta(i);
                        meta.data.forEach(function(bar, index) {{
                            const value = dataset.data[index];
                            if (value < 5) return;
                            ctx2.fillStyle = '#fff';
                            ctx2.font = "bold 11px 'JetBrains Mono', monospace";
                            ctx2.textAlign = 'center';
                            ctx2.textBaseline = 'middle';
                            const x = bar.x - (bar.width / 2) + (bar.width * 0.5);
                            ctx2.fillText(value + '%', (bar.base + bar.x) / 2, bar.y);
                        }});
                    }});
                }}
            }}]
        }});

        // Daily evolution chart
        const ctx = document.getElementById('dailyChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {daily_labels_json},
                datasets: [
                    {{
                        label: 'Positivo',
                        data: {daily_pos_json},
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34,197,94,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#22c55e',
                        borderWidth: 2
                    }},
                    {{
                        label: 'Neutro',
                        data: {daily_neu_json},
                        borderColor: '#94a3b8',
                        backgroundColor: 'rgba(148,163,184,0.08)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#94a3b8',
                        borderWidth: 2
                    }},
                    {{
                        label: 'Negativo',
                        data: {daily_neg_json},
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239,68,68,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#ef4444',
                        borderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                interaction: {{ mode: 'index', intersect: false }},
                plugins: {{
                    legend: {{
                        labels: {{ color: '#94a3b8', font: {{ family: "'DM Sans', sans-serif", size: 12 }} }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#64748b', font: {{ family: "'JetBrains Mono', monospace", size: 10 }}, maxRotation: 45 }},
                        grid: {{ color: 'rgba(148,163,184,0.06)' }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: '#64748b', font: {{ family: "'JetBrains Mono', monospace", size: 11 }}, precision: 0 }},
                        grid: {{ color: 'rgba(148,163,184,0.06)' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  ✅ Reporte generado: {output_file}")
    print(f"  📊 {total_tweets} tweets analizados")
    print(f"  📈 {total_pos} positivos | {total_neu} neutros | {total_neg} negativos")
