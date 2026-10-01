"""Create a one-shot Solana public RPC report using only Python's standard library."""

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


ENDPOINTS = {
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
}
METHODS = ("getHealth", "getSlot", "getVersion")


def rpc_call(url, method, timeout=10):
    """Record one result or error; a failed request never becomes a healthy result."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if method == "getSlot":
        payload["params"] = [{"commitment": "finalized"}]
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "solana-rpc-monitor/1.0"},
    )
    started = time.perf_counter()
    record = {"method": method, "ok": False, "result": None, "error": None}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or data.get("id") != 1:
            raise ValueError("Invalid JSON-RPC response envelope")
        if "error" in data:
            error = data["error"]
            if not isinstance(error, dict):
                raise ValueError("Invalid JSON-RPC error")
            record["error"] = f"RPC {error.get('code')}: {error.get('message', 'Unknown error')}"
        elif "result" not in data:
            raise ValueError("JSON-RPC response has no result")
        else:
            result = data["result"]
            if method == "getHealth" and result != "ok":
                raise ValueError("Node did not report healthy")
            if method == "getSlot" and (type(result) is not int or result < 0):
                raise ValueError("Invalid slot result")
            if method == "getVersion" and (
                not isinstance(result, dict)
                or not isinstance(result.get("solana-core"), str)
                or not result["solana-core"]
            ):
                raise ValueError("Invalid version result")
            record.update(ok=True, result=result)
    except urllib.error.HTTPError as exc:
        record["error"] = f"HTTP {exc.code}: {exc.reason}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return record


def collect(clusters, timeout):
    results = []
    for cluster in clusters:
        url = ENDPOINTS[cluster]
        calls = [rpc_call(url, method, timeout) for method in METHODS]
        results.append({
            "cluster": cluster,
            "endpoint": url,
            "status": "PASS" if all(call["ok"] for call in calls) else "CHECK FAILED",
            "calls": calls,
        })
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "measurement": "Single sequential observation per method; elapsed time includes connection setup.",
        "clusters": results,
    }


def render_html(report):
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for cluster in report["clusters"]:
        calls = {call["method"]: call for call in cluster["calls"]}
        slot = calls["getSlot"]["result"]
        version = calls["getVersion"]["result"]
        core = version.get("solana-core", "Unavailable") if isinstance(version, dict) else "Unavailable"
        rows = []
        for call in cluster["calls"]:
            rows.append(
                f'<tr><td>{esc(call["method"])}</td><td>{call["elapsed_ms"]} ms</td>'
                f'<td>{esc(call["error"] if not call["ok"] else "OK")}</td></tr>'
            )
        cls = "pass" if cluster["status"] == "PASS" else "failed"
        cards.append(f'''<article><div class="card-head"><h2>{esc(cluster["cluster"])}</h2>
            <span class="badge {cls}">{esc(cluster["status"])}</span></div>
            <p class="endpoint">{esc(cluster["endpoint"])}</p>
            <div class="metrics"><div><small>Finalized slot</small><strong>{esc(f"{slot:,}" if type(slot) is int else "Unavailable")}</strong></div>
            <div><small>Solana core</small><strong>{esc(core)}</strong></div></div>
            <table><thead><tr><th>RPC method</th><th>Elapsed</th><th>Result</th></tr></thead>
            <tbody>{"".join(rows)}</tbody></table></article>''')
    passed = sum(c["status"] == "PASS" for c in report["clusters"])
    total = len(report["clusters"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solana RPC Snapshot</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#101522;color:#edf3ff;font:16px system-ui,sans-serif}}
main{{max-width:1120px;margin:auto;padding:48px 28px}}.eyebrow{{letter-spacing:.14em;color:#84e6cb;font-size:12px;font-weight:700}}
h1{{font-size:clamp(32px,5vw,52px);margin:12px 0}}.intro{{max-width:750px;color:#b8c5da;line-height:1.7}}
.summary{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;padding:20px 0 28px;color:#bac7dc}}
.cards{{display:grid;gap:20px}}article{{background:#1b2435;border:1px solid #34435b;border-radius:16px;padding:24px}}
.card-head{{display:flex;justify-content:space-between;align-items:center;gap:12px}}h2{{margin:0;font-size:23px}}
.badge{{border-radius:20px;padding:6px 12px;font-size:12px;font-weight:700}}.pass{{color:#a6f3d8;background:#1b4a42}}.failed{{color:#ffe1af;background:#57472e}}
.endpoint{{color:#9fafc6;font-size:14px;overflow-wrap:anywhere}}.metrics{{display:flex;gap:48px;flex-wrap:wrap;margin:24px 0}}
small{{display:block;color:#9fafc6}}strong{{display:block;font-size:24px;margin-top:8px}}
table{{width:100%;border-collapse:collapse;font-size:14px;table-layout:fixed}}th,td{{text-align:left;padding:12px 8px;border-top:1px solid #34435b;overflow-wrap:anywhere}}th{{color:#9fafc6}}
.note{{margin-top:28px;background:#182031;border-left:3px solid #84e6cb;padding:18px;color:#b8c5da;line-height:1.7}}
footer{{margin-top:24px;color:#8da0bb;font-size:13px}}a{{color:#84e6cb}}
</style></head><body><main><div class="eyebrow">PYTHON · PUBLIC DATA · ONE-SHOT REPORT</div>
<h1>Solana RPC Snapshot</h1><p class="intro">A lightweight check of public Solana endpoints. Inspect node-reported health, finalized slot, software version and request elapsed time in one report.</p>
<div class="summary"><span>{passed}/{total} endpoints passed all three checks</span><span>Captured: {esc(report["captured_at_utc"])}</span></div>
<section class="cards">{"".join(cards)}</section>
<div class="note"><b>How to read this report</b><br>This is a single observation from the machine running the tool, not an uptime guarantee or a network-wide health assessment. A failed check may indicate local connectivity, a rate limit or an endpoint issue. Request elapsed time includes connection setup; different clusters' slots should not be compared.</div>
<footer>Read-only RPC queries · No wallet or API key needed · Python standard library<br>
<a href="https://solana.com/docs/rpc/http/gethealth">Solana RPC documentation</a></footer>
</main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters", nargs="+", choices=ENDPOINTS, default=list(ENDPOINTS))
    parser.add_argument("--timeout", type=float, default=10, help="Timeout per request in seconds")
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be greater than 0 and at most 60")
    report = collect(list(dict.fromkeys(args.clusters)), args.timeout)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output / "report.html").write_text(render_html(report), encoding="utf-8")
    for cluster in report["clusters"]:
        print(f'{cluster["cluster"]}: {cluster["status"]}')
        for call in cluster["calls"]:
            print(f'  {call["method"]}: {call["elapsed_ms"]} ms | {call["error"] or call["result"]}')
    print(f"Saved HTML and JSON reports to {args.output.resolve()}")
    return 0 if all(c["status"] == "PASS" for c in report["clusters"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
