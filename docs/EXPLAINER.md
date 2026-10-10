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

---
## [2026-10-10 13:12] Healthy baseline captured + fairer recovery check — Milestone item 3 (Monitoring baseline)

### 🗣️ Explain it to the judges
- **What we did (plain English):** With 15 fake shoppers using the shop and nothing broken, we took a reading every 5 seconds for 3 minutes. Healthy means: 0% failed requests, about 0.5 seconds average response, about 2.7 requests per second. We also noticed that healthy readings alone jump between 0.3 and 0.9 seconds, so we now judge "recovered" on a 30-second average instead of on single noisy readings.
- **Why it matters:** Every safety decision is "compared to normal". Without a baseline the referee can't tell broken from busy; with a noisy measure it would report fake slow recoveries.
- **Analogy:** Taking your resting heart rate before a stress test — and averaging a few beats rather than trusting one.
- **Say it like this:** "We measured healthy first: zero errors and about half a second per request at 15 shoppers. Our safety stop fires if errors pass 5% or responses double to over one second for 30 seconds."
- **Likely judge question + our answer:** "Why 15 users, not more?" — "At 50 to 100 users the database ran out of memory and the load generator itself maxed out, so higher numbers would measure our test tool, not the shop. At 5 users each 5-second check saw only about 6 requests — one failure would look like 17% errors."
- **Numbers to remember:** 0.00% errors · 517 ms avg response · 2.7 req/s · 15 users · abort limits 5% errors / 1,034 ms · healthy readings swing 275–880 ms · at 5 users avg was ~115 ms (4–5× slower at 15 users).

---
## [2026-10-10 13:16] Experiment 1: crash recommendation — safety stop fired automatically — Milestone items 4 + 5

### 🗣️ Explain it to the judges
- **What we did (plain English):** Our safety controller crashed the recommendation service (the "you may also like" box) with a 90-second limit, and checked what shoppers felt every 5 seconds. From 15 seconds in, responses were 2–7× slower than normal and up to 20% of requests failed. After 30 seconds of that, the controller stopped the experiment on its own after 41 seconds, restarted the service, and measured 66 seconds until the shop was back to normal.
- **Why it matters:** It proves both seat belts: our code broke something on purpose AND undid it automatically when shoppers were hurt too much — without a human. It also found a real weakness: a small optional feature can drag down the whole shop because there is no fallback.
- **Analogy:** A fire drill where the alarm system itself noticed people were getting stuck and opened the doors early.
- **Say it like this:** "We crashed a small, optional service. We expected nobody to notice — instead one in five requests failed, so our referee stopped the test after 41 seconds by itself and the shop was back to normal 66 seconds later."
- **Likely judge question + our answer:** "Why did the shop take 66 seconds to recover when the service restarted instantly?" — "The service was ready in under a second, but the frontend only started talking to it again 21 seconds later, then a second wave of slow, failing product pages hit 30–60 seconds after the restart. We haven't confirmed the cause yet; our best guess is that queued requests were all released at once and overloaded the product catalog. That's what we'd check next in the traces."
- **Numbers to remember:** abort at +41 s (limit 90 s) · abort reason errors 9.1% > 5%, avg 1,745 ms > 1,034 ms · peak errors 20% · peak avg response 3.7 s · recovery 66 s · aftershock up to 50% errors / 9.7 s · 21 s silence before traffic returned.

---
## [2026-10-10 13:33] Published the repo "Faultline" with README + deploy steps — Submission requirement (repo link + deployment steps)

### 🗣️ Explain it to the judges
- **What we did (plain English):** We named the project Faultline and put the code on GitHub publicly, with an open-source license (MIT) and a README that explains, step by step, how anyone can start the shop and run our safety-controlled experiments on their own laptop. Before publishing we checked there were no passwords, keys or personal emails anywhere in the history.
- **Why it matters:** The brief requires a public repo and deployment steps; a stranger being able to reproduce our results is what makes them trustworthy.
- **Analogy:** Publishing a recipe with exact ingredients and steps, not just a photo of the cake.
- **Say it like this:** "Everything is on GitHub under Faultline — clone two repos, run one command for the shop and three for our map, baseline and experiment."
- **Likely judge question + our answer:** "Can I run this on my machine?" — "Yes: Docker Desktop and Python. The README has the exact commands; the only manual step we hit was building one image the demo didn't publish."
- **Numbers to remember:** 1 repo · MIT license · 3 commands to map, measure and run an experiment · 28 containers in the target app.

---
## [2026-10-10 13:45] Emergency stop fixed + demo script + correcting our own finding — Milestone items 5 + 6

**This replaces the earlier explanation (12:24 / 12:30 entries) that "Docker does not self-heal after a crash", because new evidence showed `docker kill` counts as a deliberate stop; real crashes ARE auto-restarted.**

### 🗣️ Explain it to the judges
- **What we did (plain English):** We tested our emergency stop button before relying on it and found it would have run commands inside our own monitoring tools, so we restricted it to the services we're allowed to break; it now finishes in about 5 seconds. We wrote a 3-minute demo script with a fallback for everything that can go wrong. And we corrected one of our own findings when new evidence contradicted it.
- **Why it matters:** An emergency button that touches monitoring could blind the safety system at the worst moment; correcting our own finding shows our conclusions come from evidence.
- **Analogy:** Testing the fire extinguisher before the fire drill — and updating the report when a witness changes their story.
- **Say it like this:** "We first thought Docker doesn't self-heal. Then we saw it auto-restart a real crash — our kill is treated as a deliberate stop. So our controller restores what it breaks itself, and real crashes are Docker's job."
- **Likely judge question + our answer:** "Do you rely on Docker's restart policy?" — "No. The controller always restores what it broke. Docker's restart only covers real crashes, which we saw happen to product-catalog at 12:40."
- **Numbers to remember:** emergency stop 5.4 s · 17 allowlisted targets cleaned, 11 protected ones never touched · product-catalog auto-restarted at 12:40 (RestartCount 1).

---
## [2026-10-10 14:45] Docker froze — the referee must never freeze with it — Milestone item 5 (Safety controls)

### 🗣️ Explain it to the judges
- **What we did (plain English):** During our break, Docker itself — the engine everything runs on — stopped answering. We realised our safety referee would have frozen with it and never undone a fault, so every command it sends to Docker now gives up after 60 seconds and says so loudly. After restarting Docker, only 4 of 28 parts of the shop came back by themselves; one command brought back the rest.
- **Why it matters:** A safety system must fail safely, and an app that doesn't come back after an infrastructure restart is a real resilience weakness.
- **Analogy:** A lifeguard whose radio dies doesn't keep waiting for instructions — they blow the whistle and clear the pool.
- **Say it like this:** "Our own infrastructure froze during the hackathon. We used it: the controller now times out every Docker call, and we found the shop doesn't fully come back on its own after a Docker restart."
- **Likely judge question + our answer:** "What if the chaos tool itself fails mid-experiment?" — "Every Docker call times out after 60 seconds, the controller reports it, and `stop_all.ps1` restores everything; Pumba's network faults also undo themselves after their duration."
- **Numbers to remember:** Docker unresponsive at 14:20 · 60 s timeout per Docker command · only 4 of 28 containers auto-returned after restart · 28/28 back at 14:42.

---
## [2026-10-10 15:05] Our rehearsal beat our own safety rule → abort on a 30-second average; control-room dashboard — Milestone items 5 + 6

**This replaces the earlier explanation that the safety stop fires after "6 bad checks in a row", because our rehearsal showed bursty damage can slip past that rule.**

### 🗣️ Explain it to the judges
- **What we did (plain English):** In our rehearsal, crashing the recommendation service hurt up to 27% of requests, but in bursts — and every normal reading in between reset our "6 bad checks in a row" counter, so the referee never stopped the test. We changed the rule to "stop if the average of the last 30 seconds is over the limit" and replayed it on every real run we have: it now stops both runs at 31 seconds and never false-alarms on healthy data. We also built a control-room web page with live numbers, the map, a START button and a big red STOP button.
- **Why it matters:** A safety rule that intermittent damage can sneak past isn't safe. Finding that in our own rehearsal — and proving the fix on recorded data — is exactly what chaos engineering is for.
- **Analogy:** A smoke alarm that only goes off after 30 seconds of continuous smoke would miss a fire that flickers; ours now listens to the average.
- **Say it like this:** "Our own rehearsal tricked our safety rule: the damage came in bursts. So we switched to a 30-second average and replayed every recorded run — it now stops both at 31 seconds with zero false alarms on healthy traffic."
- **Likely judge question + our answer:** "Couldn't an average be too slow or too twitchy?" — "We checked against real data: on healthy traffic the worst 30-second average was 572 ms against a 1,034 ms limit, so lots of margin; on both failure runs it fired at 31 seconds — 10 seconds faster than the old rule."
- **Numbers to remember:** rehearsal: 27% peak errors, 8 of 18 bad checks, longest streak 4, no abort · new rule: abort at +31 s on both runs · baseline worst 30 s average 572 ms vs 1,034 ms limit · STOP reacts within ~1 s.
