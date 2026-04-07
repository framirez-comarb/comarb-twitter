#!/usr/bin/env python3
"""
Enriquece un JSON de tweets con análisis de emociones (pysentimiento).

Agrega a cada post:
    emotion          → str  (joy, anger, sadness, fear, surprise, disgust, others)
    emotion_probas   → dict  con todas las probabilidades

Agrega a cada keyword:
    emotion_summary  → dict  conteo de emociones dominantes
    emotion_dominant → str   emoción mayoritaria (excluyendo "others")

NO modifica `sentiment` ni `sentiment_score`. Es 100% un *feature* nuevo.

Uso:
    python enrich_emotions.py
    python enrich_emotions.py --in tweets_data_v2.json --out tweets_data_v2_emo.json

Importable:
    from enrich_emotions import enrich_in_memory
    enrich_in_memory(data_dict)   # modifica in-place
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# Prioridad de desempate (menor índice gana): negativas pesan más en este corpus
_PRIORITY = ["anger", "disgust", "sadness", "fear", "surprise", "joy"]
_PRIO_IDX = {e: i for i, e in enumerate(_PRIORITY)}
_MIN_COUNT = 3        # mínimo de tweets para reportar emoción dominante
_MIN_RATIO = 0.15     # o al menos 15% de los tweets de la keyword


def enrich_in_memory(data: dict) -> dict:
    """
    Enriquece in-place una estructura `data` (formato tweets_data.json)
    agregando análisis de emociones a cada post y un resumen por keyword.

    Devuelve el mismo dict por conveniencia.
    """
    from pysentimiento import create_analyzer
    analyzer = create_analyzer(task="emotion", lang="es")

    texts = []
    refs = []
    for kw in data["keywords"]:
        for post in kw.get("posts", []):
            texts.append(post.get("text", "") or "")
            refs.append(post)

    print(f"⏳ Analizando emociones de {len(texts)} tweets...")
    results = analyzer.predict(texts) if texts else []

    for post, r in zip(refs, results):
        post["emotion"] = r.output
        post["emotion_probas"] = {k: round(float(v), 3) for k, v in r.probas.items()}

    for kw in data["keywords"]:
        c = Counter()
        for post in kw.get("posts", []):
            c[post.get("emotion", "others")] += 1
        kw["emotion_summary"] = dict(c)

        total_kw = sum(c.values())
        cand = [
            (e, n) for e, n in c.items()
            if e != "others" and (n >= _MIN_COUNT or (total_kw and n / total_kw >= _MIN_RATIO))
        ]
        if cand:
            cand.sort(key=lambda en: (-en[1], _PRIO_IDX.get(en[0], 99)))
            kw["emotion_dominant"] = cand[0][0]
        else:
            kw["emotion_dominant"] = "others"

    total = Counter()
    for kw in data["keywords"]:
        for post in kw.get("posts", []):
            total[post.get("emotion", "others")] += 1
    print("📊 Distribución global de emociones:")
    for e, n in sorted(total.items(), key=lambda x: -x[1]):
        print(f"   {e:10} {n:>4}")

    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", default="tweets_data_v2.json")
    p.add_argument("--out", default="tweets_data_v2_emo.json")
    args = p.parse_args()

    if not os.path.exists(args.inp):
        raise SystemExit(f"❌ No existe: {args.inp}")

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("⏳ Cargando modelo de emociones (pysentimiento)...")
    enrich_in_memory(data)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Guardado: {args.out}")
    print("\nAhora podés correr:")
    print(f"   python render_from_cache.py --data {args.out}")


if __name__ == "__main__":
    main()
