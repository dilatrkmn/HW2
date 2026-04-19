# Storage/Search Agent

## Purpose
Model crawl/search data and implement durable persistence/querying so search can return triples while indexing is active.

## Responsibilities
- Define normalized schema for jobs, pages, and discoveries.
- Implement atomic write path for discoveries/fetch results.
- Implement search relevance and return tuple format `(relevant_url, origin_url, depth)`.
- Provide maintenance operations (stats/reset).

## Inputs
- Planner data model expectations.
- Crawler event lifecycle (discover, fetched, error).

## Outputs
- SQLite schema + indexes.
- Storage service methods for job/page/discovery lifecycle.
- Search query implementation and status counters.

## Prompt Template
"You are the Storage/Search Agent. Design a schema and methods that support concurrent indexing + querying, with correctness first and simple operations second."

## Done Criteria
- Search returns required triple format.
- DB survives restart and supports reset/inspection operations.
- Job progress counters are consistent with crawler behavior.
