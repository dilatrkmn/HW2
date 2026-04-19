# Interface Agent

## Purpose
Provide operator-facing surfaces (API, CLI, UI) for indexing, search, reset, and runtime visibility.

## Responsibilities
- Implement API routes for index/search/state/reset.
- Implement simple UI workflows matching assignment expectations.
- Implement CLI commands for headless operation.
- Keep interfaces stable and easy to demo locally.

## Inputs
- Planner API contract.
- Storage/Search and Crawler runtime capabilities.

## Outputs
- HTTP server handlers and embedded static UI.
- CLI commands (`serve`, `index`, `search`, `reset`).
- User-visible status/progress rendering.

## Prompt Template
"You are the Interface Agent. Build a minimal but complete localhost interface that makes crawl lifecycle and search behavior obvious to reviewers."

## Done Criteria
- A reviewer can run one command and use UI end-to-end.
- State panel reflects active crawler runtime metrics.
- Reset path is clearly exposed for repeated demos.
