# Demo Video Script — Returns Manager
# Target: 4–5 minutes · record at https://returns-manager-390y.onrender.com

---

## BEFORE YOU RECORD

Open these tabs in advance:
1. https://returns-manager-390y.onrender.com  (operator UI)
2. https://returns-manager-390y.onrender.com/developers  (API docs)
3. https://returns-manager-390y.onrender.com/label  (eval labelling tool)
4. A terminal with the project folder open
5. eval/eval-report.md open in VS Code

Have these images ready to upload:
- test_images/test_used_bottle_1790418109421.jpg
- test_images/test_missing_lid_1790418125316.jpg
- test_images/test_new_sealed_1790418156479.jpg
- test_images/test_closed_box_1790418142766.jpg

---

## SCRIPT

---

### 00:00 — HOOK (15 seconds)

**[Show: the live deployed URL in browser]**

> "Every returned parcel on Amazon needs four answers before anything can happen to it:
> Is this actually the product we sold? Is it complete? What condition is it in?
> And what do we do with it — restock, refurbish, liquidate, or dispose?
> A human doing this manually takes 3 to 5 minutes per item.
> This agent does it in one photo and one API call."

---

### 00:15 — ARCHITECTURE IN 30 SECONDS

**[Show: README.md — the "How it works" diagram section]**

> "The design is simple on purpose. Up to three photos go in. There is exactly one call
> to Claude — claude-opus-5-5 — which returns a strict JSON schema with three verdicts:
> identity, completeness, and condition. Each verdict is PASS, FAIL, or UNCERTAIN.
> After that, a deterministic policy in code — not the model — decides the disposition.
> The model grades. The code decides. The model can never auto-dispose a wrong item."

**[Point at the disposition policy table]**

> "If anything is UNCERTAIN, the unit goes to human review.
> Zero false positives is the hard constraint.
> The agent must never pass something humans would fail."

---

### 00:45 — LIVE DEMO: USED BOTTLE → LIQUIDATE

**[Operator UI. Select account: Alpha Retail. Type a Unit ID, select SKU-BOTTLE-750,
drag in test_used_bottle image, click Inspect]**

> "One photo of a returned water bottle."

**[Results appear — show the three verdict cards]**

> "Identity PASS — it matches the 750ml stainless-steel SKU in our catalogue.
> Completeness PASS — bottle and lid both present.
> Condition: Used - Acceptable. That is Amazon's published condition scale, not our own invented one.
> Disposition: liquidate.
> Each verdict has a confidence score and a one-sentence explanation of what the model saw.
> That sentence is the evidence trail — auditable, stored, and tamper-detectable via SHA-256."

---

### 01:30 — MISSING PART → REFURBISH

**[Upload test_missing_lid image, same SKU, click Inspect]**

> "Same bottle, lid missing. Completeness fails — and it names the missing part.
> A sound item with a missing part goes to refurbish, not dispose.
> Add the part, resell it. That is recoverable value."

---

### 02:00 — WRONG ITEM + FAIL OPEN

**[Upload test_new_sealed image, SKU-BOTTLE-750, click Inspect]**

> "This one is interesting. The bag reads 1 litre. We sold a 750ml bottle.
> Identity FAIL — the label contradicts the SKU.
> A wrong item never gets auto-disposed. It goes to pending review,
> where a human and the Recovery Manager downstream can handle it."

**[Upload test_closed_box image, click Inspect]**

> "Closed shipping carton. Nothing inside is visible.
> Every check comes back UNCERTAIN.
> The agent refuses to guess. UNCERTAIN is a real, correct verdict.
> Fail open: the capture is kept, routed to review, nothing is lost."

---

### 02:30 — OVERRIDE + EVIDENCE RECORD

**[Click Change Decision on any result → Refurbish → type a reason → Save]**

> "Operators can disagree with the agent. The override is appended to the record —
> original verdict, new verdict, reason, timestamp.
> The agent's checks are left exactly as they were."

**[Click Record Details — show the JSON with checks, overrides, content_hash]**

> "This is the evidence contract — the shape the Recovery Manager downstream consumes.
> The content hash is SHA-256 over canonical JSON. It detects any tampering.
> Overrides are history, not erasure."

---

### 03:00 — TENANT ISOLATION

**[Switch the account switcher from Alpha Retail to Bravo Goods]**

> "Records are partitioned by tenant. Switch to Bravo Goods —
> Alpha's inspection history disappears completely.
> Guessing Alpha's record ID returns 404.
> The org ID header is validated on every single request."

---

### 03:15 — PUBLIC API

**[Open the /developers page]**

> "The same agent is a public API. Any system with an API key
> can upload photos and a SKU and get the evidence record back."

**[Switch to terminal, run this command:]**

  curl -X POST https://returns-manager-390y.onrender.com/api/v1/inspect
    -H "X-API-Key: rtn_alpha_q5-pwtkUOYgqAElgbnTV9pwh"
    -F "sku=SKU-BOTTLE-750"
    -F "images=@test_images/test_used_bottle_1790418109421.jpg"

> "One curl command. The key maps to one tenant only, rate-limited to 30 calls per hour,
> with a service-wide daily spending cap so a public deployment cannot drain the account."

---

### 03:45 — EVAL RESULTS

**[Open eval/eval-report.md — show the per-check accuracy table]**

> "The agent was evaluated on 50 units labelled independently by two people.
> Identity: 88 percent accuracy. Completeness: 87.5 percent. Condition: 96 percent.
> False positives: zero across all three checks.
> The agent never passed something both labellers marked as fail.
> Human agreement — Cohen's kappa — was 1.0 on identity and condition.
> Cost: 1.8 cents per unit. 47 of 50 units served from cache."

**[Scroll to Failure modes section]**

> "Three failure patterns identified. The model over-weights readable text on packaging.
> Low-information images sometimes get a decided verdict when they should be UNCERTAIN.
> Both have prompt-level fixes. But critically — zero false positives.
> The safety-critical direction is clean."

---

### 04:15 — TEST SUITE

**[Terminal:]**

  python -m pytest tests -q

> "36 offline tests, model mocked, run in 2 seconds.
> They cover tenant isolation, fail-open, override history, the full disposition policy,
> API key auth, rate limits, the daily cap, and account-scoped order lookup."

---

### 04:30 — CLOSE

**[Return to the live UI]**

> "Returns Manager is step 4 of 5 in the chain.
> One model call. Three graded checks. A deterministic policy.
> An auditable evidence record the Recovery Manager can consume.
> Zero false positives. 1.8 cents per unit.
> It is live, tested, and documented."

**[Hold on the URL for 3 seconds — cut]**

---

## RECORDING TIPS

- Use Loom (free) or OBS. Record at 1080p minimum.
- Set browser font to 110 percent so text is readable in the recording.
- If Render is in sleep mode (free tier), open the URL 30 seconds before recording starts.
- Do one dry run. Target 4:40 to 5:00 total.
- After you upload the video, paste the link into README.md and replace the line:
    [Link to Demo Video (Placeholder) - Loom / YouTube]
