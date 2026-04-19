# Product Requirements Document (PRD)

## Product
Localhost web crawler and search engine with live indexing visibility, built using a multi-agent AI development workflow.

## Goals
1. Crawl from an origin URL to depth `k`, never crawling the same URL twice.
2. Persist crawl artifacts and metadata for search and observability.
3. Search indexed content while crawl jobs are still active.
4. Expose a lightweight UI + API for indexing, searching, and system state.
5. Demonstrate a clear multi-agent build process and decision ownership.

## Non-Goals
- Distributed crawling across multiple machines.
- Full ranking algorithms equivalent to production search engines.
- JS-rendered pages via headless browser.

## Users
- Student/developer evaluating crawler/search architecture.
- Reviewer testing functionality and scalability decisions.

## Functional Requirements
### 1) Index API
- Input: `origin` URL and integer `k`.
- Behavior:
  - BFS-style crawl to max depth `k`.
  - De-duplicate globally by canonicalized URL.
  - Track `(origin, depth)` per discovered URL.
  - Respect back pressure via bounded task queue.
  - Apply per-host request delay for polite crawling.
- Output: `job_id`, accepted status.

### 2) Search API
- Input: query string.
- Output: list of triples `(relevant_url, origin_url, depth)`.
- Relevance definition:
  - Case-insensitive substring match in title or body.
- Must return partial results while indexing is in progress.

### 3) UI/CLI
- Web UI:
  - Start index job.
  - Execute search.
  - View system state: queue depth, back pressure status, jobs, page counts.
- CLI:
  - `index` command.
  - `search` command.
  - `serve` command.

### 4) Persistence
- SQLite local DB.
- Survive restarts for already indexed pages/results.

## Scale & Performance Constraints
- Single-machine, large crawl assumption.
- Worker pool with bounded queue controls memory and throughput.
- Request payload cap (1MB per page) to bound storage/cost.

## Observability
- Runtime state endpoint includes:
  - worker count
  - queue depth/capacity
  - back pressure status
  - seen URL count
- Job state includes discovered/fetched counters and status.

## Failure Handling
- Non-HTML content skipped with error status.
- Per-page fetch errors persisted without stopping job.
- Job completes when discovered == fetched.

## Stretch: Search While Indexing (Design Notes)
- Supported by immediate upsert of fetched page content and discovery metadata.
- Search reads committed rows; no global lock beyond SQLite transaction scope.
- For higher scale: use append-only index segments + periodic compaction.
