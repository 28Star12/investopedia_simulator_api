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
.decision-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}.decision-count{background:#121c32;border:1px solid #34435f;border-radius:10px;padding:12px}.decision-count strong{display:block;font-size:22px;margin-top:4px}.research-controls{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.research-controls select{min-width:190px}.research-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.research-card{background:#121a2d;border:1px solid #34435f;border-radius:12px;padding:16px}.research-card h3{margin:0 0 5px;font-size:18px}.research-card .status{font-size:11px;letter-spacing:.04em;color:#b8c9e8}.metrics{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0;color:#c5d2e6;font-size:13px}.research-card p{color:#b8c5d8;line-height:1.45;font-size:13px}.research-card a{color:#a9cbff}.alert-card{background:#121a2d;border:1px solid #34435f;border-radius:12px;padding:15px;margin:10px 0}.alert-card h3{margin:0 0 8px;font-size:16px}.severity{font-size:11px;font-weight:700}.severity.HIGH{color:#ff9b9b}.severity.MEDIUM{color:#ffd58a}.severity.LOW{color:#9fc5ff}.alert-card p{color:#c2ccdc;line-height:1.45;font-size:13px}.alert-card a{color:#a9cbff}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0 0}.tabs button{background:#17243b;border-color:#34435f}.tabs button[aria-selected="true"]{background:#345486;border-color:#7da7e8}.page{display:none}.page.active{display:block}
footer{color:#7e8ca4;font-size:12px;padding:24px 0;text-align:center}
@media(max-width:600px){.controls>*{width:100%}.stat{flex:1}.decision-summary{grid-template-columns:1fr}.research-controls>*{width:100%}}
</style>
</head>
<body>
<header><h1>Market Monitor</h1><div class="sub">Public market news archive · Read-only research · No trading</div><div id="monitor-status" class="sub" role="status">Monitoring status: loading…</div><nav class="tabs" role="tablist" aria-label="Dashboard pages"><button type="button" role="tab" data-page="info" aria-selected="true">Infos</button><button type="button" role="tab" data-page="stocks" aria-selected="false">Stocks</button><button type="button" role="tab" data-page="alerts" aria-selected="false">Alertes</button></nav></header>
<main class="wrap">
<section id="info-page" class="page active" aria-label="Informations">
<div class="controls">
<input id="symbol" maxlength="12" placeholder="Filter symbol (e.g. AAPL)" aria-label="Filter by symbol">
<select id="limit" aria-label="Number of events"><option value="25">Latest 25</option><option value="50" selected>Latest 50</option><option value="100">Latest 100</option><option value="250">Latest 250</option></select>
<button id="refresh">Refresh archive</button>
</div>
<div class="stats"><div class="stat"><span class="muted">Events displayed</span><strong id="count">—</strong></div><div class="stat"><span class="muted">Latest publication</span><strong id="latest" style="font-size:14px">—</strong></div><div class="stat"><span class="muted">Archive status</span><strong style="font-size:14px">Local SQLite</strong></div></div>
<h2 style="margin-top:30px">Upcoming earnings calendar</h2><p class="muted">Only dates explicitly found in archived publisher announcements are shown as confirmed. Unconfirmed announcements never receive an estimated date.</p><div id="earnings-status" class="muted" role="status">Loading earnings calendar…</div><section id="earnings-calendar" aria-live="polite"></section><h2 style="margin-top:30px">News and filings archive</h2><div id="status" role="status">Loading archive…</div><section id="events" aria-live="polite"></section>
</section>
<section id="stocks-page" class="page" aria-label="Stocks">
<h2>Autonomous stock research</h2><section class="committee"><h2>Top 5 investment research shortlist</h2><p class="muted">The committee ranks the top five discovered stocks. Missing SEC or technical data is shown explicitly; sentiment is estimated from archived news headlines and summaries. No buy candidate is declared until all three analysts are complete.</p><div id="committee-status" class="muted" role="status">Loading shortlist…</div><section id="committee-list" class="research-grid" aria-live="polite"></section></section><p class="muted">Universe discovery, market snapshot and explainable news signals. Research labels are screening signals, not buy/sell instructions.</p><div class="decision-summary" aria-label="Research decision counts"><div class="decision-count"><span class="muted">CANDIDATE</span><strong id="candidate-count">—</strong></div><div class="decision-count"><span class="muted">WATCH</span><strong id="watch-count">—</strong></div><div class="decision-count"><span class="muted">AVOID</span><strong id="avoid-count">—</strong></div></div><div class="research-controls"><select id="decision-filter" aria-label="Filter research decisions"><option value="ALL">All decisions</option><option value="CANDIDATE">CANDIDATE only</option><option value="WATCH">WATCH only</option><option value="AVOID">AVOID only</option></select><select id="research-sort" aria-label="Sort research cards"><option value="priority">Sort: decision priority</option><option value="score">Sort: score (high to low)</option><option value="daily">Sort: daily change (largest move)</option><option value="symbol">Sort: symbol A–Z</option></select></div><div id="research-status" class="muted" role="status">Loading research…</div><section id="research" class="research-grid" aria-live="polite"></section></section>
<section id="alerts-page" class="page" aria-label="Alertes">
<h2 style="margin-top:0">Market alerts</h2><h2>News impact on held positions</h2><p class="muted">Keyword-based signals matched to positions in the read-only Paper account. Exposure is indicative, not a forecast.</p><div id="impact-status" class="muted" role="status">Loading portfolio impact…</div><section id="portfolio-impacts" aria-live="polite"></section><p class="muted">Large daily price moves, material news keywords and newly archived SEC filings. Keyword signals require source verification.</p><div class="decision-summary"><div class="decision-count"><span class="muted">HIGH priority</span><strong id="alert-high">—</strong></div><div class="decision-count"><span class="muted">MEDIUM priority</span><strong id="alert-medium">—</strong></div><div class="decision-count"><span class="muted">LOW priority</span><strong id="alert-low">—</strong></div></div><div id="alerts-status" class="muted" role="status">Loading alerts…</div><section id="alerts" aria-live="polite"></section></section>
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
let savedResearchCards=[];
function decisionOf(card){return String(card.decision?.decision||"UNCLASSIFIED").toUpperCase()}
function renderInvestmentReview(card){
 const review=card.investment_review||{},article=document.createElement("article");article.className="research-card";
 const title=document.createElement("h3");title.textContent=(card.symbol||"—")+" · "+(card.company||"");article.append(title);
 const status=document.createElement("div");status.className="status";status.textContent=(review.decision||"DO_NOT_BUY")+" · score "+(review.score??"—")+"/100";article.append(status);
 const market=card.market||{},price=document.createElement("p");price.textContent="Market snapshot: "+(market.price==null?"price unavailable":"$"+Number(market.price).toFixed(2))+" · daily change "+(market.daily_change_pct==null?"—":market.daily_change_pct+"%");article.append(price);
 const explanation=document.createElement("p");explanation.textContent=review.explanation||"No explanation available.";article.append(explanation);
 const combined=document.createElement("p");combined.textContent="Combined analyst score: "+(review.combined_score==null?"incomplete":(review.combined_score*100).toFixed(1)+"/100")+" · technical "+(review.technical_score==null?"—":review.technical_score)+" · sentiment "+(review.sentiment_score==null?"—":review.sentiment_score)+" · fundamental "+(review.fundamental_score==null?"—":review.fundamental_score);article.append(combined);
 const tech=card.technical||{};const technicalDetail=document.createElement("p");technicalDetail.textContent="Technical: "+(tech.status||"unavailable")+" · SMA20 "+(tech.sma_20??"—")+" · SMA50 "+(tech.sma_50??"—")+" · RSI14 "+(tech.rsi_14??"—")+" · reversal "+(tech.reversal?.status||"—")+" · trend "+(tech.trend?.status||"—");article.append(technicalDetail);
 const sentiment=card.sentiment||{};const sentimentDetail=document.createElement("p");sentimentDetail.textContent="News sentiment: "+(sentiment.status||"unavailable")+" · score "+(sentiment.score==null?"—":(sentiment.score*100).toFixed(0)+"/100")+" · mood "+(sentiment.mood||"—")+" · positive "+(sentiment.positive_articles??0)+" · negative "+(sentiment.negative_articles??0)+" · intensity "+(sentiment.extreme_score==null?"—":(sentiment.extreme_score*100).toFixed(0)+"/100");article.append(sentimentDetail);
 for(const [label,items] of [["Positive factors",review.reasons||[]],["Risks / missing information",review.risks||[]]]){
  const p=document.createElement("p");p.textContent=label+": "+(items.length?items.join(" · "):"None identified");article.append(p)
 }
 const missing=document.createElement("p");missing.textContent="Missing core data: "+((review.missing_data||[]).join(", ")||"none")+" · SEC filing age: "+(review.annual_filing_age_days==null?"unknown":review.annual_filing_age_days+" days");article.append(missing);
 const stamp=document.createElement("small");stamp.className="muted";stamp.textContent="Reviewed "+dateLabel(review.generated_at)+" · rules-based, not generative AI";article.append(stamp);
 return article
}
function renderInvestmentShortlist(){
 const selected=savedResearchCards.filter(card=>card.shortlisted&&card.investment_review);
 $("committee-list").replaceChildren();
 if(!selected.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No research cards are saved yet. Run a monitoring cycle to populate the shortlist.";$("committee-list").append(empty)}
 else selected.forEach(card=>$("committee-list").append(renderInvestmentReview(card)));
 const buyCount=selected.filter(card=>card.investment_review.decision==="PAPER_BUY_CANDIDATE").length;
 $("committee-status").textContent=selected.length+" / 5 stocks reviewed · "+buyCount+" paper-buy candidate(s) · "+(selected.length-buyCount)+" do not pass the buy screen.";
}
function renderResearchList(){
 const filter=$("decision-filter").value,sort=$("research-sort").value;
 let cards=savedResearchCards.filter(card=>filter==="ALL"||decisionOf(card)===filter);
 const priority={CANDIDATE:0,WATCH:1,AVOID:2,UNCLASSIFIED:3};
 cards.sort((a,b)=>{
  if(sort==="score")return Number(b.decision?.score??-999)-Number(a.decision?.score??-999);
  if(sort==="daily")return Math.abs(Number(b.market?.daily_change_pct??0))-Math.abs(Number(a.market?.daily_change_pct??0));
  if(sort==="symbol")return String(a.symbol||"").localeCompare(String(b.symbol||""));
  return (priority[decisionOf(a)]??3)-(priority[decisionOf(b)]??3)||Number(b.decision?.score??-999)-Number(a.decision?.score??-999);
 });
 $("research").replaceChildren();
 if(!cards.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No stocks match this decision filter."; $("research").append(empty)}
 else cards.forEach(card=>$("research").append(renderResearch(card)));
 $("research-status").textContent=cards.length+" of "+savedResearchCards.length+" research cards displayed · labels are screening signals only.";
}
function renderResearch(card){
 const article=document.createElement("article");article.className="research-card";
 const title=document.createElement("h3");title.textContent=(card.symbol||"—")+" · "+(card.company||"");article.append(title);
 const decision=card.decision||{};const status=document.createElement("div");status.className="status";status.textContent=(decision.decision||card.research_status||"UNCLASSIFIED")+" · score "+(decision.score??"—");article.append(status);
 const metrics=document.createElement("div");metrics.className="metrics";
 const market=card.market||{};
 for(const value of ["Price: "+(market.price==null?"—":"$"+Number(market.price).toFixed(2)),"Daily: "+(market.daily_change_pct==null?"—":Number(market.daily_change_pct).toFixed(2)+"%"),"News signal: "+(card.news_score_heuristic??"—"),"Discovery: "+(card.discovery_score??"—")]){
  const span=document.createElement("span");span.textContent=value;metrics.append(span)
 }article.append(metrics);
 const detail=document.createElement("p");detail.textContent="Archived news: "+(card.news_count_archived??0)+" · Fundamentals: "+((card.fundamentals||{}).status||"not available");article.append(detail);
 if(decision.explanation){const explanation=document.createElement("p");explanation.textContent=decision.explanation;article.append(explanation)}
 const reasons=[...(decision.reasons||[]).map(x=>"✓ "+x),...(decision.risks||[]).map(x=>"⚠ "+x)];if(reasons.length){const p=document.createElement("p");p.textContent=reasons.join(" · ");article.append(p)}
 const terms=[...(card.positive_terms||[]).map(x=>"Positive: "+x),...(card.risk_terms||[]).map(x=>"Risk: "+x)];
 if(terms.length){const p=document.createElement("p");p.textContent=terms.join(" · ");article.append(p)}
 const filings=card.sec_filings||[];if(filings.length){const p=document.createElement("p");p.textContent="Recent SEC filings: ";filings.slice(0,3).forEach((filing,i)=>{if(i)p.append(" · ");const a=document.createElement("a");const href=safeLink(filing.url);a.textContent=filing.form||filing.title||"Filing";if(href){a.href=href;a.target="_blank";a.rel="noopener noreferrer"}p.append(a)});article.append(p)}
 const fundamentalMetrics=card.fundamentals?.metrics||{};const metricLabels={revenue:"Revenue",operating_income:"Operating income",net_income:"Net income",operating_cash_flow:"Operating cash flow",assets:"Assets",liabilities:"Liabilities"};const metricText=Object.entries(metricLabels).filter(([key])=>fundamentalMetrics[key]).map(([key,label])=>label+": "+Number(fundamentalMetrics[key].value).toLocaleString()+" "+(fundamentalMetrics[key].unit||"")).join(" · ");if(metricText){const p=document.createElement("p");p.textContent=metricText;article.append(p)}
 const note=document.createElement("p");note.textContent=(decision.disclaimer||card.assessment||"Rule-based screening only.");article.append(note);
 const stamp=document.createElement("small");stamp.className="muted";stamp.textContent="Analyzed "+dateLabel(card.generated_at);article.append(stamp);
 return article
}
async function loadResearch(){
 $("research-status").textContent="Loading saved research cards…";$("research").replaceChildren();
 try{const response=await fetch("/api/research?limit=250",{headers:{"Accept":"application/json"}});
 if(!response.ok)throw new Error("HTTP "+response.status);
 const data=await response.json();
 savedResearchCards=data.research_cards||[];
 renderInvestmentShortlist();
 const counts={CANDIDATE:0,WATCH:0,AVOID:0};savedResearchCards.forEach(card=>{const label=decisionOf(card);if(Object.prototype.hasOwnProperty.call(counts,label))counts[label]++});
 $("candidate-count").textContent=counts.CANDIDATE;$("watch-count").textContent=counts.WATCH;$("avoid-count").textContent=counts.AVOID;
 renderResearchList();
 }catch(error){$("research-status").textContent="Could not load research cards: "+error.message}
}
function renderAlert(item){
 const article=document.createElement("article");article.className="alert-card";
 const heading=document.createElement("h3");heading.textContent=item.title;article.append(heading);
 const severity=document.createElement("div");severity.className="severity "+item.severity;severity.textContent=item.severity+" · "+item.alert_type.replaceAll("_"," ");article.append(severity);
 const p=document.createElement("p");p.textContent=item.description;article.append(p);
 const meta=document.createElement("div");meta.className="meta";meta.textContent=item.symbol+" · "+dateLabel(item.observed_at);article.append(meta);
 const href=safeLink(item.source_url);if(href){const a=document.createElement("a");a.href=href;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open source";article.append(a)}
 return article
}
function renderPortfolioImpact(item){
 const article=document.createElement("article");article.className="alert-card";
 const heading=document.createElement("h3");heading.textContent=item.symbol+" · "+item.title;article.append(heading);
 const level=document.createElement("div");level.className="severity "+item.severity;level.textContent=item.severity+" · "+item.impact.replaceAll("_"," ");article.append(level);
 const p=document.createElement("p");p.textContent=item.description;article.append(p);
 const details=item.payload||{};const meta=document.createElement("div");meta.className="meta";
 meta.textContent="Exposure: "+(details.exposure_pct==null?"unavailable":details.exposure_pct.toFixed(2)+"% of account equity")+" · Confidence: "+(details.confidence||"LOW")+" · "+dateLabel(item.published_at);article.append(meta);
 const href=safeLink(item.source_url);if(href){const a=document.createElement("a");a.href=href;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open source";article.append(a)}
 return article
}
async function loadPortfolioImpacts(){
 $("impact-status").textContent="Loading held-position impact signals…";$("portfolio-impacts").replaceChildren();
 try{const response=await fetch("/api/portfolio-impact?limit=100",{headers:{"Accept":"application/json"}});
 if(!response.ok)throw new Error("HTTP "+response.status);
 const data=await response.json(),items=data.impacts||[];
 if(!items.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No archived news matched your current holdings yet.";$("portfolio-impacts").append(empty)}
 else items.forEach(item=>$("portfolio-impacts").append(renderPortfolioImpact(item)));
 $("impact-status").textContent=items.length+" impact signals · generated from archived sources · read-only";
 }catch(error){$("impact-status").textContent="Could not load portfolio impact: "+error.message}
}
function renderEarnings(item){
 const article=document.createElement("article");article.className="event";
 const heading=document.createElement("h2");heading.textContent=item.symbol+" · "+(item.metadata?.earnings_date||"Date unconfirmed");article.append(heading);
 const meta=document.createElement("div");meta.className="meta";meta.textContent=(item.metadata?.status||"UNKNOWN")+" · source: "+(item.metadata?.original_source||item.source)+" · announced "+dateLabel(item.published_at);article.append(meta);
 const summary=document.createElement("p");summary.className="summary";summary.textContent=item.metadata?.original_title||item.summary||item.title;article.append(summary);
 const href=safeLink(item.metadata?.original_url||item.canonical_url);if(href){const a=document.createElement("a");a.href=href;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open announcement";article.append(a)}
 return article
}
async function loadEarningsCalendar(){
 $("earnings-status").textContent="Loading earnings announcements…";$("earnings-calendar").replaceChildren();
 try{const response=await fetch("/api/earnings?limit=250",{headers:{"Accept":"application/json"}});
 if(!response.ok)throw new Error("HTTP "+response.status);
 const data=await response.json(),items=data.announcements||[];
 if(!items.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No explicit earnings-date announcements found in the current news archive.";$("earnings-calendar").append(empty)}
 else items.forEach(item=>$("earnings-calendar").append(renderEarnings(item)));
 $("earnings-status").textContent=items.length+" announcements · "+data.confirmed_count+" explicit dates · "+data.unconfirmed_count+" unconfirmed · no estimated dates";
 }catch(error){$("earnings-status").textContent="Could not load earnings calendar: "+error.message}
}
async function loadAlerts(){
 $("alerts-status").textContent="Loading saved alerts…";$("alerts").replaceChildren();
 try{const response=await fetch("/api/alerts?limit=250",{headers:{"Accept":"application/json"}});
 if(!response.ok)throw new Error("HTTP "+response.status);
 const data=await response.json(),items=data.alerts||[];
 const counts={HIGH:0,MEDIUM:0,LOW:0};items.forEach(x=>{if(counts[x.severity]!==undefined)counts[x.severity]++});
 $("alert-high").textContent=counts.HIGH;$("alert-medium").textContent=counts.MEDIUM;$("alert-low").textContent=counts.LOW;
 if(!items.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No alerts yet. Run python market_research.py to generate a monitoring cycle.";$("alerts").append(empty)}
 else items.forEach(item=>$("alerts").append(renderAlert(item)));
 $("alerts-status").textContent=items.length+" saved alerts · updated "+dateLabel(data.generated_at);
 }catch(error){$("alerts-status").textContent="Could not load alerts: "+error.message}
}
async function loadMonitor(){try{const r=await fetch("/api/monitor");const s=await r.json();const next=s.next_run_at?" · next "+dateLabel(s.next_run_at):"";const last=s.last_run_at?" · last "+dateLabel(s.last_run_at):"";const err=s.last_error?" · "+s.last_error:"";$("monitor-status").textContent="Monitoring: "+s.state+" · every "+Math.round((s.interval_seconds||0)/60)+" min"+last+next+err;}catch(e){$("monitor-status").textContent="Monitoring status unavailable";}}
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
$("refresh").addEventListener("click",()=>{load();loadResearch();loadEarningsCalendar();loadAlerts();loadPortfolioImpacts();loadMonitor()});$("symbol").addEventListener("keydown",e=>{if(e.key==="Enter")load()});$("limit").addEventListener("change",load);$("decision-filter").addEventListener("change",renderResearchList);$("research-sort").addEventListener("change",renderResearchList);
load();loadResearch();loadEarningsCalendar();loadAlerts();loadPortfolioImpacts();loadMonitor();setInterval(()=>{load();loadResearch();loadEarningsCalendar();loadAlerts();loadPortfolioImpacts();loadMonitor()},60000);
function activatePage(name){const allowed=["info","stocks","alerts"];const page=allowed.includes(name)?name:"info";document.querySelectorAll(".page").forEach(el=>el.classList.toggle("active",el.id===page+"-page"));document.querySelectorAll("[data-page]").forEach(btn=>btn.setAttribute("aria-selected",String(btn.dataset.page===page)));}
document.querySelectorAll("[data-page]").forEach(btn=>btn.addEventListener("click",()=>{activatePage(btn.dataset.page);history.replaceState(null,"","#"+btn.dataset.page)}));
activatePage(location.hash.slice(1));
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
        if parsed.path == "/api/monitor":
            status = getattr(self, "monitor_status", None) or {"state": "DISABLED", "interval_seconds": 0}
            self._send(200, json.dumps(status, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/research":
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["100"])[0])
            except (TypeError, ValueError):
                limit = 100
            cards = self.store.list_research_cards(max(1, min(limit, 250)))
            payload = {"research_cards": cards, "count": len(cards), "read_only": True}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/portfolio-impact":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except (TypeError, ValueError):
                limit = 100
            symbol = query.get("symbol", [None])[0]
            impacts = self.store.list_portfolio_impacts(max(1, min(limit, 250)), symbol=symbol)
            payload = {"impacts": impacts, "count": len(impacts),
                       "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                       "read_only": True}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/earnings":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except (TypeError, ValueError):
                limit = 100
            limit = max(1, min(limit, 250))
            from datetime import date
            events = self.store.list_events(limit=500)
            announcements = []
            today = date.today().isoformat()
            for item in events:
                if item.get("event_type") != "earnings_calendar":
                    continue
                metadata = item.get("metadata") or {}
                earnings_date = metadata.get("earnings_date")
                if metadata.get("status") == "DATE_CONFIRMED" and earnings_date and earnings_date < today:
                    continue
                announcements.append({**item, "symbol": (item.get("symbols") or [""])[0]})
            announcements.sort(key=lambda item: (
                (item.get("metadata") or {}).get("earnings_date") or "9999-99-99",
                item.get("symbol", "")))
            announcements = announcements[:limit]
            payload = {"announcements": announcements, "count": len(announcements),
                       "confirmed_count": sum(1 for x in announcements if (x.get("metadata") or {}).get("status") == "DATE_CONFIRMED"),
                       "unconfirmed_count": sum(1 for x in announcements if (x.get("metadata") or {}).get("status") != "DATE_CONFIRMED"),
                       "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                       "read_only": True}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/alerts":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except (TypeError, ValueError):
                limit = 100
            symbol = query.get("symbol", [None])[0]
            alerts = self.store.list_alerts(max(1, min(limit, 250)), symbol=symbol)
            payload = {"alerts": alerts, "count": len(alerts),
                       "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                       "read_only": True}
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
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


def create_server(host: str = "127.0.0.1", port: int = 8765, db_path: str | None = None, monitor_status=None):
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("For safety, the dashboard may only bind to loopback.")
    store = MarketEventStore(db_path)
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"store": store, "monitor_status": monitor_status})
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local read-only market events dashboard.")
    parser.add_argument("--host", default=os.environ.get("MARKET_DASHBOARD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MARKET_DASHBOARD_PORT", "8765")))
    parser.add_argument("--db", default=os.environ.get("MARKET_EVENT_DB", "data/market_events.sqlite3"))
    parser.add_argument("--no-monitor", action="store_true", help="Disable automatic periodic research cycles.")
    args = parser.parse_args()
    from monitoring_scheduler import MonitoringScheduler
    interval = int(os.environ.get("MARKET_MONITOR_INTERVAL_SECONDS", "900"))
    status = {"state": "DISABLED", "interval_seconds": interval, "last_run_at": None, "next_run_at": None, "last_error": None}
    scheduler = None
    if not args.no_monitor and os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY"):
        scheduler = MonitoringScheduler(interval, int(os.environ.get("MARKET_MONITOR_LIMIT", "100")), args.db, status)
        scheduler.start()
    elif not args.no_monitor:
        status["state"] = "WAITING_FOR_CREDENTIALS"
    server = create_server(args.host, args.port, args.db, status)
    print(f"Read-only Market Monitor: http://{args.host}:{args.port}")
    print("GET-only dashboard; no trading or account actions.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        if scheduler:
            scheduler.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
