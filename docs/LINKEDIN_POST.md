# LinkedIn post draft

Use the organisers' official template if they share one. Fill in the bracketed numbers from `eval/eval-report.md` before posting, and don't post placeholder numbers.

---

For Round 2 of the Cube Buildathon I built the **Returns Manager**: step 4 of a 5-agent chain that follows one physical unit from supplier to refund.

When a returned parcel is opened, the agent looks at the photos and answers four questions:
✅ Is this the item we sold? (checked against the seller catalogue)
✅ Is it complete?
✅ What condition is it in? (Amazon's published condition scale)
✅ Restock, refurbish, liquidate, dispose, or send to a human?

What I focused on:
🔹 **UNCERTAIN is a real answer.** A closed carton or a blurry photo goes to human review instead of getting a confident guess.
🔹 **One vision call per return**, with the disposition decided by fixed, tested rules in code. It costs about $[x] per unit.
🔹 **Every decision is an evidence record** with its checks, confidence, reasons and hash, plus operator overrides kept as history.
🔹 **Tenant isolation and fail-open**: a model outage never loses a return.

Evaluated on [n] held-out units labelled independently by two people:
Identity [x]% · Completeness [x]% · Condition [x]% · Disposition [x]% · review rate [x]%

Repo: https://github.com/Yaser-123/cube26-rtn-0167-yaser-123
Demo: [video link]

Thanks to @CodeQuesters and @Sydon.AI for running the buildathon.

#CubeBuildathon #AI #Ecommerce #Returns #BuildInPublic
