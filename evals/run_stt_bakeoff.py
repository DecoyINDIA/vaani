"""STT bake-off evaluation script (Loop L14 / ADR-05).

Calculates Word Error Rate (WER), latency, and per-minute cost for
Sarvam, Deepgram, and Google STT providers on the voice corpus dataset.
"""

from __future__ import annotations

import asyncio
import csv
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure Indic scripts print correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.channels.voice.stt import transcribe_audio


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate the Word Error Rate (WER) using Levenshtein distance on words."""
    # Normalize and tokenize
    ref_words = re.findall(r"[\u0900-\u097f\u0b00-\u0b7f\w']+", reference.lower(), re.UNICODE)
    hyp_words = re.findall(r"[\u0900-\u097f\u0b00-\u0b7f\w']+", hypothesis.lower(), re.UNICODE)
    
    if not ref_words:
        return 1.0 if hyp_words else 0.0
        
    n = len(ref_words)
    m = len(hyp_words)
    
    # Initialize DP matrix
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
        
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                substitution = dp[i - 1][j - 1] + 1
                deletion = dp[i - 1][j] + 1
                insertion = dp[i][j - 1] + 1
                dp[i][j] = min(substitution, deletion, insertion)
                
    return float(dp[n][m]) / n


async def run_bakeoff() -> None:
    csv_path = Path("evals/voice_corpus/metadata.csv")
    if not csv_path.exists():
        print(f"[FAIL] Voice corpus metadata file not found at {csv_path}")
        sys.exit(1)

    # Load corpus records
    records: List[Dict[str, str]] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    print(f"\n[STT Bake-off] Loaded {len(records)} utterances from corpus metadata.")
    print("=" * 90)

    providers = ["sarvam", "deepgram", "google"]
    stats: Dict[str, Dict[str, Any]] = {
        p: {
            "total_wer": 0.0,
            "total_latency_ms": 0.0,
            "total_cost_inr": 0.0,
            "count": 0,
            "lang_wer": {"hi": 0.0, "hi-Latn": 0.0, "or": 0.0},
            "lang_count": {"hi": 0, "hi-Latn": 0, "or": 0}
        }
        for p in providers
    }

    # Run evaluations sequentially
    for idx, row in enumerate(records):
        file_path = row["file_path"]
        ref_text = row["transcript"]
        lang = row["language"]
        
        for prov in providers:
            # Override provider settings on evaluation run
            res = await transcribe_audio(file_path, lang=lang, provider=prov)
            hyp_text = res["text"]
            latency = res["latency_ms"]
            cost = res["cost_inr"]
            
            # Compute WER
            wer = calculate_wer(ref_text, hyp_text)
            
            # Record statistics
            stats[prov]["total_wer"] += wer
            stats[prov]["total_latency_ms"] += latency
            stats[prov]["total_cost_inr"] += cost
            stats[prov]["count"] += 1
            
            if lang in stats[prov]["lang_wer"]:
                stats[prov]["lang_wer"][lang] += wer
                stats[prov]["lang_count"][lang] += 1

    # Print summary comparative table
    print("\n" + "=" * 32 + " STT BAKE-OFF COMPARATIVE RESULTS " + "=" * 32)
    print(f"{'Provider':<15} | {'Avg WER (All)':<15} | {'WER (hi)':<10} | {'WER (hi-Latn)':<14} | {'WER (or)':<10} | {'Avg Latency':<12} | {'Est. Cost/min':<15}")
    print("-" * 115)
    
    winning_prov = ""
    min_overall_metric = float("inf")
    
    for prov in providers:
        p_stats = stats[prov]
        count = p_stats["count"]
        avg_wer = p_stats["total_wer"] / count if count > 0 else 0.0
        avg_lat = p_stats["total_latency_ms"] / count if count > 0 else 0.0
        
        # Calculate per-language WERs
        w_hi = p_stats["lang_wer"]["hi"] / p_stats["lang_count"]["hi"] if p_stats["lang_count"]["hi"] > 0 else 0.0
        w_hl = p_stats["lang_wer"]["hi-Latn"] / p_stats["lang_count"]["hi-Latn"] if p_stats["lang_count"]["hi-Latn"] > 0 else 0.0
        w_or = p_stats["lang_wer"]["or"] / p_stats["lang_count"]["or"] if p_stats["lang_count"]["or"] > 0 else 0.0
        
        # Standard Exotel telephony overage pricing comparison
        # Sarvam: ~₹0.08/min, Deepgram: ~₹0.15/min, Google: ~₹0.20/min
        cost_per_min = 0.08 if prov == "sarvam" else (0.15 if prov == "deepgram" else 0.20)
        
        print(f"{prov:<15} | {avg_wer:<15.4f} | {w_hi:<10.4f} | {w_hl:<14.4f} | {w_or:<10.4f} | {avg_lat:<9.1f}ms | ₹{cost_per_min:<13.3f}")

        # Decision score: combination of lower WER and cost
        decision_metric = avg_wer + (cost_per_min * 0.1)
        if decision_metric < min_overall_metric:
            min_overall_metric = decision_metric
            winning_prov = prov

    print("-" * 115)
    print(f"VERDICT (ADR-05): {winning_prov.upper()} wins the bake-off based on lower overall WER and per-minute cost.")
    print("=" * 98)


if __name__ == "__main__":
    asyncio.run(run_bakeoff())
