"""
Generador de reporte HTML para el análisis de sentimiento.
Crea un dashboard interactivo con los datos scrapados.
"""

import json as _json
import re
from collections import Counter, defaultdict
from datetime import datetime


# Stopwords castellano + ruido típico de Twitter (lista compacta, no exhaustiva)
_STOPWORDS = set("""
a al algo algun alguna algunas alguno algunos ante antes aquel aquella aquellas aquello aquellos aqui
asi aun aunque cada como con contra cual cuales cuando cuanto cuantos da de del desde donde dos
el ella ellas ello ellos en entre era eran eras eres es esa esas ese eso esos esta estaba estaban
estado estamos estan estar estas este esto estos estoy fue fuera fueron ha habia haber habia
habian han has hasta hay he hizo igual la las le les lo los mas me mi mis mucho muchos muy nada
ni no nos nosotros nuestra nuestras nuestro nuestros o os otra otras otro otros para pero poco
por porque que quien quienes se sea sean ser si sido siendo sin sobre solo son soy su sus tambien
tanto te tener tengo ti tiene tienen toda todas todo todos tras tu tus un una unas uno unos usted
ustedes va vamos van varios ver vos vosotros y ya yo eso ese esa esos esas mismo misma esta este
estos estas hacer hace haces hago hizo hicieron lo la le les nos nuestro nuestra ya solo bien mal
ahora aqui alli ahi cuando como porque cual quien donde mientras pues entonces tambien tampoco
todavia siempre nunca jamas mientras quiza quizas tal vez asi luego despues antes hoy mañana ayer
soy son fui fuiste fueron sere seras sera seremos seran sea seas seamos sean siendo sido le lo
http https www com co rt via vi
""".split())


def _tokenize(text):
    """Limpia y tokeniza para extracción de n-gramas."""
    if not text:
        return []
    t = text.lower()
    t = re.sub(r"http\S+|www\.\S+", " ", t)        # urls
    t = re.sub(r"@\w+", " ", t)                    # menciones
    t = re.sub(r"#(\w+)", r"\1", t)                # hashtags → palabra
    t = re.sub(r"[^\wáéíóúüñ\s]", " ", t)         # quitar puntuación
    tokens = [w for w in t.split() if len(w) > 2 and not w.isdigit() and w not in _STOPWORDS]
    return tokens


_MAX_MERGED_TOKENS = 6


def _merge_overlapping(selected):
    """Combina n-gramas que se solapan en ≥2 tokens consecutivos, hasta MAX tokens.
    Ej: 'activa menem scioli' + 'menem scioli pareja' → 'activa menem scioli pareja'."""
    changed = True
    while changed:
        changed = False
        for i in range(len(selected)):
            for j in range(len(selected)):
                if i == j:
                    continue
                a = selected[i]["phrase"].split()
                b = selected[j]["phrase"].split()
                max_ov = min(len(a), len(b)) - 1
                for k in range(max_ov, 1, -1):
                    if a[-k:] == b[:k]:
                        merged_tokens = a + b[k:]
                        if len(merged_tokens) > _MAX_MERGED_TOKENS:
                            continue
                        if len(set(merged_tokens)) != len(merged_tokens):
                            continue  # rechazar merges con tokens duplicados
                        merged_phrase = " ".join(merged_tokens)
                        merged_count = max(selected[i]["count"], selected[j]["count"])
                        merged_sent = selected[i]["sentiment"] if selected[i]["count"] >= selected[j]["count"] else selected[j]["sentiment"]
                        new_item = {"phrase": merged_phrase, "count": merged_count, "sentiment": merged_sent}
                        for idx in sorted([i, j], reverse=True):
                            selected.pop(idx)
                        selected.append(new_item)
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    # Dedupe final por substring (eliminar n-gramas contenidos en otro de igual o mayor count)
    selected.sort(key=lambda s: (-s["count"], -len(s["phrase"])))
    final = []
    for s in selected:
        if any(s["phrase"] in f["phrase"] and f["count"] >= s["count"] for f in final):
            continue
        final.append(s)
    return final


def _extract_top_ngrams(posts, keyword, top_n=5, min_count=2):
    """Extrae top n-gramas (bi/tri/4-gramas) por frecuencia, mergeando solapamientos.
    Devuelve lista de dicts {phrase, count, sentiment}."""
    kw_low = (keyword or "").lower()
    counts = Counter()
    sent_acc = defaultdict(lambda: Counter())  # phrase -> Counter(sentiment)
    for p in posts:
        toks = [w for w in _tokenize(p.get("text", "")) if w != kw_low]
        sent = p.get("sentiment", "neutro")
        for n in (2, 3, 4):
            for i in range(len(toks) - n + 1):
                gram = tuple(toks[i:i + n])
                if kw_low in gram:
                    continue
                phrase = " ".join(gram)
                counts[phrase] += 1
                sent_acc[phrase][sent] += 1
    # Orden: por frecuencia desc, longitud desc (más informativo gana empates).
    items = [(p, c) for p, c in counts.items() if c >= min_count]
    items.sort(key=lambda x: (-x[1], -len(x[0]), x[0]))
    selected = []
    # Sobreasignar para tener margen antes del merge final
    pool_target = top_n * 3
    for phrase, count in items:
        # ¿Hay un n-grama seleccionado que contiene a este con count ≥?
        if any(phrase in s["phrase"] and s["count"] >= count for s in selected):
            continue
        # ¿Este contiene a uno seleccionado con mismo count? Reemplazarlo.
        replaced = False
        for i, s in enumerate(selected):
            if s["phrase"] in phrase and s["count"] == count:
                dom_sent = sent_acc[phrase].most_common(1)[0][0]
                selected[i] = {"phrase": phrase, "count": count, "sentiment": dom_sent}
                replaced = True
                break
        if replaced:
            continue
        dom_sent = sent_acc[phrase].most_common(1)[0][0]
        selected.append({"phrase": phrase, "count": count, "sentiment": dom_sent})
        if len(selected) >= pool_target:
            break
    # Merge de n-gramas solapados (suffix de uno == prefix del otro, ≥2 tokens)
    selected = _merge_overlapping(selected)
    # Reordenar y truncar
    selected.sort(key=lambda s: (-s["count"], -len(s["phrase"])))
    return selected[:top_n]


# Metadatos visuales para emociones (modelo pysentimiento ES)
EMOTION_META = {
    "anger":    {"emoji": "😠", "label": "Enojo",    "color": "#ef4444"},
    "disgust":  {"emoji": "🤢", "label": "Asco",     "color": "#a855f7"},
    "fear":     {"emoji": "😨", "label": "Miedo",    "color": "#8b5cf6"},
    "joy":      {"emoji": "😊", "label": "Alegría",  "color": "#22c55e"},
    "sadness":  {"emoji": "😢", "label": "Tristeza", "color": "#3b82f6"},
    "surprise": {"emoji": "😲", "label": "Sorpresa", "color": "#f59e0b"},
    "others":   {"emoji": "·",  "label": "Neutra",   "color": "#94a3b8"},
}


def _emo_meta(name):
    return EMOTION_META.get(name or "others", EMOTION_META["others"])


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

    # ── Estadísticas de emociones (si están disponibles) ──
    emotion_total = Counter()
    has_emotions = False
    for kw in data["keywords"]:
        for p in kw.get("posts", []):
            if "emotion" in p:
                has_emotions = True
                emotion_total[p["emotion"]] += 1
    # Emoción dominante global con desempate sesgado a negativas (corpus de quejas)
    EMO_PRIORITY = ["anger", "disgust", "sadness", "fear", "surprise", "joy"]
    _prio = {e: i for i, e in enumerate(EMO_PRIORITY)}
    emotion_dominant_global = "others"
    non_others = [(e, n) for e, n in emotion_total.items() if e != "others"]
    if non_others:
        non_others.sort(key=lambda en: (-en[1], _prio.get(en[0], 99)))
        emotion_dominant_global = non_others[0][0]
    emo_meta_global = _emo_meta(emotion_dominant_global)

    # Timeline: todos los posts ordenados por fecha
    all_posts = []
    for kw in data["keywords"]:
        for p in kw["posts"]:
            all_posts.append({**p, "keyword": kw["keyword"]})
    all_posts.sort(key=lambda x: x.get("date", ""), reverse=True)
    recent_posts = all_posts[:12]
    top_liked_posts = sorted(all_posts, key=lambda x: x.get("likes", 0) or 0, reverse=True)[:12]

    # ── N-gramas asociados por keyword ──
    ngrams_html = ""
    ngrams_empty_kws = []
    for kw in data["keywords"]:
        grams = _extract_top_ngrams(kw.get("posts", []), kw["keyword"], top_n=5, min_count=2)
        if not grams:
            ngrams_empty_kws.append(kw["keyword"].upper())
            continue
        max_c = max(g["count"] for g in grams)
        min_c = min(g["count"] for g in grams)
        pills = ""
        for g in grams:
            # Tamaño proporcional: 11px (min) → 18px (max)
            if max_c == min_c:
                size = 14
            else:
                size = 11 + round(7 * (g["count"] - min_c) / (max_c - min_c))
            pills += (
                f'<span class="ngram-pill {g["sentiment"]}" '
                f'style="font-size:{size}px" title="{g["count"]} menciones">'
                f'{g["phrase"]} <em>{g["count"]}</em></span>'
            )
        ngrams_html += f"""
        <div class="ngram-card">
            <div class="ngram-kw">#{kw['keyword'].upper()}</div>
            <div class="ngram-pills">{pills}</div>
        </div>
        """
    ngrams_empty_html = (
        f'<span class="ngrams-empty-note">— sin frases frecuentes: {", ".join(ngrams_empty_kws)}</span>'
        if ngrams_empty_kws else ""
    )

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

            # Emoción (opcional, si el JSON está enriquecido)
            emo_pill_html = ""
            if post.get("emotion") and post["emotion"] != "others":
                em = _emo_meta(post["emotion"])
                emo_pill_html = (
                    f'<span class="emotion-pill" title="Emoción dominante: {em["label"]}" '
                    f'style="color:{em["color"]};border-color:{em["color"]}33;background:{em["color"]}1a">'
                    f'{em["emoji"]} {em["label"]}</span>'
                )

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
                        {emo_pill_html}
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

        # Emoción dominante por keyword (si los datos vienen enriquecidos)
        kw_emo_html = ""
        kw_emo_dom = kw.get("emotion_dominant")
        if kw_emo_dom and kw_emo_dom != "others":
            em = _emo_meta(kw_emo_dom)
            n_emo = kw.get("emotion_summary", {}).get(kw_emo_dom, 0)
            kw_emo_html = (
                f'<span class="kw-emotion" title="Emoción dominante en {kw["keyword"].upper()}" '
                f'style="color:{em["color"]};border-color:{em["color"]}33;background:{em["color"]}1a">'
                f'{em["emoji"]} {em["label"]} ({n_emo})</span>'
            )

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
                            {kw_emo_html}
                        </div>
                    </div>
                </div>
                <div class="kw-stats-right">
                    <span class="stat-pos">{s['positivo']}+</span>
                    <span class="stat-neu">{s['neutro']}~</span>
                    <span class="stat-neg">{s['negativo']}−</span>
                    <span class="toggle-arrow collapsed" id="arrow-{kw['keyword']}">▾</span>
                </div>
            </div>
            {error_html}
            <div class="kw-posts hidden" id="posts-{kw['keyword']}">
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
                <p class="timeline-text">{p['text'][:280]}{'...' if len(p.get('text','')) > 280 else ''}</p>
            </div>
        </div>
        """

    # ── Top 10 con más likes ──
    top_liked_html = ""
    for i, p in enumerate(top_liked_posts):
        top_liked_html += f"""
        <div class="timeline-item" style="animation-delay: {i * 0.03}s">
            <div class="timeline-dot {p['sentiment']}"></div>
            <div class="timeline-content">
                <div class="timeline-top">
                    <span class="timeline-kw">#{p['keyword'].upper()}</span>
                    <span class="timeline-user">@{p.get('username', 'unknown')}</span>
                    <span class="timeline-date">{p.get('date', '')[:10]}</span>
                    <span class="timeline-likes">❤️ {p.get('likes', 0)}</span>
                </div>
                <p class="timeline-text">{p['text'][:280]}{'...' if len(p.get('text','')) > 280 else ''}</p>
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
    stacked_pos_n = []
    stacked_neu_n = []
    stacked_neg_n = []
    for kw in sorted_kws:
        s = kw["sentiment_summary"]
        total = s["positivo"] + s["negativo"] + s["neutro"]
        stacked_labels.append(f"{kw['keyword'].upper()} ({total})")
        stacked_pos.append(round((s["positivo"] / total * 100), 1) if total > 0 else 0)
        stacked_neu.append(round((s["neutro"] / total * 100), 1) if total > 0 else 0)
        stacked_neg.append(round((s["negativo"] / total * 100), 1) if total > 0 else 0)
        stacked_pos_n.append(s["positivo"])
        stacked_neu_n.append(s["neutro"])
        stacked_neg_n.append(s["negativo"])
    stacked_labels_json = _json.dumps(stacked_labels)
    stacked_pos_json = _json.dumps(stacked_pos)
    stacked_neu_json = _json.dumps(stacked_neu)
    stacked_neg_json = _json.dumps(stacked_neg)
    stacked_pos_n_json = _json.dumps(stacked_pos_n)
    stacked_neu_n_json = _json.dumps(stacked_neu_n)
    stacked_neg_n_json = _json.dumps(stacked_neg_n)

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
        .timeline-likes {{
            font-size: 10px; color: #f87171;
            font-family: 'JetBrains Mono', monospace; font-weight: 700;
        }}
        .timeline-grid {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
        }}
        @media (max-width: 900px) {{
            .timeline-grid {{ grid-template-columns: 1fr; }}
        }}

        /* ── N-gramas asociados ── */
        .ngrams-section {{ margin-bottom: 32px; }}
        .ngrams-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }}
        .ngram-card {{
            background: rgba(15,23,42,0.55); border: 1px solid rgba(148,163,184,0.08);
            border-radius: 12px; padding: 12px 14px;
        }}
        .ngram-kw {{
            font-size: 11px; font-weight: 800; color: #38bdf8;
            font-family: 'JetBrains Mono', monospace; margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        .ngram-pills {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
        .ngram-pill {{
            display: inline-flex; align-items: center; gap: 5px;
            padding: 3px 9px; border-radius: 999px;
            border: 1px solid rgba(148,163,184,0.15);
            background: rgba(148,163,184,0.08);
            color: #cbd5e1; line-height: 1.4;
            font-family: 'DM Sans', sans-serif;
        }}
        .ngram-pill em {{
            font-style: normal; font-size: 0.75em; opacity: 0.65;
            font-family: 'JetBrains Mono', monospace;
        }}
        .ngram-pill.positivo {{
            color: #86efac; border-color: rgba(34,197,94,0.3); background: rgba(34,197,94,0.08);
        }}
        .ngram-pill.negativo {{
            color: #fca5a5; border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.08);
        }}
        .ngram-pill.neutro {{
            color: #cbd5e1; border-color: rgba(148,163,184,0.2); background: rgba(148,163,184,0.08);
        }}
        .ngram-empty {{
            font-size: 11px; color: #64748b; font-style: italic;
        }}
        .ngrams-empty-note {{
            font-size: 11px; color: #64748b; font-style: italic;
            font-weight: 400; margin-left: 6px;
            font-family: 'JetBrains Mono', monospace;
        }}
        .timeline-text {{
            font-size: 12px; color: #b0b8c8; line-height: 1.5;
            overflow: hidden; display: -webkit-box;
            -webkit-line-clamp: 5; -webkit-box-orient: vertical;
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
        .emotion-pill {{
            display: inline-block; padding: 2px 9px; border-radius: 999px;
            font-size: 10px; font-weight: 700; letter-spacing: 0.4px;
            border: 1px solid;
        }}
        .kw-emotion {{
            display: inline-flex; align-items: center; gap: 4px;
            padding: 2px 9px; border-radius: 999px;
            font-size: 11px; font-weight: 700; border: 1px solid;
            margin-left: 8px;
        }}
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
            <div class="subtitle">Sistemas Tributarios COMARB · Tweets por palabra clave</div>
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
            {f'''<div class="stat-card" style="animation-delay:0.3s">
                <div class="stat-label">Emoción Dominante</div>
                <div class="stat-value" style="color:{emo_meta_global["color"]}">{emo_meta_global["emoji"]} {emo_meta_global["label"]}</div>
            </div>''' if has_emotions else ''}
        </div>

        <!-- Chart -->
        <div style="margin-bottom: 32px;">
            <div class="section-title">📊 Distribución de sentimiento por sistema</div>
            <div style="background: rgba(15,23,42,0.5); border-radius: 12px; padding: 20px; border: 1px solid rgba(148,163,184,0.06);">
                <canvas id="stackedChart" height="180"></canvas>
            </div>
        </div>

        <!-- N-gramas asociados por keyword -->
        <div class="ngrams-section">
            <div class="section-title">🏷 Frases asociadas por palabra clave (top 5) {ngrams_empty_html}</div>
            <div class="ngrams-grid">
                {ngrams_html}
            </div>
        </div>

        <!-- Daily evolution chart -->
        <div style="margin-bottom: 32px;">
            <div class="section-title">📈 Evolución diaria de sentimiento (todas las palabras)</div>
            <div style="background: rgba(15,23,42,0.5); border-radius: 12px; padding: 20px; border: 1px solid rgba(148,163,184,0.06);">
                <canvas id="dailyChart" height="100"></canvas>
            </div>
        </div>

        <!-- Recent timeline + Top liked -->
        <div class="timeline-section">
            <div class="timeline-grid">
                <div>
                    <div class="section-title">⏱ Publicaciones más recientes (todas las palabras)</div>
                    {timeline_html}
                </div>
                <div>
                    <div class="section-title">❤️ Top 12 con más likes</div>
                    {top_liked_html}
                </div>
            </div>
        </div>

        <!-- Keyword detail sections -->
        <div class="section-title" style="margin-top: 8px;">📋 Tweets por palabra clave</div>
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
                        counts: {stacked_pos_n_json},
                        backgroundColor: '#22c55e',
                        borderRadius: 4
                    }},
                    {{
                        label: 'Neutro',
                        data: {stacked_neu_json},
                        counts: {stacked_neu_n_json},
                        backgroundColor: '#94a3b8',
                        borderRadius: 0
                    }},
                    {{
                        label: 'Negativo',
                        data: {stacked_neg_json},
                        counts: {stacked_neg_n_json},
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }}
                ]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                layout: {{ padding: {{ left: 20 }} }},
                plugins: {{
                    legend: {{
                        labels: {{ color: '#94a3b8', font: {{ family: "'DM Sans', sans-serif", size: 12 }} }}
                    }},
                    tooltip: {{
                        callbacks: {{
                            title: function(items) {{
                                return (items[0].label || '').replace(/\\s*\\(\\d+\\)\\s*$/, '');
                            }},
                            label: function(ctx) {{
                                const n = ctx.dataset.counts ? ctx.dataset.counts[ctx.dataIndex] : null;
                                const pct = ctx.raw + '%';
                                return ctx.dataset.label + ': ' + (n !== null ? n + ' tweets (' + pct + ')' : pct);
                            }}
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
                        ticks: {{ color: '#cbd5e1', padding: 8, font: {{ family: "'JetBrains Mono', monospace", size: 12, weight: 'bold' }} }},
                        afterFit: function(scale) {{ scale.width = Math.max(scale.width, 120); }},
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
