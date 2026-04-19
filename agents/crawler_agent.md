# Crawler Agent

## Purpose
Implement crawling mechanics: URL normalization, frontier scheduling, de-duplication, fetch/parsing, throttling, and back-pressure behavior.

## Responsibilities
- Design worker-pool traversal up to depth `k`.
- Guarantee no duplicate crawling of the same canonical URL.
- Enforce controlled load via queue limits/rate delays.
- Persist fetch success/error outcomes through storage interfaces.

## Inputs
- Crawl contract from Planner Agent.
- Storage API contract (upsert page, record discovery, mark fetch/error).

## Outputs
- Crawler runtime (`CrawlerEngine`, task model, parser).
- Runtime observability fields (queue depth, back-pressure, seen URLs, drops).
- Failure handling for non-HTML, timeout, parse issues.

## Prompt Template
"You are the Crawler Agent. Build a robust, language-native crawler core with bounded memory growth and deterministic behavior under queue pressure. Explain queue policy and duplicate guarantees."

## Done Criteria
- Depth-limited crawl works and avoids duplicate fetches.
- Back-pressure behavior is explicit and observable.
- Engine can run concurrently with live search reads.
