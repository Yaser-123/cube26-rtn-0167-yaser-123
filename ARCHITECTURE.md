# Architecture: Returns Manager

## Overview

A FastAPI service with a browser UI. One vision-model call per returned unit produces three independent check verdicts. Deterministic code turns those into a disposition, and the result is written as an Evidence Record in the official contract shape.

```text
Browser (drag/drop or camera)
  └─ downscale to 1024px, send as data URL ─┐
                                            ▼
FastAPI  src/main.py
  ├─ tenant check: x-org-id == organization_id
  ├─ ReturnsAgent.process()                 src/agent.py
  │    ├─ decode + resize images (≤3, 1024px)
  │    ├─ disk cache lookup (hash of org, model, effort, prompt version, SKU, parts, image bytes)
  │    ├─ Claude messages API: images + SKU + parts → strict JSON schema
  │    ├─ fail open on any error → all UNCERTAIN, pending_review
  │    └─ decide_disposition() → outcome
  └─ records_db[org_id][record_id]  (in-memory, tenant-partitioned)
```

## Key decisions and trade-offs

**One batched call, three verdicts.** Identity, completeness and condition all come from the same photos, so one call covers them. Three separate calls would triple the image tokens, which dominate the cost. The trade-off is that one bad response affects all three checks. The strict JSON schema (`output_config.format`) removes parsing failures, and any API failure fails open.

**Per-check UNCERTAIN.** The model returns PASS/FAIL/UNCERTAIN for each check rather than one "needs more images" flag. A plain shipping carton can be identity-UNCERTAIN, and a clearly visible bottle with exposed threads can be completeness-FAIL without asking for more photos. Any UNCERTAIN routes to `pending_review`.

**Identity against the seller catalogue.** The model gets the SKU's catalogue description (`src/catalog.py`), not just the code, so an unbranded bottle can pass while a label reading "1L" fails a 750 ml SKU. An SKU with no catalogue entry is never allowed to PASS identity; code downgrades it to UNCERTAIN.

**Eval labelling tool.** `/label` lets two people build and label the held-out set. Each labeller's API view only contains their own columns, so labels stay independent. Images are served only from the fixture folders, never from arbitrary paths in the CSV.

**Code decides the disposition.** The model only grades. `decide_disposition()` is a small, tested table. That keeps outcomes consistent and auditable, and it means the policy can change without re-prompting. A wrong item (identity FAIL) goes to review, never to `dispose`, because the item might belong to someone else and is a Recovery claim.

**Model choice.** The default is `claude-opus-5-5` at effort `low`: the most capable current model, with a low thinking budget, since this is a short grading task. It's configurable through `RTN_MODEL` / `RTN_EFFORT`. The eval report should compare against `claude-sonnet-5-5` before settling on a production default. A server-side refusal fallback (`fallbacks: "default"`) re-runs a declined request on another model instead of losing the case.

**Cost.** Image tokens dominate. The levers, in order of impact:
1. The 1024px cap (about half the tokens of full resolution)
2. At most 3 images
3. One call per unit
4. The content-hash cache, so re-submissions and eval re-runs cost $0
5. Low effort
6. No call at all without a readable image

Each call's token usage, USD cost and latency are recorded and aggregated by `eval.py`.

**Tenancy.** Records live in `records_db[org_id]`, and every read path goes through the caller's partition. Guessing another tenant's `record_id` returns 404, the same as a missing record. Uploaded images are not persisted or served. The record stores `upload:sha256:<prefix>` as a reference, so there is no shared image path to guess. The cache key includes `organization_id`, so cached results are never shared across tenants. `x-org-id` stands in for real authentication in this demo; production would derive the tenant from an auth token.

**Evidence record.** It has every field in the official contract. `model_version` on each check is the actual model ID. `content_hash` is SHA-256 over the canonical JSON of the record minus the hash. It detects changes but isn't signed or anchored, so it doesn't make records tamper-proof. Overrides append history and recompute the hash, and the agent's original checks are preserved.

## Known limitations

- The store is in-memory, so records vanish on restart. Production would use Postgres with row-level security per org.
- Images arrive as base64 JSON. Production would use multipart or presigned object-store uploads with per-tenant buckets.
- The condition definitions are paraphrased from Amazon's Condition Guidelines and should be re-checked against the live page per category.
- Evaluation numbers are pending the 50-unit two-labeller set (see README).

## Dependencies
Python 3.10+, FastAPI, Pydantic, Anthropic Python SDK, Pillow, python-dotenv.

## Security
No secrets in the repository: `.env` is git-ignored, and `.env.example` holds placeholders. Model output shown in the UI is HTML-escaped.
