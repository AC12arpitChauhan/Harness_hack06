"""PR Health Analytics backend.

Hexagonal architecture:
  - Pure core  : app.domain, app.analyzers, app.scoring  (stdlib only)
  - Edges      : app.providers, app.llm, app.persistence, app.api
  - Orchestrate: app.services

Dependencies point INWARD only. The core never imports an edge.
"""
