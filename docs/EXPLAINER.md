# Explainer — judge-ready study guide

---
## [2026-10-10 11:40] Project setup + first commit — Milestone 1 item 1 (Setup)

- **What we did (plain English):** We created our own project folder and saved its first snapshot in git (a tool that keeps a history of every change). It holds our rulebook (CLAUDE.md), the safety limits, a glossary, a progress tracker, and the first version of the program that maps which shop services depend on each other.
- **Why it matters:** Our safety limits are written down and saved before we break anything, so every experiment can be traced back to agreed rules.
- **Analogy:** Like signing off the safety plan before a fire drill starts.
- **Say it like this:** "From the first hour, our safety limits were written in a version-controlled config file — not hard-coded or decided on the fly."
- **Likely judge question + our answer:** *"Why keep thresholds in a config file?"* — "So we can tune them from the measured baseline without touching code, and anyone can see exactly what triggers an abort."
- **Numbers to remember:** abort after 30 s of errors > 5% (or 3× normal) or p95 latency > 2× normal; every fault auto-undone after 120 s.

---
## [2026-10-10 11:44] Static dependency map — Milestone 1 item 2 (Application mapping)

- **What we did (plain English):** We wrote a program that reads the shop's setup files and draws a map of which services rely on which. It then counts, for each service, how many others would be hurt if it failed.
- **Why it matters:** Chaos engineering should start with the parts whose failure hurts the most; the map tells us where those are, so our experiments are chosen for a reason, not at random.
- **Analogy:** Like a city map showing which bridges, if closed, would cut off the most neighbourhoods.
- **Say it like this:** "We let Docker merge the app's configuration and turned it into a graph; the product database turned out to be the single most critical piece — five services depend on it."
- **Likely judge question + our answer:** *"Config only says what COULD talk — how do you know what really does?"* — "That's why we add a second, runtime view from Jaeger traces, and we highlight connections that appear in only one of the two views."
- **Numbers to remember:** 19 shop services, 27 connections; astronomy-db → 5 services impacted, kafka → 4, product-catalog/quote/valkey-cart → 3.
