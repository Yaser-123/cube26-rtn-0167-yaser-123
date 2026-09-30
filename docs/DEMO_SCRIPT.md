# Returns Manager — Demo Script (Rewritten)
# 4:30 target · business + tech · story-driven

---

## THE CORE STORY TO TELL

Business hook: Wrong return decisions cost money in both directions.
Pass a damaged item → angry buyer, costly reverse logistics.
Reject a good item → money left on the table.
The agent solves this with a feedback loop that gets smarter over time.

Three acts:
  ACT 1 — The problem + live demo (show the magic)
  ACT 2 — How it actually works (earn the trust)
  ACT 3 — It learns (the future angle / why this compounds)

---

## BEFORE YOU RECORD

Have these open and ready:
- Tab 1: https://returns-manager-390y.onrender.com  (set to Alpha Retail)
- Tab 2: eval/eval-report.md in VS Code
- Terminal: cd into the project folder
- Images to upload (drag-and-drop order):
    1. test_images/test_used_bottle_1790418109421.jpg
    2. test_images/test_missing_lid_1790418125316.jpg
    3. test_images/test_new_sealed_1790418156479.jpg
    4. test_images/test_closed_box_1790418142766.jpg

Wake up Render 30 seconds before hitting record (free tier sleeps).

---

## SCRIPT

---

### ACT 1 — THE PROBLEM IS EXPENSIVE (0:00–0:20)

**[Open with the operator UI already on screen — not a title card]**

> "Amazon processes over a million returns a day.
> Every single one needs the same four questions answered:
> Right product? Complete? What condition? What do we do with it?
> Get it wrong in one direction — you restock a damaged item and an angry buyer
> leaves a one-star review. Get it wrong in the other direction —
> you dispose of something worth thirty dollars.
> This agent answers all four questions from a single photo.
> Let me show you."

---

### ACT 2 — THE MAGIC (0:20–2:00)

**[Select Alpha Retail account. Type unit ID. Choose SKU-BOTTLE-750. Drag in the used bottle photo. Hit Inspect.]**

> "750ml stainless-steel water bottle. One photo.
> Watch what happens."

**[Results load — hold for 2 seconds so viewer can read them]**

> "Three verdicts, each one independent.
> Identity: PASS — it's the right product.
> Completeness: PASS — bottle and lid, both there.
> Condition: Used - Acceptable. Not our invented scale —
> Amazon's actual published Condition Guidelines.
> Disposition: liquidate.
> Total cost: under two cents. Total time: under 10 seconds."

**[Drag in the missing-lid photo — same SKU — hit Inspect]**

> "Same bottle. Lid missing.
> Completeness fails — and it tells you exactly what's missing.
> A sound item with one missing part doesn't get disposed.
> It goes to refurbish. Add the lid, resell it.
> That's recoverable revenue the old process would have lost."

**[Drag in the sealed bottle photo — click Inspect]**

> "Now this one.
> The bag it came in reads one litre. We sold 750ml.
> Identity FAIL.
> The agent read the label on the packaging and caught a discrepancy
> that a rushed warehouse worker absolutely would have missed.
> Wrong item. Goes to a human — never auto-disposed.
> You always want a human in the loop when something doesn't add up."

**[Drag in the closed box photo — click Inspect]**

> "Closed box. Can't see inside.
> Every check comes back UNCERTAIN.
> This is important. The agent knows what it doesn't know.
> It doesn't guess. It keeps the capture, flags it for review,
> and nothing falls through the cracks."

---

### ACT 3 — THE TRUST LAYER (2:00–2:45)

**[Click Change Decision on one result → pick Refurbish → type: "Operator disagrees — item appears functional" → Save]**
**[Open Record Details — show the JSON]**

> "Operators can always override the agent. And here's where it gets interesting
> for the business side.
> Every override is stored — original verdict, new verdict, reason, timestamp.
> The agent's checks are never erased, just annotated.
> That means every time a human disagrees with the AI,
> we're capturing a labelled training example.
> Over time, that override history becomes the dataset
> that closes the gap between 88 percent accuracy and 98 percent.
> The system gets smarter the more it's used."

**[Switch account to Bravo Goods]**

> "Records are fully isolated by tenant.
> Switch to a different client — completely separate history.
> Guessing another tenant's record ID returns 404.
> Enterprise-grade data isolation, out of the box."

---

### ACT 4 — THE FEEDBACK LOOP (2:45–3:30)

**[Open the /label page]**

> "Now here's the piece most AI tools skip entirely: measurement.
> This is the two-person labelling interface.
> Person A labels each return. Person B labels the same items independently.
> They never see each other's answers."

**[Open eval/eval-report.md — show the accuracy table]**

> "Then we run an evaluation. Real numbers from 50 labelled units:
> Identity accuracy: 88 percent.
> Condition accuracy: 96 percent.
> And the number that actually matters for a returns system —
> false positives: zero.
> The agent never passed something both labellers marked as fail.
> The safety-critical direction is completely clean."

**[Point at the kappa scores]**

> "We also measure labeller agreement — Cohen's kappa.
> 1.0 on identity and condition. That means the humans agreed perfectly.
> Where they disagreed — those cases are marked ambiguous and excluded from scoring.
> That's rigorous. Most AI demos don't show you this."

**[Scroll to Failure modes]**

> "And here's the failure mode analysis — three specific patterns,
> each with a named fix. This is how you improve the model systematically,
> not just by vibe-checking outputs.
> Think of the A/B labelling as a permanent feedback loop.
> Run it monthly. Track accuracy over time. Ship prompt improvements with confidence.
> This is how the 88 becomes 95, then 98."

---

### ACT 5 — UNDER THE HOOD (3:30–4:00)

**[Switch to terminal]**

> "For the engineers in the room:"

```
python -m pytest tests -q
```

> "36 offline tests. Model is mocked — they cost nothing and run in two seconds.
> Tenant isolation, fail-open behaviour, override integrity, rate limits,
> the full disposition policy — all covered."

**[Open /developers page for 5 seconds]**

> "Public API for downstream systems.
> Upload photos and a SKU with an API key, get an evidence record back.
> Rate-limited per key. Service-wide daily spending cap.
> The model is swappable via an environment variable —
> drop to Sonnet if you want half the cost,
> upgrade to Opus if you need higher accuracy.
> One config change."

---

### CLOSE (4:00–4:20)

**[Return to the operator UI — the live URL on screen]**

> "What makes this different isn't just the AI.
> It's the feedback loop.
> Every inspection builds the evidence record.
> Every override adds a labelled training example.
> Every eval run closes the gap.
> The model grades. The code decides. The humans improve it.
> That's not a demo. That's a system."

**[Hold on URL: https://returns-manager-390y.onrender.com — 3 seconds — cut]**

---

## POWER LINES — SAY THESE CLEARLY

Pick the moments to slow down and land these:

1. "The agent knows what it doesn't know." (on UNCERTAIN)
2. "Every override is a labelled training example." (on the feedback loop)
3. "False positives: zero. The safety-critical direction is clean." (on eval)
4. "The model grades. The code decides. The humans improve it." (closing)

---

## AFTER THE VIDEO

Paste the Loom / YouTube link into README.md at this line:
  [Link to Demo Video (Placeholder) - Loom / YouTube]

Then run:
  git add README.md
  git commit -m "docs: add demo video link"
  git push
