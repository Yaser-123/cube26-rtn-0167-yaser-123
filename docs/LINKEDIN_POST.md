# LinkedIn Post — Final Draft

**Post this on LinkedIn. Tag CodeQuesters and Sydon.AI. Then paste the live post URL into the submission form.**

---

COPY THIS TEXT:

---

Just shipped my Round 2 submission for the Cube Buildathon — and it was one of the most intense engineering challenges I have taken on.

I built the Returns Manager — Step 4 of a 5-agent commerce chain built by Sydon.AI x CodeQuesters. The problem it solves is deceptively simple: when a parcel comes back, what do you do with it?

The answer requires four decisions made instantly, consistently, and at scale:
PASS - Is this the item we actually sold?
PASS - Are all the parts there?
PASS - What condition is it in? (Amazon's official published scale — not made up)
PASS - Restock? Refurbish? Liquidate? Dispose? Or escalate to a human?

How it works:
The operator uploads a photo of the return. One vision API call to Claude 3.5 Sonnet runs all three checks simultaneously — identity, completeness, and condition — returning a structured JSON evidence record with confidence scores, reasons, and a SHA-256 content hash for audit traceability. Fixed, deterministic rules in code convert that into a disposition. No AI making the final call — the AI grades, the code decides.

The engineering decision I am most proud of:
I spent real time on AI hallucination mitigation. Early builds would confidently say "bottle and lid present — Used Like New" when the image was literally a closed cardboard box. The fix was not adding more specific rules (that is whack-a-mole). Instead I built a Zero-Trust Evidence Policy into the prompt: the model must visually confirm every claim or set needs_more_images: true and route to human review. UNCERTAIN is a first-class outcome, not a failure state.

What the evaluation showed:
- Closed box or blurred image: correctly flagged UNCERTAIN every time
- Missing lid: completeness FAIL caught correctly with reason stated
- Used item: condition graded on Amazon's actual scale, disposition auto-set to REFURBISH
- API failure: fail-open — the return is preserved in pending_review, never lost

Architecture highlights:
- Multi-tenant isolation enforced at API level via x-org-id header (403 on mismatch)
- Operator override system: original verdict + revised verdict + reason stored permanently as audit trail — never silently replaced
- Batch endpoint for processing multiple returns in one pass
- Full offline test suite (mocked model) — runs in under 3 seconds, zero API cost

Demo: https://youtu.be/Qd7Z2MgsjHk
GitHub: https://github.com/Yaser-123/cube26-rtn-0167-yaser-123
Live deployment: https://returns-manager-390y.onrender.com/

Building this pushed me to think about AI reliability in a way I had not before. Getting the model to do the right thing on edge cases is a prompt engineering and architecture problem as much as it is an AI problem.

Grateful to CodeQuesters and Sydon.AI for designing a buildathon that actually rewards engineering depth over flashy demos.

@CodeQuesters @Sydon.AI

#CubeBuildathon #AI #MachineLearning #ComputerVision #Python #FastAPI #BuildInPublic #Ecommerce #Returns #LLM #PromptEngineering

---

## Images to attach (pick 3-4, post in this order)

1. HERO IMAGE: Screenshot of the UI showing REFURBISH result — dark glassmorphism UI, green PASS badges, blue REFURBISH badge. Post this first.

2. SAFETY CASE: Screenshot of UNCERTAIN / PENDING REVIEW result on the closed box — proves "the agent knows what it doesn't know".

3. OVERRIDE: Screenshot of the Override modal with a reason being typed — illustrates the audit trail / human-in-the-loop feature.

4. TECHNICAL: Screenshot of the terminal showing DEBUG CLAUDE RESPONSE with real JSON — proves it is a real working system, not a mock.

---

## After posting

1. Copy the live LinkedIn post URL
2. Paste it into the official Round 2 submission form
3. Update README.md with the LinkedIn URL
4. git add README.md && git commit -m "docs: add LinkedIn post link" && git push
