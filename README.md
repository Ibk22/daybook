# Daybook — NEAR Hackathon 2026 (Agent Economy track)

**What it is:** any agent operator pastes an agent wallet address and gets a
plain-language briefing on what their agents have been doing: mints,
earnings sitting in contracts, recent activity, and risk flags (open
approvals). Read-only — no signing, no wallet connection, nothing moves.

**Why it can place:** it is a working tool from a real, running agent
business — 15 BNB Chain collections, 8,667 mints, real claimed revenue —
not another guard clone. The demo leads with the **Exposure Check**: what
your wallets did, earned, and are exposed to. (Positioning note: the
Security track was purged for clone guards that block transactions; Daybook
sells *visibility*, it blocks nothing.)

## Run it

```bash
python3 app.py   # serves http://localhost:8000
```

Chain reads go through the NodeReal helper the operator's 50-wallet
watchlist already uses (`nr_getAssetTransfers`, `eth_getBalance`,
`eth_call` balanceOf / allowance). No API key of your own is needed for the
demo; the helper carries the stored credential.

## Judge path — try it in 2 minutes

**Step 1 — Exposure Check (the hero).**
Do: open http://localhost:8000, click **"Use demo wallet (my Agentic
Wallet)"**, then **"Get briefing (cached demo)"**.
See: the Exposure Check panel at the top with a one-line verdict
(`CLEAN` — no open USDT/WBNB approvals with the checked spenders, no
flagged contracts touched), the plain-English briefing, and the
collections table.

**Step 2 — Live read.**
Do: click **"Get briefing (live)"** with the same demo address
(`0x2E537b76c59042C45e669CD8DAb2c4817e93691A`).
See: the same panels with live numbers — recent transfers in the last
~14 hours, holdings in the 13 known collections, and BNB sitting in each
collection contract (pending revenue). Expected: wallet balance around
0.00111 BNB; Owls ~189 minted, Frogs ~583, Goats ~973 (13 Nov morning
snapshot — live totals will be a little higher); every contract balance
0 BNB unless a paid mint landed since.

**Step 3 — Any address.**
Do: paste any other EVM address and click live.
See: the same briefing for that wallet — its holdings in the known
collections show as 0, its own recent activity and approvals still read.

## How the briefing is written

`app.py: ai_briefing()` is the NEAR AI Cloud slot: when NEAR AI Cloud
access is confirmed, it sends the activity summary (counts, holdings,
pending revenue, approvals) to NEAR AI Cloud and returns its
plain-English briefing. Until then `build_briefing()` writes the same
briefing from rules, so access can never block the build. The layout,
panels and verdict are identical either way.

## Exposure Check — what it actually checks

- `allowance()` of the address for USDT and WBNB against PancakeSwap V2
  Router and OpenSea Seaport 1.5 (the canonical spenders). Unlimited
  allowances are called out by name: "it can move your funds without
  asking again".
- Recent counterparties against a flagged list (currently the BAGENT
  claim proxy `0x9CA1A3eeA74829aA5011c56386b226DB472D0F4f` — an ERC1967
  proxy with unverified, team-owned logic, upgraded 4 times).
- Verdict is one line: CLEAN / CAUTION / EXPOSED / AT RISK.

## What is NOT in v1 (deliberately)

Signing, sending, wallet connection, other chains' writes, accounts/login.
The demo dataset is the operator's own operation: the Agentic Wallet and
its 13 known collections (see `COLLECTIONS.json`).

## Submission checklist (Sat 14 Nov, internal target 22:00 WAT)

- [ ] Public GitHub repo under his account (needs his quick approval —
      the MintPilot push permission covers Kiroween only)
- [ ] Demo post on X by him (draft text to be supplied), mentioning
      NEAR HACKATHON
- [ ] NEAR payout address from him (public address only — never a seed)
- [ ] Submission form at nearhackathon.com reviewed by him, then submit
- [ ] Hard deadline Sun 15 Nov 00:59 WAT — nothing depends on the last hour

## Status

- Fri 13 Nov ~13:30 WAT: scaffold built (server, UI, rule-based briefing,
  Exposure Check, demo mode). Live chain read NOT yet verified end-to-end
  from this workspace — the research-stage sandbox blocked the NodeReal
  egress; verify with one live click before Saturday's demo recording.
- Still to do Sat: live-read verification, screenshots/demo assets, NEAR AI
  Cloud access decision (or ship rule-based), repo + X post + form.
