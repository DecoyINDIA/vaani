# KB search deployment

Vaani uses OpenRouter embeddings and MongoDB Atlas hybrid search. The Atlas cluster
must run MongoDB 8.0 or later because the query uses `$rankFusion`.

Choose an embedding model, set `LLM_MODEL_EMBEDDING`, and set
`KB_EMBEDDING_DIMENSIONS` to that model's returned vector size. The vector index and
application setting must match exactly. With the default index names and 1536
dimensions, create these indexes on `vaani.kb_entries`:

```javascript
db.kb_entries.createSearchIndex("kb_text", {
  mappings: {
    dynamic: false,
    fields: {
      tenant_id: { type: "token" },
      key: { type: "string" },
      question: { type: "string" },
      answer: { type: "string" }
    }
  }
})

db.kb_entries.createSearchIndex("kb_vector", "vectorSearch", {
  fields: [
    {
      type: "vector",
      path: "embedding",
      numDimensions: 1536,
      similarity: "cosine"
    },
    { type: "filter", path: "tenant_id" }
  ]
})
```

If different names are used, set `KB_TEXT_INDEX` and `KB_VECTOR_INDEX`. Wait until
both indexes report `READY` before a retrieval drill. Do not create or update Atlas
search indexes from application startup.

Inventory existing entries without calling the embedding provider or changing data:

```powershell
uv run python -m ops.reembed_kb --limit 100
```

After the embedding model, dimensions, and Atlas vector index are approved, apply one
bounded batch at a time. Rerun until `limit_reached` is false:

```powershell
uv run python -m ops.reembed_kb --limit 100 --apply --confirm REEMBED
```

Use `--tenant clinic_slug` to restrict a rehearsal. Changing the embedding model or
dimensions makes prior rows eligible again, so the same command is the resumable model
migration path.

The credentialed retrieval gate is intentionally separate from normal CI. Configure
the `credentialed-retrieval` workflow with an isolated database URI whose database name
contains `eval`, the OpenRouter secret, and the four KB model/index variables. That
workflow embeds ten synthetic entries, runs the versioned 50-query multilingual corpus,
requires at least 90% top-3 hits, deletes the synthetic tenant in `finally`, and retains
only a summary artifact with no questions or answers.

Every KB write embeds `question + answer` before MongoDB is changed. If embedding is
unavailable, the API returns 503 and preserves the prior entry. If Atlas search is
unavailable at read time, only an exact tenant-scoped structured key such as
`faq_hours` is returned; free-text FAQ misses hand off to clinic staff instead of
answering from an unranked regex result.
