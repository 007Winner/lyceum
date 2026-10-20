# Tokenomics summary

Rows measured: **3**. Source: `analysis/token_usage.csv`.

The logger records provider-reported input, cached input, cache-write, output, total tokens, duration, model, role, and an optional estimated cost. It never records prompts, responses, or API keys.

| Agent role | Calls | Avg input | Avg cached input | Avg output | Avg total | Avg duration (ms) |
|---|---:|---:|---:|---:|---:|---:|
| evaluator | 1 | 311.0 | 0.0 | 49.0 | 360.0 | 1446.1 |
| philosopher | 2 | 1099.5 | 0.0 | 53.5 | 1153.0 | 1539.7 |

## Rates and cost

No verified GPT-6 Luna rates were found in the repository or provider response metadata. The optional environment variables `LYCEUM_INPUT_RATE_PER_MILLION`, `LYCEUM_CACHED_INPUT_RATE_PER_MILLION`, and `LYCEUM_OUTPUT_RATE_PER_MILLION` remain unset, so estimated cost is blank rather than invented.

Once verified rates are supplied, cost is calculated as `(uncached input × input rate + cached input × cached rate + cache-write input × input rate + output × output rate) / 1,000,000`. Complete-playthrough and 1/100/10,000-user projections are extrapolations from measured rows and an explicitly chosen number of monthly playthroughs; they are not observed usage.

## Limitations

Existing acceptance JSON contains completion-token measurements but not provider input/cache metadata. New CSV rows are required for measured input and cache analysis. Logging is best effort and cannot interrupt gameplay.
