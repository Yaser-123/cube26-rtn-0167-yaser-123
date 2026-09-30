# Demo video script (about 4 minutes)

Record the screen at http://localhost:8000 (or the deployed URL). Keep a terminal visible for the last part.

| Time | Show | Say |
|---|---|---|
| 0:00 | Title and README | "Returns Manager is step 4 of 5. Someone opens a returned parcel and needs four answers in seconds: is it the item we sold, is it complete, what condition is it in, and what happens next." |
| 0:20 | Upload `test_used_bottle` → **liquidate** | "One photo, one model call. Each check has its own verdict, confidence and a sentence of evidence. Condition uses Amazon's published scale, and the disposition comes from a fixed policy in code, not from the model." |
| 0:50 | Upload `test_missing_lid` → **refurbish** | "Completeness fails. It names the missing lid, and a sound bottle with a missing part goes to refurbish." |
| 1:15 | Upload `test_new_sealed` → **pending review** | "It read the bag label: 1 litre, but we sold a 750 ml bottle. A wrong item goes to a human, never to auto-dispose." Point at the *Why it needs review* note. |
| 1:40 | Upload `test_closed_box` → **pending review**, all UNCERTAIN | "A closed carton. Nothing inside is visible, so every check is UNCERTAIN. The agent refuses to guess, and UNCERTAIN is a real verdict here." |
| 2:00 | Click **Change decision** → Refurbish, with a reason | "Operators can disagree. The override is appended with the original verdict, the reason and a timestamp. The agent's checks stay as they were, and the hash is recomputed." Open *Record details* to show the JSON. |
| 2:30 | Switch *Client account* to Alpha Retail | "Records are partitioned by tenant. The other org sees zero rows, and guessing a record ID returns 404." |
| 2:40 | Open **API**, run the curl example in a terminal | "Other systems can call the same agent: upload photos and a SKU with an API key and get the evidence record back. Keys are tied to one client, rate-limited, and there's a daily spending cap." |
| 2:55 | Open **Accuracy testing** | "The eval set is labelled here. Two people label each unit independently and never see each other's answers." |
| 3:10 | Terminal: `python -m pytest tests -q` then `python eval.py` | "36 offline tests cover isolation, fail-open, overrides and the disposition policy. The eval reports per-check accuracy, false positives and negatives, the UNCERTAIN rate, labeller agreement, and cost per unit." Show `eval/eval-report.md`. |
| 3:40 | README cost section | "About two cents per return. There's one call per unit, 1024px images, low effort, and a cache so re-runs are free. If the model fails, the case is kept as pending review, not lost." |
