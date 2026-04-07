#!/usr/bin/env python3
"""
Compara el clasificador viejo (rule-based + lexicon, ya guardado en
`tweets_data.json`) contra el nuevo (analyze_sentiment_v2 / pysentimiento)
sobre los tweets cacheados. SIN tocar Twitter.

Salidas:
  • Resumen en consola:
      - Distribución vieja vs nueva
      - Matriz de confusión vieja → nueva
      - Top N tweets donde más cambió la decisión
      - Tweets POS-vieja → NEG-nueva (los falsos positivos catárticos)
  • CSV con todas las decisiones lado a lado: comparison.csv
  • JSON con clasificación nueva por tweet: tweets_data_v2.json

Uso:
    python compare_classifiers.py
    python compare_classifiers.py --data tweets_data.json --top 25
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

# UTF-8 stdout (Windows console)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from analyze_sentiment_v2 import classify_batch, classify

DEFAULT_DATA = "tweets_data.json"
LABELS = ["positivo", "neutro", "negativo"]


def load_posts(path: str):
    """Yield (keyword, post) tuples conservando orden."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for kw_block in data["keywords"]:
        for post in kw_block.get("posts", []):
            yield kw_block["keyword"], post
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--top", type=int, default=15,
                        help="Cantidad de ejemplos a mostrar por categoría de cambio")
    parser.add_argument("--csv", default="comparison.csv")
    parser.add_argument("--out-json", default="tweets_data_v2.json")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        raise SystemExit(f"❌ No existe: {args.data}")

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ── Recolectar todos los posts manteniendo referencias ──
    all_entries = []  # (keyword, post_ref)
    for kw_block in data["keywords"]:
        for post in kw_block.get("posts", []):
            all_entries.append((kw_block["keyword"], post))

    n = len(all_entries)
    print(f"📊 Total tweets a clasificar: {n}\n")
    print("⏳ Cargando RoBERTuito y clasificando (puede tardar la 1ra vez)...\n")

    # ── Clasificar en batch para velocidad ──
    # Aplicamos primero la regla de cuenta institucional (no llamar al modelo).
    # Para el resto, usamos el batch del modelo.
    new_results = [None] * n
    batch_indices = []
    batch_texts = []
    for i, (_, post) in enumerate(all_entries):
        username = (post.get("username") or "").lstrip("@").lower()
        from analyze_sentiment_v2 import INSTITUTIONAL_USERNAMES
        if username in INSTITUTIONAL_USERNAMES:
            new_results[i] = {
                "sentiment": "neutro",
                "score": 0.0,
                "confidence": 1.0,
                "probas": {"positivo": 0.0, "neutro": 1.0, "negativo": 0.0},
                "rule": "institutional_account",
            }
        else:
            batch_indices.append(i)
            batch_texts.append(post.get("text", ""))

    batch_out = classify_batch(batch_texts) if batch_texts else []
    for idx, res in zip(batch_indices, batch_out):
        new_results[idx] = res

    # ── Estadísticas ──
    old_dist = Counter()
    new_dist = Counter()
    confusion = defaultdict(int)  # (old, new) → count
    diffs = []  # (old, new, conf, kw, username, text, score_old, score_new)

    for (kw, post), new in zip(all_entries, new_results):
        old = post.get("sentiment", "neutro")
        old_dist[old] += 1
        new_dist[new["sentiment"]] += 1
        confusion[(old, new["sentiment"])] += 1
        if old != new["sentiment"]:
            diffs.append({
                "keyword": kw,
                "username": post.get("username", ""),
                "text": post.get("text", ""),
                "old_sentiment": old,
                "old_score": post.get("sentiment_score", 0),
                "new_sentiment": new["sentiment"],
                "new_score": new["score"],
                "new_confidence": new["confidence"],
                "rule": new["rule"],
            })

    # ── Imprimir resumen ──
    print("═" * 70)
    print("  DISTRIBUCIÓN")
    print("═" * 70)
    print(f"  {'Sentimiento':<12} {'Viejo':>10} {'Nuevo':>10}   Δ")
    for lbl in LABELS:
        o, nn = old_dist[lbl], new_dist[lbl]
        delta = nn - o
        sign = "+" if delta >= 0 else ""
        print(f"  {lbl:<12} {o:>10} {nn:>10}   {sign}{delta}")
    print(f"  {'TOTAL':<12} {sum(old_dist.values()):>10} {sum(new_dist.values()):>10}")

    print("\n" + "═" * 70)
    print("  MATRIZ DE CONFUSIÓN  (filas = viejo, columnas = nuevo)")
    print("═" * 70)
    header = "  " + " " * 12 + "".join(f"{c:>10}" for c in LABELS) + "    total"
    print(header)
    for r in LABELS:
        row = f"  {r:<12}"
        total = 0
        for c in LABELS:
            v = confusion[(r, c)]
            total += v
            row += f"{v:>10}"
        row += f"    {total:>5}"
        print(row)

    n_changed = len(diffs)
    print(f"\n  ✏️  Tweets que cambiaron de etiqueta: {n_changed} / {n}  ({100*n_changed/n:.1f}%)")

    # ── Falsos positivos catárticos: POS viejo → NEG nuevo ──
    pos_to_neg = [d for d in diffs if d["old_sentiment"] == "positivo" and d["new_sentiment"] == "negativo"]
    pos_to_neg.sort(key=lambda d: d["new_confidence"], reverse=True)
    if pos_to_neg:
        print("\n" + "═" * 70)
        print(f"  🔥 POS → NEG  ({len(pos_to_neg)} casos — falsos positivos del viejo)")
        print("═" * 70)
        for d in pos_to_neg[:args.top]:
            txt = d["text"].replace("\n", " ")[:130]
            print(f"  [conf {d['new_confidence']:.2f}] @{d['username']}  ({d['keyword']})")
            print(f"    {txt}")

    # ── Neutros del viejo que ahora son NEG (sarcasmo / quejas no detectadas) ──
    neu_to_neg = [d for d in diffs if d["old_sentiment"] == "neutro" and d["new_sentiment"] == "negativo"]
    neu_to_neg.sort(key=lambda d: d["new_confidence"], reverse=True)
    if neu_to_neg:
        print("\n" + "═" * 70)
        print(f"  😠 NEU → NEG  ({len(neu_to_neg)} casos — quejas/sarcasmo que el viejo no captó)")
        print("═" * 70)
        for d in neu_to_neg[:args.top]:
            txt = d["text"].replace("\n", " ")[:130]
            print(f"  [conf {d['new_confidence']:.2f}] @{d['username']}  ({d['keyword']})")
            print(f"    {txt}")

    # ── Neutros del viejo que ahora son POS ──
    neu_to_pos = [d for d in diffs if d["old_sentiment"] == "neutro" and d["new_sentiment"] == "positivo"]
    neu_to_pos.sort(key=lambda d: d["new_confidence"], reverse=True)
    if neu_to_pos:
        print("\n" + "═" * 70)
        print(f"  🙂 NEU → POS  ({len(neu_to_pos)} casos)")
        print("═" * 70)
        for d in neu_to_pos[:args.top]:
            txt = d["text"].replace("\n", " ")[:130]
            print(f"  [conf {d['new_confidence']:.2f}] @{d['username']}  ({d['keyword']})")
            print(f"    {txt}")

    # ── NEG viejo → POS nuevo (potenciales falsos negativos del viejo, o errores del v2) ──
    neg_to_pos = [d for d in diffs if d["old_sentiment"] == "negativo" and d["new_sentiment"] == "positivo"]
    if neg_to_pos:
        print("\n" + "═" * 70)
        print(f"  ⚠️  NEG → POS  ({len(neg_to_pos)} casos — REVISAR, podrían ser errores)")
        print("═" * 70)
        for d in neg_to_pos[:args.top]:
            txt = d["text"].replace("\n", " ")[:130]
            print(f"  [conf {d['new_confidence']:.2f}] @{d['username']}  ({d['keyword']})")
            print(f"    {txt}")

    # ── CSV completo ──
    with open(args.csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["keyword", "username", "old_sentiment", "old_score",
                    "new_sentiment", "new_score", "new_confidence", "rule",
                    "changed", "text"])
        for (kw, post), new in zip(all_entries, new_results):
            old = post.get("sentiment", "neutro")
            w.writerow([
                kw, post.get("username", ""),
                old, post.get("sentiment_score", 0),
                new["sentiment"], new["score"], new["confidence"], new["rule"] or "",
                "1" if old != new["sentiment"] else "0",
                post.get("text", "").replace("\n", " "),
            ])

    # ── JSON con la nueva clasificación aplicada al dataset entero ──
    new_data = json.loads(json.dumps(data))  # deep copy
    idx = 0
    for kw_block in new_data["keywords"]:
        new_summary = {"positivo": 0, "neutro": 0, "negativo": 0}
        for post in kw_block.get("posts", []):
            res = new_results[idx]
            post["sentiment"] = res["sentiment"]
            post["sentiment_score"] = res["score"]
            post["sentiment_confidence"] = res["confidence"]
            post["sentiment_rule"] = res["rule"]
            new_summary[res["sentiment"]] += 1
            idx += 1
        kw_block["sentiment_summary"] = new_summary

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print("\n" + "═" * 70)
    print(f"  📄 CSV completo:        {args.csv}")
    print(f"  💾 JSON re-clasificado: {args.out_json}")
    print("═" * 70)
    print("\n  Sugerencia: para ver el HTML con las etiquetas nuevas, corré:")
    print(f"     python render_from_cache.py --data {args.out_json}")


if __name__ == "__main__":
    main()
