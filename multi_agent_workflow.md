# Multi-Agent Workflow

## Agent Set
1. **Planner Agent**
   - Responsibilities: convert requirements into architecture + milestones.
   - Prompt focus: scale assumptions, back pressure, search-while-indexing.
2. **Crawler Agent**
   - Responsibilities: URL normalization, crawl queue, worker logic, parsing, de-dup.
   - Prompt focus: language-native crawling without heavy frameworks.
3. **Storage/Search Agent**
   - Responsibilities: schema design, write path, query path, consistency.
   - Prompt focus: `(relevant_url, origin_url, depth)` retrieval and live reads.
4. **Interface Agent**
   - Responsibilities: API contracts, CLI, simple web UI, status endpoints.
   - Prompt focus: usability and observability.
5. **Reviewer Agent**
   - Responsibilities: threat-model-like review (errors, bottlenecks, edge cases).
   - Prompt focus: scalability and correctness checks.

## Collaboration Process
1. Planner Agent drafted PRD and module boundaries.
2. Crawler Agent proposed worker-pool + bounded queue + per-host throttling.
3. Storage/Search Agent proposed normalized SQLite tables (`crawl_jobs`, `pages`, `discoveries`) and join-based search.
4. Interface Agent implemented API + CLI + browser UI for indexing, searching, and state.
5. Reviewer Agent evaluated race conditions, completion logic, and limits (payload caps, link caps, queue pressure).
6. Human orchestrator accepted/rejected proposals and performed final integration.

## Interaction Protocol
- Shared contract docs first (input/output schemas).
- Code proposed in small, reviewable chunks.
- Agents exchanged artifacts via file-level interfaces rather than direct runtime composition.
- Final decision authority remained with the human orchestrator.

## Why this satisfies the requirement
The delivered runtime is a standard single-process Python app, but the development process explicitly separated concerns among multiple specialized agents and documented their prompts, responsibilities, and review loops.
