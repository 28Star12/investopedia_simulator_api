"""Local read-only web dashboard for the market event archive.

Run with: python market_dashboard.py
The server binds to loopback only by default and exposes GET endpoints only.
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from market_event_store import MarketEventStore


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Read-only Market Monitor</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color:#e8edf5;background:#0b1020}
*{box-sizing:border-box}body{margin:0}header{padding:28px max(22px,calc((100vw - 1120px)/2));background:#111a30;border-bottom:1px solid #26334d}
h1{margin:0 0 7px;font-size:clamp(24px,4vw,34px)}.sub,.muted{color:#9eacc3}.wrap{max-width:1120px;margin:auto;padding:24px 20px}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}input,select,button{font:inherit;border-radius:9px;border:1px solid #34435f;padding:10px 12px;background:#121c32;color:#edf3ff}
input{min-width:170px}button{cursor:pointer;background:#263d65}button:hover{background:#345486}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}.stat{background:#121c32;border:1px solid #26334d;border-radius:12px;padding:14px 18px;min-width:150px}.stat strong{display:block;font-size:23px;margin-top:4px}
#status{margin:12px 0;color:#9eacc3}.event{background:#121a2d;border:1px solid #26334d;border-radius:12px;padding:17px;margin:12px 0}
.event h2{font-size:17px;margin:0 0 8px}.event h2 a{color:#dce9ff;text-decoration:none}.event h2 a:hover{text-decoration:underline}
.meta{font-size:12px;color:#9eacc3;display:flex;gap:12px;flex-wrap:wrap;margin-bottom:9px}.summary{color:#c2ccdc;line-height:1.5;white-space:pre-wrap}
.tag{display:inline-block;background:#233653;color:#cfe0ff;border-radius:20px;padding:3px 8px;font-size:11px;margin:3px 4px 0 0}
.empty{padding:36px;text-align:center;border:1px dashed #34435f;border-radius:12px;color:#9eacc3}
footer{color:#7e8ca4;font-size:12px;padding:24px 0;text-align:center}
@media(max-width:600px){.controls>*{width:100%}.stat{flex:1}}
</style>
</head>
<body>
<header><h1>Market Monitor</h1><div class="sub">Public market news archive · Read-only research · No trading</div></header>
<main class="wrap">
<div class="controls">
<input id="symbol" maxlength="12" placeholder="Filter symbol (e.g. AAPL)" aria-label="Filter by symbol">
<select id="limit" aria-label="Number of events"><option value="25">Latest 25</option><option value="50" selected>Latest 50</option><option value="100">Latest 100</option><option value="250">Latest 250</option></select>
<button id="refresh">Refresh archive</button>
</div>
<div class="stats"><div class="stat"><span class="muted">Events displayed</span><strong id="count">—</strong></div><div class="stat"><span class="muted">Latest publication</span><strong id="latest" style="font-size:14px">—</strong></div><div class="stat"><span class="muted">Archive status</span><strong style="font-size:14px">Local SQLite</strong></div></div>
<div id="status" role="status">Loading archive…</div><section id="events" aria-live="polite"></section>
<footer>Source text is unverified publisher content, not investment advice. Publication and collection timestamps are distinct.</footer>
</main>
<script>
const $=id=>document.getElementById(id);
function dateLabel(value){if(!value)return "Publication date unavailable";const d=new Date(value);return Number.isNaN(d.valueOf())?"Publication date unavailable":d.toLocaleString();}
function safeLink(url){try{const u=new URL(url);return u.protocol==="https:"?u.href:null}catch{return null}}
function renderEvent(item){
 const article=document.createElement("article");article.className="event";
 const heading=document.createElement("h2"),link=safeLink(item.canonical_url);
 if(link){const a=document.createElement("a");a.href=link;a.target="_blank";a.rel="noopener noreferrer";a.textContent=item.title;heading.append(a)}
 else heading.textContent=item.title;
 article.append(heading);
 const meta=document.createElement("div");meta.className="meta";
 for(const label of [item.source,dateLabel(item.published_at),"Collected "+dateLabel(item.fetched_at)]){
  const span=document.createElement("span");span.textContent=label;meta.append(span)
 }
 article.append(meta);
 if(item.summary){const p=document.createElement("p");p.className="summary";p.textContent=item.summary;article.append(p)}
 if(item.symbols&&item.symbols.length){const tags=document.createElement("div");item.symbols.forEach(symbol=>{const t=document.createElement("span");t.className="tag";t.textContent=symbol;tags.append(t)});article.append(tags)}
 return article
}
async function load(){
 $("status").textContent="Loading archive…";$("events").replaceChildren();
 const params=new URLSearchParams({limit:$("limit").value});
 const symbol=$("symbol").value.trim().toUpperCase();if(symbol)params.set("symbol",symbol);
 try{
  const response=await fetch("/api/events?"+params.toString(),{headers:{"Accept":"application/json"}});
  if(!response.ok)throw new Error("HTTP "+response.status);
  const data=await response.json();$("count").textContent=data.count;
  $("latest").textContent=data.latest_published_at?dateLabel(data.latest_published_at):"—";
  if(!data.events.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No events in the archive yet. Run python collect_market_events.py to collect public headlines."; $("events").append(empty)}
  else data.events.forEach(item=>$("events").append(renderEvent(item)));
  $("status").textContent="Updated "+dateLabel(data.generated_at)+" · "+(symbol?"Filtered by "+symbol:"All symbols");
 }catch(error){$("status").textContent="Could not load archive: "+error.message}
}
$("refresh").addEventListener("click",load);$("symbol").addEventListener("keydown",e=>{if(e.key==="Enter")load()});$("limit").addEventListener("change",load);
load();
</script>
</body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    store: MarketEventStore

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._send(200, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/events":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            limit = max(1, min(limit, 250))
            symbol = query.get("symbol", [None])[0]
            if symbol:
                symbol = "".join(ch for ch in symbol.upper() if ch.isalnum() or ch in ".-")[:12] or None
            events = self.store.list_events(limit=limit, symbol=symbol)
            latest = next((item["published_at"] for item in events if item["published_at"]), None)
            payload = {
                "events": events,
                "count": len(events),
                "latest_published_at": latest,
                "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "read_only": True,
            }
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")

    def do_POST(self) -> None:
        self._send(405, b'{"error":"method not allowed; dashboard is read-only"}', "application/json; charset=utf-8")

    def do_PUT(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def log_message(self, format: str, *args) -> None:
        # Keep local terminal output concise and avoid logging query contents.
        print("dashboard:", format % args)


def create_server(host: str = "127.0.0.1", port: int = 8765, db_path: str | None = None):
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("For safety, the dashboard may only bind to loopback.")
    store = MarketEventStore(db_path)
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"store": store})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local read-only market events dashboard.")
    parser.add_argument("--host", default=os.environ.get("MARKET_DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MARKET_DASHBOARD_PORT", "8765")))
    parser.add_argument("--db", default=os.environ.get("MARKET_EVENT_DB", "data/market_events.sqlite3"))
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.db)
    print(f"Read-only Market Monitor: http://{args.host}:{args.port}")
    print("GET-only dashboard; no trading or account actions.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
