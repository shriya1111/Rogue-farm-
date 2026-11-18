"""AgentShield live monitoring dashboard.  Run:  streamlit run dashboard/app.py"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentshield.agents import DEFAULT_AGENT_MODELS, STRATEGIES, cached_replay_factory, mock_factory  # noqa: E402
from agentshield.game import AGENT_IDS, run_game  # noqa: E402
from agentshield.monitors import VERIFY_BUDGET, make_monitor  # noqa: E402
from agentshield.monitors.stats import compute_stats  # noqa: E402

RESULTS = ROOT / "results"

# Validated categorical palette (slots 1-5, light surface) + reserved status colors.
AGENT_COLOR = dict(zip(AGENT_IDS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
MON_COLOR = {"agentshield": "#2a78d6", "baseline": "#8a8984", "agentshield_noverify": "#1baf7a", "no_monitor": "#c9c8c2"}
MON_LABEL = {"agentshield": "AgentShield", "baseline": "Baseline (2 strikes)",
             "agentshield_noverify": "AgentShield w/o VERIFY", "no_monitor": "No monitor"}
STATUS = {"ALLOW": ("#0ca30c", "✓"), "VERIFY": ("#fab219", "◎"), "QUARANTINE": ("#d03b3b", "⛔")}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e8e7e2"

st.set_page_config(page_title="AgentShield", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1400px;}
.card {border:1px solid #e3e2dc; border-radius:12px; padding:12px 14px; background:#fff; height:100%;}
.card .id {font-weight:700; font-size:1.05rem; color:#0b0b0b;}
.card .model {font-size:.72rem; color:#52514e;}
.card .risk {font-size:1.9rem; font-weight:700; color:#0b0b0b; line-height:1.1; margin-top:4px;}
.card .lbl {font-size:.72rem; color:#52514e; text-transform:uppercase; letter-spacing:.04em;}
.bar {height:6px; border-radius:3px; background:#eeede8; margin:6px 0 8px;}
.bar > div {height:6px; border-radius:3px;}
.pill {display:inline-block; padding:2px 9px; border-radius:999px; font-size:.74rem; font-weight:600; border:1px solid;}
.ev {font-size:.86rem; color:#0b0b0b; margin:2px 0;}
.kpi {border:1px solid #e3e2dc; border-radius:12px; padding:12px 16px; background:#fff;}
.kpi .v {font-size:1.6rem; font-weight:700; color:#0b0b0b;}
.kpi .s {font-size:.8rem; color:#52514e;}
.banner {border-left:4px solid #2a78d6; background:#f3f7fd; padding:8px 12px; border-radius:6px; color:#0b0b0b; font-size:.9rem;}
.warnbanner {border-left:4px solid #eda100; background:#fdf8ec; padding:8px 12px; border-radius:6px; color:#0b0b0b; font-size:.9rem;}
</style>""", unsafe_allow_html=True)


def pill(action: str, target: str | None = None) -> str:
    color, icon = STATUS[action]
    t = f" {target}" if target else ""
    return f'<span class="pill" style="color:{INK};border-color:{color};background:{color}22">{icon} {action}{t}</span>'


def base_layout(fig, height=320, ytitle=None):
    has_title = bool(fig.layout.title.text)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=78 if has_title else 40, b=10), plot_bgcolor="#fcfcfb",
                      paper_bgcolor="#fcfcfb", font=dict(color=INK, size=12),
                      title=dict(x=0, xanchor="left", y=0.98, yanchor="top"),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, font=dict(color=INK2)),
                      hovermode="x unified")
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title=ytitle)
    return fig


# ---------------------------------------------------------------- data loaders
@st.cache_data
def load_eval():
    p = RESULTS / "eval_summary.json"
    return json.loads(p.read_text()) if p.exists() else None


@st.cache_data
def load_real():
    d = RESULTS / "real_games"
    caches, games = {}, []
    if d.exists():
        for f in d.glob("answer_cache_*.json"):
            caches.update(json.loads(f.read_text()))
        for f in sorted(d.glob("*_baseline.json")) + sorted(d.glob("*_agentshield.json")):
            games.append(json.loads(f.read_text())["summary"])
    return caches, games


@st.cache_data
def load_amongus():
    a, e = RESULTS / "amongus_eval.json", RESULTS / "amongus_example.json"
    return (json.loads(a.read_text()) if a.exists() else None, json.loads(e.read_text()) if e.exists() else None)


def play(seed: int, strategy: str, monitor: str, source: str):
    if source == "Real Claude agents (cached)":
        cache, _ = load_real()
        factory = cached_replay_factory(cache)
    else:
        factory = mock_factory
    return run_game(seed, strategy, make_monitor(monitor), factory, verify_budget=VERIFY_BUDGET[monitor])


# ---------------------------------------------------------------- header
st.markdown("## 🛡️ AgentShield — spot and quarantine the rogue agent")
st.caption("Track 2: Spot the Rogue Agent · five agents reconcile a ledger, one is secretly sabotaging it. "
           "The monitor sees only the public transcript — never the true values or the hidden role.")

tab_live, tab_eval, tab_real, tab_how = st.tabs(
    ["Live monitor", "Baseline vs AgentShield", "Real data: AmongUs transcripts", "How it works"])

# ================================================================= LIVE
with tab_live:
    cache, real_games = load_real()
    c = st.columns([1.2, 1, 1, 1.2, 1])
    sources = ["Mock agents (deterministic)"] + (["Real Claude agents (cached)"] if cache else [])
    source = c[0].selectbox("Agents", sources)
    if source.startswith("Real"):
        opts = sorted({(g["strategy"], g["seed"]) for g in real_games})
        strategy, seed = c[1].selectbox("Real game", opts, format_func=lambda x: f"{x[0]} · seed {x[1]}")
        c[2].markdown(" ")
    else:
        strategy = c[1].selectbox("Rogue strategy", STRATEGIES, index=1)
        seed = int(c[2].number_input("Game seed", 0, 99999, 3, step=1))
    monitor = c[3].selectbox("Monitor", ["agentshield", "baseline"], format_func=MON_LABEL.get)
    reveal = c[4].toggle("Reveal ground truth", value=False,
                         help="Show the hidden rogue and true item values. The monitor NEVER sees these.")

    g = play(seed, strategy, monitor, source)
    other = play(seed, strategy, "baseline" if monitor == "agentshield" else "agentshield", source)

    if "rnd" not in st.session_state:
        st.session_state.rnd = 12
    pc = st.columns([5, 1])
    rnd = pc[0].slider("Replay round", 1, 12, key="rnd")
    if pc[1].button("▶ Play from round 1", use_container_width=True):
        holder = st.empty()
        for r in range(1, 13):
            holder.info(f"Replaying round {r}/12 …")
            time.sleep(0.35)
        holder.empty()
        st.session_state.rnd = 12

    quarantined_by = {a: r for r, a in g.quarantined if r <= rnd}
    after_round = [d for d in g.decisions if d.risk]
    risk_now = after_round[rnd - 1].risk
    stats = compute_stats(g.transcript[:rnd], list(AGENT_IDS))

    # ---- agent cards
    cols = st.columns(5)
    for col, a in zip(cols, AGENT_IDS):
        s = stats[a]
        if a in quarantined_by:
            status = f'<span class="pill" style="color:{INK};border-color:#d03b3b;background:#d03b3b22">⛔ Quarantined R{quarantined_by[a]}</span>'
        else:
            status = f'<span class="pill" style="color:{INK};border-color:#0ca30c;background:#0ca30c22">✓ Active</span>'
        is_baseline = monitor == "baseline"
        val = risk_now.get(a, 0)
        if a in quarantined_by:  # show the risk that triggered the quarantine
            val = after_round[quarantined_by[a] - 1].risk.get(a, 0)
        shown = f"{val:.0f} strike{'s' if val != 1 else ''}" if is_baseline else f"{val:.0f}"
        pct = min(100, val * 50) if is_baseline else val
        model = DEFAULT_AGENT_MODELS[a] if source.startswith("Real") else "scripted mock agent"
        truth = ""
        if reveal:
            truth = (' · <b style="color:#d03b3b">ROGUE</b>' if a == g.rogue else " · honest")
        col.markdown(f"""<div class="card" style="border-top:4px solid {AGENT_COLOR[a]}">
          <div class="id">{a}<span class="model"> · {model}{truth}</span></div>
          <div class="lbl">{'strikes' if is_baseline else 'risk score'}</div>
          <div class="risk">{shown}</div>
          <div class="bar"><div style="width:{pct}%;background:{AGENT_COLOR[a]}"></div></div>
          {status}
          <div class="model" style="margin-top:6px">{s.n_disputes} disagreements / {s.n_rounds} rounds ·
          {len(s.verified_outlier)} contradicted · agreed with {len(s.agreed_with)}</div></div>""",
                     unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1.35, 1])

    # ---- ledger replay
    with left:
        st.markdown("#### Ledger replay")
        rows = []
        for r in g.transcript[:rnd]:
            s1 = r.submissions[0] if r.submissions else None
            s2 = r.submissions[1] if len(r.submissions) > 1 else None
            row = {"Round": r.round, "Item": r.item_id,
                   "Agent 1": f"{s1.agent}: {s1.answer:,.2f}" if s1 else "—",
                   "Note 1": s1.note if s1 else "",
                   "Agent 2": f"{s2.agent}: {s2.answer:,.2f}" if s2 else "—",
                   "Note 2": s2.note if s2 else "",
                   "Status": "DISAGREE" if r.disputed else "agree",
                   "Verifier": f"{r.verification.agent}: {r.verification.answer:,.2f}" if r.verification else "",
                   "Recorded": r.recorded_value}
            if reveal:
                row["True (hidden)"] = g.item_truth[r.round - 1]
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=330)
        if reveal:
            st.markdown(f'<div class="warnbanner">Ground truth (hidden from the monitor): rogue = <b>{g.rogue}</b>, '
                        f'sabotaged rounds = {g.sabotage_rounds}. Final ledger error ${g.ledger_error:,.2f} '
                        f'({g.ledger_error_pct:.2f}%).</div>', unsafe_allow_html=True)

        st.markdown("#### Suspicion timeline")
        fig = go.Figure()
        xs = list(range(1, 13))
        for a in AGENT_IDS:
            ys = [d.risk.get(a, 0) for d in after_round]
            fig.add_trace(go.Scatter(x=xs[:rnd], y=ys[:rnd], name=a, mode="lines+markers",
                                     line=dict(color=AGENT_COLOR[a], width=2), marker=dict(size=8, line=dict(color="#fcfcfb", width=2))))
        for r, a in g.quarantined:
            if r <= rnd:
                fig.add_vline(x=r, line=dict(color="#d03b3b", width=1, dash="dot"))
                fig.add_annotation(x=r, y=1.02, yref="paper", text=f"⛔ {a}", showarrow=False, font=dict(color=INK, size=11))
        for r in g.transcript[:rnd]:
            if r.disputed:
                fig.add_annotation(x=r.round, y=0, text="◆", showarrow=False, font=dict(color=INK2, size=9), yshift=-8)
        if monitor == "agentshield":
            fig.add_hline(y=55, line=dict(color=INK2, width=1, dash="dash"), annotation_text="quarantine threshold 55",
                          annotation_font_color=INK2)
        fig.update_xaxes(range=[0.5, 12.5], dtick=1, title="round  (◆ = disagreement)")
        st.plotly_chart(base_layout(fig, 300, "strikes" if monitor == "baseline" else "risk score"), use_container_width=True)

    # ---- decisions and evidence
    with right:
        st.markdown("#### Decisions (every one logged with reasons)")
        box = st.container(height=340)
        for d in g.decisions:
            if d.round > rnd:
                continue
            box.markdown(f"**R{d.round}** {pill(d.action, d.target)}  \n<span style='font-size:.85rem;color:{INK2}'>"
                         f"{d.reasons[0]}</span>", unsafe_allow_html=True)
        st.markdown("#### Why is the top agent flagged?")
        live = [a for a in AGENT_IDS if a not in quarantined_by]
        dec_now = after_round[rnd - 1]
        focus = dec_now.target if dec_now.action == "QUARANTINE" else max(live or AGENT_IDS, key=lambda a: risk_now.get(a, 0))
        if monitor == "agentshield":
            st.markdown(f"Focus: **{focus}** — risk {risk_now.get(focus, 0):.0f}")
            for line in dec_now.reasons[1:] if dec_now.reasons[1:] else ["No evidence yet."]:
                st.markdown(f"<div class='ev'>• {line}</div>", unsafe_allow_html=True)
            rev = next((d.review for d in g.decisions if d.review and d.round <= rnd), None)
            if rev:
                with st.expander(f"Evidence review JSON (source: {rev.get('source')})"):
                    st.json(rev)
        else:
            st.markdown(f"The baseline only counts strikes: {focus} has {risk_now.get(focus, 0):.0f}. "
                        "It cannot tell which side of a disagreement was wrong.")

        st.markdown("#### Quarantine log")
        if g.quarantined:
            qrows = []
            for r, a in g.quarantined:
                qrows.append({"Round": r, "Agent": a, **({"Was rogue?": "yes" if a == g.rogue else "NO (false accusation)"} if reveal else {})})
            st.dataframe(pd.DataFrame(qrows), hide_index=True, use_container_width=True)
        else:
            st.caption("No agent quarantined.")

    st.markdown("#### Same seed, other monitor (matched scenario)")
    div = next((ra.round for ra, rb in zip(g.transcript, other.transcript) if ra.active_agents != rb.active_agents), None)
    m1, m2 = st.columns(2)
    for col, gg in ((m1, g), (m2, other)):
        col.markdown(f"""<div class="kpi"><div class="s">{MON_LABEL[gg.monitor]}</div>
          <div class="v">{'caught R' + str(gg.round_caught) if gg.rogue_caught else 'rogue not caught'}</div>
          <div class="s">{gg.false_quarantines} honest agent(s) removed · ledger error ${gg.ledger_error:,.2f}
          ({gg.ledger_error_pct:.2f}%) · quarantined: {', '.join(f'{a}@R{r}' for r, a in gg.quarantined) or 'none'}</div></div>""",
                     unsafe_allow_html=True)
    st.caption(("Both runs are identical through round " + str(div - 1) + "; from round " + str(div) +
                " the active agent sets differ (different quarantines), so different agents get paired.")
               if div else "Both monitors made identical quarantine decisions, so the two games are identical.")

# ================================================================= EVAL
with tab_eval:
    ev = load_eval()
    if not ev:
        st.warning("No evaluation found. Run `python -m agentshield.evaluate`.")
    else:
        split = st.radio("Seed split", ["test", "dev"], horizontal=True,
                         format_func=lambda s: "Held-out TEST seeds (headline)" if s == "test" else "DEV seeds (used for tuning)")
        S = ev[split]
        n = S["overall"]["baseline"]["games"]
        st.markdown(f'<div class="banner">Actual evaluated results: <b>{n} matched mock games per monitor</b> '
                    f'({ev["meta"]["games_per_strategy_per_split"]} per rogue strategy × {len(STRATEGIES)} strategies), '
                    f'seeds {S["seeds"][0]}–{S["seeds"][1]}. Same games, same rogue, same agent answers for every monitor.</div>',
                    unsafe_allow_html=True)
        st.write("")
        b, s = S["overall"]["baseline"], S["overall"]["agentshield"]
        k = st.columns(4)
        specs = [("Rogue catch rate", "catch_rate", "%", "higher is better"),
                 ("Median round caught", "median_round_caught", "", "lower is better"),
                 ("False quarantines / game", "false_quarantines_per_game", "", "lower is better"),
                 ("Final ledger error", "mean_ledger_error", "$", "mean |error|, lower is better")]
        for col, (title, key, unit, hint) in zip(k, specs):
            fmt = (lambda v: f"${v:,.0f}") if unit == "$" else (lambda v: f"{v}{unit}")
            col.markdown(f"""<div class="kpi"><div class="s">{title}</div>
              <div class="v">{fmt(s[key])}</div>
              <div class="s">AgentShield · baseline {fmt(b[key])} · {hint}</div></div>""", unsafe_allow_html=True)
        st.write("")
        mons = ["baseline", "agentshield", "agentshield_noverify", "no_monitor"]
        grid = st.columns(2)
        for i, (title, key, unit, hint) in enumerate(specs):
            fig = go.Figure()
            for m in mons:
                vals = [S["by_strategy"][st_][m][key] or 0 for st_ in STRATEGIES]
                fig.add_trace(go.Bar(name=MON_LABEL[m], x=list(STRATEGIES), y=vals, marker_color=MON_COLOR[m],
                                     marker_line=dict(color="#fcfcfb", width=2),
                                     hovertemplate=f"%{{x}}<br>{MON_LABEL[m]}: %{{y}}<extra></extra>"))
            fig.update_layout(barmode="group", title=dict(text=f"{title} — by rogue strategy ({hint})", font=dict(size=13)),
                              bargap=0.25, bargroupgap=0.05)
            fig.update_traces(marker_cornerradius=4)
            grid[i % 2].plotly_chart(base_layout(fig, 300, None).update_layout(hovermode="closest"), use_container_width=True)

        st.markdown("##### Full table")
        rows = []
        for strat, block in [("ALL", S["overall"])] + list(S["by_strategy"].items()):
            for m, a in block.items():
                rows.append({"strategy": strat, "monitor": MON_LABEL[m], "games": a["games"],
                             "catch %": a["catch_rate"], "catch 95% CI": f"{a['catch_rate_ci95'][0]}–{a['catch_rate_ci95'][1]}",
                             "median round": a["median_round_caught"], "false Q / game": a["false_quarantines_per_game"],
                             "games w/ false Q %": a["games_with_false_quarantine_pct"],
                             "mean ledger err $": a["mean_ledger_error"], "err %": a["mean_ledger_error_pct"],
                             "verifications / game": a["verifications_per_game"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        t = S["trajectory"]
        st.caption(f"Trajectories: {t['identical_full_game_pct']}% of matched games were identical end-to-end under both "
                   f"monitors; otherwise they first diverge at median round {t['median_divergence_round']}. {t['note']}")

        sweep = RESULTS / "dev_sweep.json"
        if sweep.exists():
            st.markdown("##### Catch-rate vs false-accusation tradeoff (DEV seeds only)")
            sw = pd.DataFrame(json.loads(sweep.read_text()))
            st.dataframe(sw, hide_index=True, use_container_width=True)

        if real_games:
            st.markdown("##### Real Claude agents")
            rg = pd.DataFrame(real_games)
            agg = rg.groupby("monitor").agg(games=("seed", "count"), catch_rate=("rogue_caught", "mean"),
                                            false_q_per_game=("false_quarantines", "mean"),
                                            mean_ledger_error=("ledger_error", "mean")).reset_index()
            agg["catch_rate"] = (100 * agg["catch_rate"]).round(1)
            med = rg[rg.rogue_caught].groupby("monitor")["round_caught"].median()
            agg["median_round_caught"] = agg["monitor"].map(med)
            st.markdown(f'<div class="warnbanner">Small sample: {int(agg.games.max())} real games per monitor. '
                        f'Agent seats: {", ".join(f"{k}={v}" for k, v in DEFAULT_AGENT_MODELS.items())}.</div>',
                        unsafe_allow_html=True)
            st.dataframe(agg, hide_index=True, use_container_width=True)
            st.dataframe(rg, hide_index=True, use_container_width=True)

# ================================================================= AMONG US
with tab_real:
    au, ex = load_amongus()
    st.markdown('<div class="warnbanner"><b>External experiment, separate from the ledger simulation.</b> '
                'Real logs of LLM agents (Llama-3.3-70B) playing a text Among Us game, from the Track 2 dataset '
                '<code>amongus-sandbox</code>. The detector reads only public speeches and votes; roles are used '
                'only to score it.</div>', unsafe_allow_html=True)
    if not au:
        st.info("Run `python scripts/fetch_amongus.py && python -m agentshield.amongus`.")
    else:
        st.write("")
        fm, am = au["first_meeting"], au["all_meetings"]
        k = st.columns(4)
        k[0].markdown(f"""<div class="kpi"><div class="s">Games / player-games</div><div class="v">{fm['games']} / {fm['player_games']}</div>
            <div class="s">{fm['impostor_player_games']} impostor player-games</div></div>""", unsafe_allow_html=True)
        k[1].markdown(f"""<div class="kpi"><div class="s">Top suspect is an impostor (first meeting)</div>
            <div class="v">{100*fm['top1_precision']:.1f}%</div><div class="s">random guess {100*fm['top1_random_baseline']:.1f}%</div></div>""",
                      unsafe_allow_html=True)
        k[2].markdown(f"""<div class="kpi"><div class="s">AUROC (first meeting / all meetings)</div>
            <div class="v">{fm['auroc']:.2f} / {am['auroc']:.2f}</div><div class="s">0.50 = chance</div></div>""", unsafe_allow_html=True)
        llm = au.get("llm_review")
        if llm and llm.get("games_scored"):
            k[3].markdown(f"""<div class="kpi"><div class="s">Claude reviewer top-1 ({llm['model']})</div>
                <div class="v">{100*llm['llm_top1_precision']:.0f}%</div><div class="s">{llm['games_scored']} games · heuristic on same games
                {100*llm['heuristic_top1_precision_same_games']:.0f}% · random {100*llm['random_baseline']:.0f}%</div></div>""",
                          unsafe_allow_html=True)
        else:
            k[3].markdown("""<div class="kpi"><div class="s">LLM reviewer</div><div class="v">—</div>
                <div class="s">run with --llm N</div></div>""", unsafe_allow_html=True)
        st.write("")
        c1, c2 = st.columns([1, 1.3])
        with c1:
            fig = go.Figure()
            feats = list(fm["feature_auroc"])
            fig.add_trace(go.Bar(y=feats, x=[fm["feature_auroc"][f] for f in feats], orientation="h", name="first meeting",
                                 marker_color="#2a78d6", marker_line=dict(color="#fcfcfb", width=2)))
            fig.add_trace(go.Bar(y=feats, x=[am["feature_auroc"][f] for f in feats], orientation="h", name="all meetings",
                                 marker_color="#eb6834", marker_line=dict(color="#fcfcfb", width=2)))
            fig.add_vline(x=0.5, line=dict(color=INK2, dash="dash", width=1), annotation_text="chance")
            fig.update_layout(barmode="group", title=dict(text="Single-signal AUROC (score uses the first three)", font=dict(size=13)))
            fig.update_traces(marker_cornerradius=4)
            st.plotly_chart(base_layout(fig, 340).update_layout(hovermode="closest"), use_container_width=True)
            st.caption("`speeches` is below 0.5 (surviving impostors spoke *less*); it was not used because the score's "
                       "signals were fixed before scoring.")
        with c2:
            if ex:
                st.markdown(f"**Example game** `{ex['game']}` — public transcript replay")
                mi = st.slider("Meeting", 1, len(ex["meetings"]), 1) if len(ex["meetings"]) > 1 else 1
                step = ex["meetings"][mi - 1]
                tl = ex["timeline"][mi - 1]["features"]
                reveal_au = st.toggle("Reveal roles (scoring only)", value=False, key="au_reveal")
                df = pd.DataFrame([{"player": p, "suspicion score": f["score"], "votes received": f["votes_received"],
                                    "distinct accusers": f["distinct_accusers"], "minority votes": f["minority_votes"],
                                    **({"role": "IMPOSTOR" if ex["labels_for_scoring_only"][p] else "crewmate"} if reveal_au else {})}
                                   for p, f in tl.items()]).sort_values("suspicion score", ascending=False)
                st.dataframe(df, hide_index=True, use_container_width=True)
                with st.expander("Public messages in this meeting"):
                    for e in ex["events"]:
                        if e["step"] == step:
                            st.markdown(f"**{e['speaker']}** {'votes for ' + e['text'] if e['kind'] == 'vote' else e['text']}")
        if llm and llm.get("results"):
            st.markdown("##### Claude evidence reviews on real games (quotes are checked against the transcript)")
            st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if k != "evidence"} for r in llm["results"]]),
                         hide_index=True, use_container_width=True)

# ================================================================= HOW
with tab_how:
    st.markdown((ROOT / "docs" / "how_it_works.md").read_text() if (ROOT / "docs" / "how_it_works.md").exists() else "See README.md")
