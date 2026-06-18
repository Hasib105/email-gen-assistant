# Evaluation Summary

| Metric | OpenAI gpt-oss 120b + Advanced | MiniMax M3 + Naive | Delta |
|---|---|---|---|
| Fact Recall | 93.33% | 80.00% | +13.33% |
| Tone Alignment | 39.58% | 39.11% | +0.47% |
| Clarity/Conciseness | 99.23% | 89.25% | +9.98% |
| **Overall** | **77.38%** | **69.45%** | **+7.93%** |

**Best performer:** OpenAI gpt-oss 120b + Advanced

**Biggest failure mode of MiniMax M3 + Naive:** Fact Recall — +13.33% difference.

**Worst scenarios for MiniMax M3 + Naive:**
- scenario_09: 1.92
- scenario_03: 1.95
- scenario_04: 2.06

**Production recommendation:** OpenAI gpt-oss 120b + Advanced. Scores +7.93% overall.
