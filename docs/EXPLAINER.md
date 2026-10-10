# Explainer â€” judge-ready study guide

---
## [2026-10-10 11:40] Project setup + first commit â€” Milestone 1 item 1 (Setup)

- **What we did (plain English):** We created our own project folder and saved its first snapshot in git (a tool that keeps a history of every change). It holds our rulebook (CLAUDE.md), the safety limits, a glossary, a progress tracker, and the first version of the program that maps which shop services depend on each other.
- **Why it matters:** Our safety limits are written down and saved before we break anything, so every experiment can be traced back to agreed rules.
- **Analogy:** Like signing off the safety plan before a fire drill starts.
- **Say it like this:** "From the first hour, our safety limits were written in a version-controlled config file â€” not hard-coded or decided on the fly."
- **Likely judge question + our answer:** *"Why keep thresholds in a config file?"* â€” "So we can tune them from the measured baseline without touching code, and anyone can see exactly what triggers an abort."
- **Numbers to remember:** abort after 30 s of errors > 5% (or 3Ã— normal) or p95 latency > 2Ã— normal; every fault auto-undone after 120 s.

---
## [2026-10-10 11:44] Static dependency map â€” Milestone 1 item 2 (Application mapping)

- **What we did (plain English):** We wrote a program that reads the shop's setup files and draws a map of which services rely on which. It then counts, for each service, how many others would be hurt if it failed.
- **Why it matters:** Chaos engineering should start with the parts whose failure hurts the most; the map tells us where those are, so our experiments are chosen for a reason, not at random.
- **Analogy:** Like a city map showing which bridges, if closed, would cut off the most neighbourhoods.
- **Say it like this:** "We let Docker merge the app's configuration and turned it into a graph; the product database turned out to be the single most critical piece â€” five services depend on it."
- **Likely judge question + our answer:** *"Config only says what COULD talk â€” how do you know what really does?"* â€” "That's why we add a second, runtime view from Jaeger traces, and we highlight connections that appear in only one of the two views."
- **Numbers to remember:** 19 shop services, 27 connections; astronomy-db â†’ 5 services impacted, kafka â†’ 4, product-catalog/quote/valkey-cart â†’ 3.

---
## [2026-10-10 11:55] Cleaner dependency map picture â€” Milestone 1 item 2 (Application mapping)

- **What we did (plain English):** We redrew the map as a left-to-right flowchart: traffic comes in on the left, databases sit on the right. Each service is a labelled box, and a red badge shows how many other services would be hurt if it failed. Arrows through the Kafka message queue are dashed because they are "fire and forget" (the sender doesn't wait for a reply).
- **Why it matters:** A judge can see in five seconds where the risky points are (astronomy-db = 5, kafka = 4), which is exactly what our planner uses to choose experiments.
- **Analogy:** Like a metro map: it doesn't show real distances, it shows clearly which stops connect and which station is the busiest interchange.
- **Say it like this:** "Read it left to right like a request travelling through the shop; the red numbers tell you how much breaks if that box goes down."
- **Likely judge question + our answer:** *"Why is accounting on the right of Kafka if it depends on Kafka?"* â€” "Arrows show data flow. Checkout drops orders into Kafka, and accounting reads them later; for the impact count we still treat accounting as depending on Kafka."
- **Numbers to remember:** we hide 3 "start-up order" links (e.g. frontend â†’ quote) because they only control boot order, not real calls.

---
## [2026-10-10 12:01] Fault injector + emergency stop — Milestone 1 items 4 & 5 (Injection, Safety)

- **What we did (plain English):** We wrote the tool that breaks things: it can crash a service, freeze it, or slow/drop its network traffic. Every "break" has a matching "undo", runs for at most 2 minutes, and is undone automatically on timeout or Ctrl+C. We also wrote a one-click emergency script that un-breaks everything.
- **Why it matters:** Bosch's brief asks for *controlled* failures with safety limits. A strict guest list (allowlist) plus a do-not-touch list (denylist) plus a check that the container really belongs to our shop means we can never hit our monitoring tools, other projects, or anything outside the sandbox.
- **Analogy:** Like a circuit breaker test in a building: you only flip switches on the labelled test panel, there's a timer that flips them back, and a master reset on the wall.
- **Say it like this:** "Every fault we inject has an undo button, a 2-minute timer, and a guest list — we tested that it refuses our monitoring tools and anything outside our project."
- **Likely judge question + our answer:** *"How do you make sure a network fault doesn't hit the venue Wi-Fi?"* — "We use Pumba, which applies the delay only inside the target container's own network namespace (its private network card), never the laptop's or the venue's."
- **Numbers to remember:** 17 allowed targets, 11 never-touch services; tested refusals: prometheus (denylist), unknown name, container not in our project.

---
## [2026-10-10 12:10] App running + choosing our "scoreboards" — Milestone 1 items 1 & 3 (Setup, Baseline)

- **What we did (plain English):** We got all 28 parts of the shop running and found two places to read health numbers: the fake shoppers' own live scoreboard (Locust, updates every ~2 s) and the monitoring database (Prometheus, per-service detail but only updated about once a minute).
- **Why it matters:** A safety referee that checks every 5 seconds needs numbers that change every few seconds; a once-a-minute number would let a full minute of damage happen before anyone noticed.
- **Analogy:** A car's speedometer (live, for driving safely) versus the trip computer summary (detailed, for reviewing the journey afterwards).
- **Say it like this:** "We measured how fresh each data source is: Prometheus refreshes every ~60 s, so our kill switch watches the shoppers' live experience instead, and we use Prometheus to explain *which* service caused it."
- **Likely judge question + our answer:** *"Why not just use Prometheus for everything?"* — "We checked the sample timestamps: about 55–60 s apart. A 30-second abort rule can't work on data that arrives once a minute."
- **Numbers to remember:** 28 containers; Prometheus refresh ≈ 60 s; Locust refresh ≈ 2 s; we ignore `/prompt` (chatbot add-on we didn't deploy).

---
## [2026-10-10 12:30] Real-traffic map + first manual crash — Milestone 1 items 2 & 4

- **What we did (plain English):** We compared the map from the setup files with what the tracing tool actually saw shoppers do. We also crashed the recommendation service by hand and checked whether Docker brought it back on its own.
- **Why it matters:** Config shows what *could* happen; traffic shows what *does*. And a crash test with no automatic recovery is our first real resilience weakness.
- **Analogy:** The building's floor plan versus CCTV of where people actually walk.
- **Say it like this:** "Every service-to-service call in the config was confirmed by real traffic; the only gaps were databases and the message queue, which tracing can't name — so we need both views. And when we killed a service, Docker did not restart it by itself."
- **Likely judge question + our answer:** *"The containers have a restart policy — why didn't it restart?"* — "Docker treats `docker kill` as a deliberate manual stop, so the policy doesn't fire. A real crash inside the app would be restarted, but a killed or OOM-stopped box needs a health-based restarter (like Kubernetes liveness probes) — that's a fix we can propose."
- **Numbers to remember:** 20 nodes, 28 links; astronomy-db hurts 5 services, kafka 4; recommendation RestartCount = 0 after kill.
