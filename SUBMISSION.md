# Submission

## Team card

**Team name:** AgentShield

**Statement number** (the card your corner wrote): _fill in from your corner's card_

**First names:** Shriya

**Statement:** How might we help **teams that deploy multi-agent AI workflows** do **catch and cut off a compromised
or misbehaving agent in real time** so that **one bad agent cannot quietly corrupt shared work, and honest agents are not
thrown out by mistake**? Build idea: **A (build a better monitor)**. We'll know it worked if **on the same games, it
removes far fewer honest agents than the official two-strike baseline and leaves a much more accurate ledger, while still
catching most rogues.**

## Six short answers

**1. The concern:** A finance team runs five AI agents that reconcile invoices. One agent is compromised and nudges
totals by a few percent with a plausible note ("minor rounding adjustment applied"). Nobody notices until the books are off.
And when someone does notice, the naive fix (remove every agent that is ever wrong) throws out the honest agents too.

**2. What we built,** and the one command that runs it: AgentShield, a live monitor for a five-agent ledger team. It
reads only the public transcript and tracks simple behavioral signals: disagreements, distinct partners, direction of
errors, over-assertive notes. It asks a third agent to redo a disputed item (VERIFY), gets an optional Claude review
with validated citations, and quarantines only on hard evidence, logging its reasons. It includes the official
two-strike baseline, a matched-scenario evaluator, a Streamlit dashboard, and a real-transcript experiment.
`python run_demo.py`

**3. Data we used:** `amongus-sandbox`: 200 game logs (2 of the 4 published experiments, dated 2025-02-01), 15,000+
agent-step rows, 169 games / 959 player-games with at least one meeting. `agentic-misalignment` was inspected; it has no
published transcripts. Plus 1,600 seeded mock ledger games per monitor (800 DEV + 800 TEST) and 20 real games with five
different Claude models as agents.

**4. What it found:** On 800 held-out matched mock games, AgentShield made **0.19 false quarantines per game vs 1.91** for
the two-strike baseline, with final ledger error **$93 vs $552** and catch rate **80.5% vs 90.0%**. In 20 real Claude games:
**0.95 vs 3.15** false quarantines per game, ledger error **$113 vs $1,699**, catch rate 60% vs 95%. On real AmongUs logs,
public speech and votes alone pick an impostor as the top suspect **67.5% of the time vs 33.4% by chance** (169 games,
first meeting). A Claude reviewer did so in 80% of 30 games.

**5. One honest limitation:** Patient rogues still slip through. Intermittent and delayed saboteurs are caught only
60–67% of the time. In real games, a rogue that invented plausible policy excuses for tiny deviations got away, and the
monitor removed a genuinely unreliable honest agent instead. The ledger game is a toy, and 20 real games is a small sample.

**6. If this were deployed and it failed,** who is accountable, and how would they find out? The team that deploys the
agent workflow owns the monitor's thresholds and every quarantine. Each decision is logged with its evidence, so a
human reviewer can audit it. Failures show up in two places. Missed sabotage appears as ledger drift at
reconciliation against bank or source records. A wrong quarantine appears as a flagged agent whose verified answers
were in fact consistent. Both are reviewable in the decision log. Quarantine should be reversible by a human.

## Demo (3 minutes)
See [docs/DEMO.md](docs/DEMO.md).
