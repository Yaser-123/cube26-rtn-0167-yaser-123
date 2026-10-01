# Cube Buildathon · 04 · Returns Manager (Submission)

Round 2 individual build of the **Returns Manager**: step 4 of 5 in the chain. Someone opens a returned parcel, photographs it, and the agent answers the four questions from the problem statement:

1. **Identity**: is this the SKU/ASIN that was ordered? Checked against the seller catalogue description in `src/catalog.py`, so a label reading "1L" fails a 750 ml SKU.
2. **Completeness**: are all expected parts present?
3. **Condition**: graded on Amazon's published condition scale (no invented scale)
4. **Disposition**: `restock`, `refurbish`, `liquidate`, `dispose` or `pending_review`

The output is an **Evidence Record** in the official contract shape, for the Recovery Manager to consume.

## How it works

```text
Photos (≤3) + ordered SKU + parts list
        │
        ▼
  One vision call to Claude (claude-opus-5-5), structured JSON output
  → identity / completeness / condition, each PASS | FAIL | UNCERTAIN + confidence + detail
        │
        ▼
  Deterministic disposition policy in code (src/agent.py: decide_disposition)
        │
        ▼
  Evidence Record: record_id, schema_version, organization_id, client_id, agent,
  subject, captured_at, operator_label, images, checks[], outcome, overrides[],
  status, content_hash
```

The model grades and the code decides. The disposition is never left to the model's discretion.

### Disposition policy

| Situation | Disposition |
|---|---|
| Any check UNCERTAIN | `pending_review` |
| Identity FAIL (wrong item came back) | `pending_review`: a human and Recovery handle it, never auto-dispose |
| Condition `Unacceptable` | `dispose` |
| Part missing, item otherwise sound | `refurbish` (`liquidate` if `Used - Acceptable`) |
| `New` / `Used - Like New`, complete | `restock` |
| `Used - Very Good` / `Used - Good`, complete | `refurbish` |
| `Used - Acceptable`, complete | `liquidate` |

This is **our** policy, derived from the problem statement and the sample data. It isn't an Amazon rule, and the sample data isn't consistent with it (see Findings).

## Engineering rules, and how each is met

| Rule | Implementation |
|---|---|
| Tenancy isolation | The `x-org-id` header must match the body's `organization_id` (403 otherwise). Records are stored in per-tenant partitions, so another org's `record_id` returns the same 404 as a nonexistent one. Uploaded images are never stored or served by a guessable path; the record keeps only a content-hash reference. Covered by tests. |
| Batch model calls | All three checks come from **one** model call per unit. `/process-batch` runs units concurrently. |
| Fail open | Model error, timeout, refusal or unreadable images → the record is still created and stored, all checks `UNCERTAIN`, outcome `pending_review`. Covered by tests. |
| Uncertain is a verdict | Each check can be UNCERTAIN on its own (e.g. a plain shipping carton makes identity UNCERTAIN). UNCERTAIN always routes to review. |
| Authoritative rules | Condition names and definitions follow Amazon Seller Central's Condition Guidelines. The disposition mapping is our documented policy, not presented as Amazon's. |
| Overrides are data | `POST /{record_id}/override` appends `{original_verdict, revised_verdict, reason, operator, timestamp}`. The agent's checks are left untouched, the status becomes `overridden`, and the hash is recomputed. |

`content_hash` is SHA-256 over the record's canonical JSON. It lets a consumer detect that a record changed. It is **not** signed or anchored, so we don't claim the records are tamper-proof.

## Cost controls

Measured per-unit costs belong in the eval report. This is the design:

- **One call per unit** for all three checks, returning a strict JSON schema (no retries from bad parsing).
- **Images capped at 3 and resized to a 1024px long edge**, in the browser and again on the server. That's about 1.0–1.4k input tokens per image.
- **Effort `low`** by default (`RTN_EFFORT`), which keeps output tokens small.
- **Disk cache**: identical images + SKU + parts + model skip the model entirely (`.cache/vision/`). Demo re-runs and eval re-runs cost $0.
- **No call at all** when no readable image arrives.
- Each call's tokens, cost (USD) and latency are logged and aggregated by `eval.py`. Run `python eval.py --estimate` to see the predicted cost before spending anything.
- The model is swappable via `RTN_MODEL` (`claude-sonnet-5-5` costs roughly half as much).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID if your key isn't workspace-scoped)
uvicorn src.main:app --reload
```

`--reload` picks up code changes automatically. Without it, restart the server after pulling changes.

Open http://localhost:8000 for the operator UI:
- **Inspect a return**: pick the SKU, add 1–3 photos by drag-and-drop or phone camera, and get the decision in plain English with the evidence for each check. *Change decision* records an override with a reason.
- **Unit ID auto-fill**: type a unit from the return label. If the account has the original order (sample orders in `data/returns_sample.csv`, e.g. `UNIT-0018` for Bravo, `UNIT-0014` for Alpha), the SKU and parts fill in. The lookup only searches the selected account.
- **Client accounts**: each client (tenant) has separate history, order lookup and API access. Two demo accounts come from the sample data: Alpha Retail = `org_demo_alpha`, Bravo Goods = `org_demo_bravo`. *+ Add client account…* creates a new one and shows its API key once. New accounts are saved in `.data/accounts.json` (git-ignored). Account creation is open in this demo; production would put it behind operator login.
- **History**: past inspections for the selected account.
- **API**: developer docs for the public inspection API (`/developers`).
- **Accuracy testing**: the two-person labelling tool for the eval set (`/label`).

### Public inspection API

Anyone with an API key can inspect a return by uploading photos. No JSON or base64 needed:

```bash
curl -X POST http://localhost:8000/api/v1/inspect   -H "X-API-Key: YOUR_KEY"   -F "sku=SKU-BOTTLE-750"   -F "images=@front.jpg" -F "images=@side.jpg"
```

It returns the same Evidence Record as the UI. `parts` defaults to the catalogue entry.
- **Keys:** each key maps to one client account (`RTN_API_KEYS=key:org,...` in `.env`). A caller can't pick another tenant, and API inspections show up in that account's history.
- **Guardrails, because every call spends Anthropic credit:**
  - a per-key limit (`RTN_RATE_LIMIT_PER_HOUR`, default 30; returns 429 with `Retry-After`)
  - a service-wide daily cap on billed model calls (`RTN_DAILY_CALL_CAP`, default 300). Past the cap, requests fail open to `pending_review` instead of spending more.
  - upload checks: 1–3 images, image types only, under 10 MB each
- **Docs:** full docs with curl/Python/JS examples are at `/developers`. The interactive reference is at `/docs`.

The operator UI endpoints use the `x-org-id` header, a demo stand-in for login. They are not authenticated. The daily cap still protects the budget if the app is deployed publicly.

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/agent` (alias of `/api/v1/returns/process`) | Process one return |
| POST | `/api/v1/returns/process-batch` | Process several returns for one tenant |
| POST | `/api/v1/inspect` | **Public API**: multipart photos + SKU, `X-API-Key` auth |
| GET | `/api/v1/catalog` | SKUs, descriptions, expected parts |
| GET | `/api/v1/returns` | List the caller's records |
| GET | `/api/v1/returns/{record_id}` | Fetch one record (own tenant only) |
| POST | `/api/v1/returns/{record_id}/override` | Record a human override |

The operator endpoints need an `x-org-id` header. The UI's tenant switcher sets it, so you can see isolation live: records made under one org don't appear under the other.

Inputs are validated. An empty or malformed `unit_id`, SKU or parts list gets a 422. An SKU missing from the seller catalogue (`src/catalog.py`) can't pass identity, so the unit goes to review.

### Tests

```bash
python -m pytest tests -q
```

36 offline tests with the model mocked, so they cost nothing. They cover:
- the contract fields and the `/agent` alias
- tenant isolation and cross-tenant ID guessing
- invalid identifiers and unknown SKUs
- fail-open, and skipping the model when there are no images
- cache hits
- override history and rehashing
- batch tenancy
- labeller independence and image path safety in the labelling tool
- the public API's key auth, tenant scoping, upload validation and rate limit
- the daily budget cap
- unknown accounts, account-scoped order lookup, and new accounts getting an isolated working API key
- the full disposition policy

## Evaluation

`eval.py` runs the agent over `eval/labels.csv` and writes `eval/eval-report.md` and `eval/results.json`. It reports:

- per-check accuracy, **FP** (agent PASS where the humans said FAIL) and **FN** (agent FAIL where they said PASS)
- the agent's UNCERTAIN rate, and UNCERTAIN on cases the humans could decide (counted separately so it can't inflate accuracy)
- two-labeller agreement (Cohen's kappa); units the labellers disagree on are reported as ambiguous, not scored
- disposition accuracy with every confusion listed, and the `pending_review` rate
- cost per unit, token counts, and p50/p95 latency

**Building the eval set (the `/label` page):**
1. Open http://localhost:8000/label, choose **Labeller A**, and add units: SKU, parts, and 1–3 photos. Photos go to `eval/images/` and rows to `eval/labels.csv`.
2. Label each unit. The page shows the catalogue description so humans judge identity against the same reference as the model.
3. A second person picks **Labeller B** and labels the same units. Neither can see the other's answers.
4. Run `python eval.py --estimate` (predicted cost), then `python eval.py`.

### Eval results — 50 units, two labellers, `claude-opus-5-5` effort `low`

| Check | Accuracy | FP | FN | UNCERTAIN rate | Human-ambiguous |
|---|---|---|---|---|---|
| Identity | **88.0%** | 0 | 4 | 10% | 0 |
| Completeness | **87.5%** (95.5% when decided) | 0 | 0 | 20% | 2 |
| Condition | **96.0%** | 0 | 0 | 10% | 0 |

Disposition accuracy: **76.7%** on agreed-gold units · pending_review rate: **26%**

Human agreement (Cohen's kappa): identity 1.0 · completeness 0.925 · condition 1.0 · disposition 0.793

Cost: **$0.0181 per unit** · 47 of 50 served from cache · p50 latency 6.3 s · p95 8.1 s

**Zero false positives** on all three checks: the agent never passed something both labellers marked as FAIL.

See `eval/eval-report.md` for every error and failure-mode analysis.

### Preliminary observations (5 development images; not the eval)

These are live runs on `claude-opus-5-5`, effort `low`. They show behaviour only; they are not accuracy numbers.

| Image | Result | Behaviour shown |
|---|---|---|
| Bottle, lid missing | refurbish | Completeness FAIL naming the lid; identity passed from the catalogue description |
| Heavily worn bottle | liquidate | Graded Used - Acceptable |
| Sealed bottle, bag reads "1L" | pending_review | Identity FAIL: it read the label, which contradicts the 750 ml SKU |
| Puzzle box reads "1000 pieces" | pending_review | Identity FAIL against the 500-piece SKU |
| Closed shipping carton | pending_review | All checks UNCERTAIN; nothing inside is visible |

Cost was about $0.018 per image (roughly 2.8k input and 300 output tokens), with 6–9 s latency.

Failure mode found during development: before the catalogue descriptions were added, identity came back UNCERTAIN for every unbranded item, because the SKU code alone doesn't say what the product is. The fix was to pass the seller catalogue description with the SKU.

## Findings (contradictions in the reference data)

From `data/returns_sample.csv` (synthetic):
1. `opened_unused` with a part missing → `restock` (e.g. the row with `parts_missing` set). Restocking an incomplete unit contradicts the completeness check.
2. `signs_of_use` with **no** missing parts → `liquidate`, but `signs_of_use` **with** missing parts → `refurbish`. The incomplete unit gets the better outcome.
3. `opened_unused` complete units are split between `restock` and `refurbish` with no distinguishing field.
4. `amazon_condition` is empty in every row by design, so condition accuracy can't be checked against the sample data.

## Project structure

- `src/main.py`: FastAPI endpoints, tenant-partitioned store, overrides
- `src/agent.py`: the vision call, cache, cost accounting, fail-open, disposition policy
- `src/models.py`: evidence contract (pydantic) and `compute_content_hash`
- `src/catalog.py`: seller catalogue for the identity check (synthetic)
- `src/public_api.py`, `src/static/developers.html`: public inspection API and its docs
- `src/accounts.py`: client accounts, their API keys, and order lookup by unit
- `src/eval_api.py`, `src/static/label.html`: two-labeller eval labelling tool
- `src/static/`: operator UI
- `eval.py`, `eval/labels.csv`: evaluation harness and label sheet
- `tests/`: offline test suite
- `ARCHITECTURE.md`: design and trade-offs

## Deployment

The `Dockerfile` and `render.yaml` are included. On Render: create a *Blueprint* from this repo, then set `ANTHROPIC_API_KEY` (and `ANTHROPIC_WORKSPACE_ID` if needed) in the dashboard. The health check is `/health`. The free tier's disk is ephemeral, so records and new eval labels reset on redeploy. Do the labelling locally.

Deployment URL: https://returns-manager-390y.onrender.com

## Submission checklist (from the problem statement)

| Item | Status |
|---|---|
| Returns Manager implementation works | ✅ UI + API, live Claude vision |
| Identity / Completeness / Condition / Disposition tested | ✅ offline suite + live runs on `test_images/` |
| UNCERTAIN / review handling tested | ✅ |
| Evidence trace implemented | ✅ contract record, JSON viewer, records history, overrides |
| README.md / ARCHITECTURE.md complete | ✅ |
| Evaluation completed (50 units, 2 labellers) | ✅ `eval/eval-report.md` · identity 88% · completeness 87.5% · condition 96% · FP=0 |
| Failure modes documented | ✅ 3 patterns identified in `eval/eval-report.md` |
| Demo video | ✅ https://youtu.be/Qd7Z2MgsjHk |
| Deployment URL | ✅ https://returns-manager-390y.onrender.com |
| LinkedIn post tagging CodeQuesters and Sydon.AI | ✅ https://lnkd.in/p/dzKbD3Ct |

## Video Demo
[Watch Demo on YouTube](https://youtu.be/Qd7Z2MgsjHk)

## LinkedIn Post
[View LinkedIn Post](https://lnkd.in/p/dzKbD3Ct)
