#!/usr/bin/env python3
"""Daybook — NEAR Hackathon 2026, Agent Economy track.

Paste an agent wallet address, get a plain-language briefing on what that
agent has been doing: mints, earnings sitting in its contracts, recent
activity, and risk flags (open approvals). Read-only: no signing, no wallet
connection, nothing moves.

Data: live public BNB Chain reads through a small NodeReal RPC helper
(`nodereal_rpc.py`, exposing `call(method, params)`). Point the
NODEREAL_HELPER_DIR environment variable at the folder containing it;
without it, live mode reports itself unavailable and demo mode still
works:
  - nr_getAssetTransfers for recent activity
  - eth_getBalance for the wallet and for each known collection contract
    (earnings sitting in contracts = pending revenue)
  - eth_call balanceOf for the wallet's holdings in each known collection
  - eth_call allowance for open token approvals (Exposure Check)

AI briefing: the briefing text is produced by `build_briefing()` — a
rule-based writer today. The NEAR AI Cloud slot is `ai_briefing()`:
when NEAR AI Cloud access is confirmed, that function sends the same
activity summary to NEAR AI Cloud and returns its plain-English briefing;
until then the rule-based text ships so access can never block the build.

Run:  python3 app.py            # serves http://localhost:8000
API:  GET /api/briefing?address=0x...        (live chain read)
      GET /api/briefing?address=0x...&mode=demo   (cached 13 Nov snapshot,
      labelled as cached — for judging the layout when the chain is slow)
"""
import json
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
_HELPER_DIR = os.environ.get("NODEREAL_HELPER_DIR", "")
if _HELPER_DIR:
    sys.path.insert(0, _HELPER_DIR)

with open(os.path.join(BASE, "COLLECTIONS.json")) as f:
    CONFIG = json.load(f)

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
DEMO_ADDRESS = CONFIG["demo_address"].lower()

# eth_call selectors
BALANCE_OF = "0x70a08231"   # balanceOf(address)
ALLOWANCE = "0xdd62ed3e"    # allowance(owner, spender)
TOTAL_SUPPLY = "0x18160ddd"


def _pad(addr):
    return "000000000000000000000000" + addr[2:].lower()


def _node_call(method, params):
    try:
        from nodereal_rpc import call
    except ImportError:
        raise RuntimeError(
            "live chain read is not configured in this copy — set "
            "NODEREAL_HELPER_DIR to a folder containing nodereal_rpc.py, "
            "or use demo mode")
    return call(method, params)


def _eth_call(to, data):
    res = _node_call("eth_call", [{"to": to, "data": data}, "latest"])
    return res.get("result") or "0x0"


def _int(hexstr):
    try:
        return int(hexstr, 16)
    except (TypeError, ValueError):
        return 0


def live_read(address):
    """One live pass over the chain. Returns the raw activity summary."""
    latest = _int(_node_call("eth_blockNumber", [])["result"])
    from_block = latest - 20000  # ~14 hours of BSC blocks

    transfers = []
    for direction in ("toAddress", "fromAddress"):
        page_key = ""
        for _ in range(3):
            params = {
                "fromBlock": hex(from_block), "toBlock": hex(latest),
                direction: address,
                "category": ["20", "721", "1155"],
                "maxCount": "0x64", "order": "desc", "excludeZeroValue": True,
            }
            if page_key:
                params["pageKey"] = page_key
            res = _node_call("nr_getAssetTransfers", [params]).get("result") or {}
            batch = res.get("transfers", [])
            for t in batch:
                transfers.append({
                    "contract": (t.get("contractAddress") or "").lower(),
                    "category": t.get("category"),
                    "from": (t.get("from") or "").lower(),
                    "to": (t.get("to") or "").lower(),
                    "value": t.get("value"),
                    "token_id": t.get("tokenId"),
                    "block": t.get("blockNum"),
                    "tx": t.get("hash"),
                    "direction": "in" if direction == "toAddress" else "out",
                })
            page_key = res.get("pageKey") or ""
            if not page_key:
                break

    wallet_bnb_wei = _int(_node_call(
        "eth_getBalance", [address, "latest"])["result"])

    holdings = []
    pending_wei = 0
    for c in CONFIG["collections"]:
        addr = c["address"]
        held = _int(_eth_call(addr, BALANCE_OF + _pad(address)))
        minted = _int(_eth_call(addr, TOTAL_SUPPLY))
        contract_bnb = _int(_node_call(
            "eth_getBalance", [addr, "latest"])["result"])
        pending_wei += contract_bnb
        holdings.append({
            "name": c["name"], "symbol": c["symbol"], "address": addr,
            "held": held, "minted": minted,
            "contract_bnb_wei": contract_bnb,
        })

    approvals = []
    for tok in CONFIG["allowance_tokens"]:
        for spender in CONFIG["allowance_spenders"]:
            allowed = _int(_eth_call(
                tok["address"], ALLOWANCE + _pad(address) + _pad(spender["address"])))
            if allowed > 0:
                approvals.append({
                    "token": tok["symbol"], "token_address": tok["address"],
                    "spender": spender["name"], "spender_address": spender["address"],
                    "allowance_raw": str(allowed),
                    "unlimited": allowed >= 2 ** 255,
                })

    flagged = set()
    for t in transfers:
        for bad in CONFIG["flagged_counterparties"]:
            if t["contract"] == bad["address"].lower() or \
                    t["from"] == bad["address"].lower() or \
                    t["to"] == bad["address"].lower():
                flagged.add(bad["address"].lower())

    return {
        "address": address, "block": latest,
        "wallet_bnb_wei": wallet_bnb_wei,
        "transfers": transfers,
        "holdings": holdings,
        "pending_wei": pending_wei,
        "approvals": approvals,
        "flagged": sorted(flagged),
    }


def ai_briefing(summary):
    """NEAR AI Cloud slot.

    When NEAR AI Cloud access is confirmed, replace this body with a call
    that sends `summary` (activity counts, holdings, pending revenue,
    approvals) to NEAR AI Cloud and returns its plain-English briefing.
    The rule-based text below is the fallback and stays as the offline path.
    """
    return None  # not connected yet — build_briefing() falls back


def build_briefing(summary):
    """Rule-based plain-English briefing from the activity summary."""
    ai = ai_briefing(summary)
    if ai:
        return ai

    transfers = summary["transfers"]
    ins = [t for t in transfers if t["direction"] == "in"]
    outs = [t for t in transfers if t["direction"] == "out"]
    held = [h for h in summary["holdings"] if h["held"] > 0]
    pending_bnb = summary["pending_wei"] / 1e18
    lines = []
    lines.append(
        "In the last ~14 hours this wallet received %d transfer(s) and sent %d."
        % (len(ins), len(outs)))
    if held:
        lines.append("It holds %d NFT(s) across %d of your known collections: %s."
                     % (sum(h["held"] for h in held), len(held),
                        ", ".join("%s #%s" % (h["symbol"], h["held"]) for h in held)))
    else:
        lines.append("It holds none of your known collections right now.")
    if pending_bnb > 0:
        lines.append("There is %.4f BNB of paid-mint revenue sitting in your "
                     "collection contracts, waiting to be withdrawn." % pending_bnb)
    else:
        lines.append("No paid-mint revenue is sitting in your collection "
                     "contracts right now — every contract balance is 0.")
    if summary["approvals"]:
        lines.append("Exposure: %d open token approval(s). See the Exposure "
                     "Check panel — one of them may let a contract move funds "
                     "without asking again." % len(summary["approvals"]))
    else:
        lines.append("Exposure: no open token approvals found for USDT or "
                     "WBNB with the checked spenders. That is the safe state.")
    if summary["flagged"]:
        lines.append("Warning: this wallet has touched %d flagged contract(s) "
                     "in the window. Check the flagged list before trusting "
                     "anything connected to them." % len(summary["flagged"]))
    return " ".join(lines)


def verdict(summary):
    """One-line Exposure Check verdict."""
    if summary["flagged"]:
        return ("AT RISK — this wallet touched a flagged contract. "
                "Do not approve anything new until you have checked it.")
    if summary["approvals"]:
        unlimited = [a for a in summary["approvals"] if a["unlimited"]]
        if unlimited:
            return ("EXPOSED — %d unlimited approval(s) open. A contract can "
                    "move your %s without asking again. Revoke what you do "
                    "not need." % (len(unlimited), ", ".join(
                        sorted({a['token'] for a in unlimited}))))
        return ("CAUTION — %d limited approval(s) open. Nothing unlimited, "
                "but each one is still permission you granted."
                % len(summary["approvals"]))
    return ("CLEAN — no open USDT/WBNB approvals with the checked spenders, "
            "and no flagged contracts touched.")


def briefing_response(address, mode):
    if mode == "demo":
        snap = CONFIG["cached_demo_snapshot"]
        summary = {
            "address": address, "block": None,
            "wallet_bnb_wei": int(snap["wallet_bnb"] * 1e18),
            "transfers": [],
            "holdings": [
                {"name": c["name"], "symbol": c["symbol"],
                 "address": c["address"], "held": None,
                 "minted": snap["totals_minted"].get(c["symbol"]),
                 "contract_bnb_wei": 0}
                for c in CONFIG["collections"]
            ],
            "pending_wei": int(snap["contract_balances_bnb"] * 1e18),
            "approvals": [],
            "flagged": [],
            "demo": True,
            "demo_as_of": snap["as_of"],
            "demo_note": snap["note"],
        }
        briefing = ("Demo mode — cached snapshot from the 13 Nov morning "
                    "briefing, not a live chain read. Owls 189 minted, "
                    "Frogs 583, Goats 973. No paid-mint revenue sitting in "
                    "contracts (all balances 0 BNB). Wallet 0.00111 BNB. "
                    "Use the live button for current numbers.")
    else:
        summary = live_read(address)
        briefing = build_briefing(summary)
    summary["briefing"] = briefing
    summary["verdict"] = verdict(summary)
    summary["flagged_details"] = [
        b for b in CONFIG["flagged_counterparties"]
        if b["address"].lower() in summary["flagged"]
    ]
    return summary


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/briefing":
            qs = parse_qs(parsed.query)
            address = (qs.get("address") or [""])[0].strip()
            mode = (qs.get("mode") or ["live"])[0].strip()
            if not ADDR_RE.match(address):
                return self._json(400, {"error": "Not a valid EVM address."})
            try:
                data = briefing_response(address.lower(), mode)
            except Exception as exc:  # chain read failed — say so plainly
                return self._json(502, {
                    "error": "Live chain read failed: %s" % exc,
                    "hint": "Try ?mode=demo for the cached snapshot, or retry.",
                })
            return self._json(200, data)
        return super().do_GET()

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    os.chdir(BASE)
    port = int(os.environ.get("PORT", "8000"))
    print("Daybook on http://localhost:%d — demo: %s" % (port, DEMO_ADDRESS))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
