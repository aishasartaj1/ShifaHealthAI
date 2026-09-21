# Demo Script

A 3–5 minute candidate demo, once the MVP (see [BACKLOG.md](BACKLOG.md#mvp-definition)) is live:

1. Open the live Women's Health Assistant, ask: *"Can PCOS cause irregular periods?"*
2. Show the grounded answer, source cards, and related topics.
3. Open **Agent Observability** — show semantic + lexical candidates, governance rejections, tool calls, latency.
4. Open **Governance** — show approved vs. non-eligible knowledge and data-quality metrics.
5. Open **Analytics** — show Pub/Sub/Dataflow-generated interaction metrics.
6. Briefly show the BigQuery semantic model; explain raw → curated → semantic → AI-ready data products.
7. Show the Terraform DEV modules and the GitHub Actions workflow.
8. Close with the architecture diagram; explain how Stage/Prod could reuse the same Terraform modules without
   being deployed for this portfolio demo.

## Response presentation reference

```
Question: Can PCOS cause irregular periods?

[Grounded educational answer]

Sources
1. Source / article title — review/source metadata
2. Source / article title

Related topics
[Understanding PCOS] [Menstrual cycles] [Hormonal health]

Educational information only; not a substitute for professional medical care.
```

The consumer UI never exposes raw chain-of-thought. The admin console may show operational traces (tools called,
retrieval candidates, filtered counts, sources used, latency, errors) — metadata only, never sensitive content.

## Resume positioning (use only after implementation is verified)

Suggested title: *ShifaHealth AI — Governed Agentic Women's Health Knowledge Platform*

- Engineered a GCP data platform transforming structured metadata and unstructured women's-health knowledge into
  governed BigQuery semantic data products using Cloud Storage, Dataflow, and Pub/Sub.
- Built a Vertex AI Gemini agent with hybrid semantic/lexical RAG, BigQuery-backed governance checks, and
  controlled tool calling to generate source-grounded educational responses through a FastAPI/React application.
- Provisioned the DEV environment with Terraform and implemented GitHub Actions CI/CD for testing, infrastructure
  validation, container builds, Cloud Run deployment, and smoke testing.

Do not claim any technology, scale, accuracy, compliance, or deployment behavior until it is actually implemented
and verified end-to-end.
