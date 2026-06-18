#!/usr/bin/env python3
"""Build a GitHub Pages-compatible static dashboard from cached CSV files."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

def records(name: str, index_col=None):
    df = pd.read_csv(DATA / name, index_col=index_col)
    return df.astype(object).where(pd.notnull(df), None).to_dict(orient="records")

files = {
    "manifest": json.loads((DATA / "manifest.json").read_text()),
    "prices": records("market_prices.csv"),
    "metrics": records("market_metrics.csv"),
    "holdings": records("holdings_valuation.csv"),
    "alerts": records("alerts.csv") if (DATA / "alerts.csv").exists() else [],
    "workforce": records("workforce_state_setting.csv"),
    "scorecard": records("career_scorecard.csv"),
    "education": records("education_attainment.csv"),
    "corr": pd.read_csv(DATA / "correlation_matrix.csv", index_col=0).reset_index().rename(columns={"index":"Index"}).astype(object).where(lambda x: pd.notnull(x), None).to_dict(orient="records"),
}

# Copy raw data for audit/download.
(DOCS / "data").mkdir(exist_ok=True)
for p in DATA.glob("*.csv"):
    (DOCS / "data" / p.name).write_bytes(p.read_bytes())
(DOCS / "data" / "manifest.json").write_text(json.dumps(files["manifest"], indent=2))
(DOCS / ".nojekyll").write_text("")

payload_json = json.dumps(files, allow_nan=False).replace("</", "<\\/")
html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Healthcare Markets + Nursing Workforce Command Center</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{ --bg:#07111f; --panel:#0d1b2e; --ink:#eaf2ff; --muted:#9db3cf; --accent:#4dd4ac; --warn:#ffcc66; --danger:#ff6b6b; --line:#1d3350; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif; }}
    header {{ padding:32px 6vw 20px; background:linear-gradient(135deg,#07111f,#10213a 65%,#123b45); border-bottom:1px solid var(--line); }}
    h1 {{ margin:0 0 8px; font-size:clamp(28px,4vw,48px); letter-spacing:-0.03em; }}
    h2 {{ margin-top:0; color:#fff; }} h3 {{ color:#fff; }}
    .tagline {{ color:var(--muted); max-width:1050px; line-height:1.55; }}
    nav {{ display:flex; gap:10px; flex-wrap:wrap; padding:14px 6vw; background:#081525; position:sticky; top:0; z-index:2; border-bottom:1px solid var(--line); }}
    nav button {{ background:#13243b; color:var(--ink); border:1px solid #274568; border-radius:999px; padding:10px 14px; cursor:pointer; }}
    nav button.active {{ background:var(--accent); color:#001b16; border-color:var(--accent); font-weight:700; }}
    main {{ padding:24px 6vw 60px; }}
    section {{ display:none; }} section.active {{ display:block; }}
    .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:16px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 20px 60px rgba(0,0,0,.22); }}
    .span4 {{ grid-column:span 4; }} .span6 {{ grid-column:span 6; }} .span12 {{ grid-column:span 12; }}
    @media (max-width:900px) {{ .span4,.span6 {{ grid-column:span 12; }} }}
    .metric {{ font-size:30px; font-weight:800; }} .muted {{ color:var(--muted); }}
    .alert {{ border-color:var(--warn); background:#271c0a; }} .danger {{ color:var(--danger); }} .good {{ color:var(--accent); }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }} th,td {{ border-bottom:1px solid var(--line); padding:9px; text-align:left; vertical-align:top; }} th {{ color:#bcd2ef; background:#0a1728; position:sticky; top:55px; }}
    .scroll {{ overflow:auto; max-height:520px; }}
    select,input {{ background:#07111f; color:var(--ink); border:1px solid #274568; border-radius:10px; padding:8px; margin:4px; }}
    a {{ color:#7be7ca; }}
  </style>
</head>
<body>
<header>
  <h1>Healthcare Markets + Nursing Workforce Command Center</h1>
  <p class="tagline">A public-source monitoring website for global healthcare market indices, 2026 nursing workforce pressure, and career-demand/ROI signals. No PHI. Market data is informational, not investment advice. Staffing and shortage indicators require human validation before policy use.</p>
  <p class="muted">Last generated: <strong>{files['manifest'].get('generated_at_utc','unknown')}</strong></p>
</header>
<nav>
  <button onclick="show('markets')" class="active">A. Markets</button>
  <button onclick="show('workforce')">B. Workforce</button>
  <button onclick="show('careers')">C. Careers</button>
  <button onclick="show('sources')">Sources + Limits</button>
</nav>
<main>
<section id="markets" class="active">
  <div id="alertBox"></div>
  <div class="grid" id="marketCards"></div>
  <div class="grid">
    <div class="card span12"><h2>12-month performance</h2><div id="performanceChart"></div></div>
    <div class="card span6"><h2>Correlation matrix</h2><div id="corrTable" class="scroll"></div></div>
    <div class="card span6"><h2>Volatility metrics</h2><div id="metricsTable" class="scroll"></div></div>
    <div class="card span12"><h2>Top-5 holdings valuation comparison</h2><div id="holdingsTable" class="scroll"></div></div>
    <div class="card span12"><h2>Analysis summary + implications for NIN-NAIO</h2>
      <p>The market dashboard turns global healthcare capital flows into an early signal for where hospitals, payers, life-science firms, and digital-health vendors may accelerate or defer AI investments. Relative performance, volatility, valuation gaps, and 30DMA deviations help NIN-NAIO read whether healthcare leaders are operating in expansion, caution, or repricing mode.</p>
      <p><strong>Implication:</strong> NAIO should position nurse-led AI governance as risk infrastructure, not optional innovation theater. When healthcare valuations diverge across the United States, global developed markets, and India, the opportunity is to teach nurses and executives how to govern AI investment choices across different economic regimes while preserving safety, dignity, and human judgment.</p>
      <h3>3 strategic moves</h3>
      <ol>
        <li><strong>Course creation:</strong> Launch <em>Healthcare AI Market Intelligence for Nurse Leaders</em> — a short executive course teaching nurses how to interpret healthcare market signals, vendor funding cycles, valuation pressure, and governance risk before AI procurement.</li>
        <li><strong>App development:</strong> Add a Florence-X <em>Market-to-Governance Signal Agent</em> that converts index moves, valuation discrepancies, and earnings shocks into procurement-risk briefs for nurse AI councils.</li>
        <li><strong>General program:</strong> Create a quarterly NIN <em>Healthcare AI Capital + Safety Briefing</em> connecting market movement to AI deployment risk, workforce burden, and nurse-led governance priorities.</li>
      </ol>
    </div>
  </div>
</section>
<section id="workforce">
  <div class="card"><h2>Filters</h2><label>State <select id="stateFilter" multiple></select></label><label>Occupation <select id="occFilter" multiple></select></label><label>Setting <select id="settingFilter" multiple></select></label><button onclick="renderWorkforce()">Apply</button></div><br>
  <div class="grid"><div class="card span6"><h2>Supply vs demand</h2><div id="supplyDemandChart"></div></div><div class="card span6"><h2>Highest shortage-risk proxy</h2><div id="shortageChart"></div></div><div class="card span12"><h2>State-by-state workforce table</h2><div id="workforceTable" class="scroll"></div></div>
    <div class="card span12"><h2>Analysis summary + implications for NIN-NAIO</h2>
      <p>The workforce dashboard converts shortage pressure, wage variation, retirement-exit risk, and setting-specific demand into a practical map of where nursing capacity is most fragile. Hospitals, outpatient care, and nursing facilities do not face the same workforce problem; each setting needs a different AI-governance, redesign, and education response.</p>
      <p><strong>Implication:</strong> NIN-NAIO can become the connective tissue between workforce planning and responsible AI adoption. The strategic message is simple: AI should first reduce avoidable cognitive and administrative burden in the settings and regions where nurses are under the greatest pressure, while giving bedside nurses a formal voice in deployment decisions.</p>
      <h3>3 strategic moves</h3>
      <ol>
        <li><strong>Course creation:</strong> Build <em>Nurse Workforce Intelligence + AI Readiness</em> — a course for nurse managers and educators on reading shortage maps, prioritizing AI use cases, and creating governance-ready staffing interventions.</li>
        <li><strong>App development:</strong> Develop a Florence-X <em>Workforce Burden Radar</em> that combines shortage, wage, retirement-exit, and setting demand signals into unit-level or regional risk briefs for nursing leaders.</li>
        <li><strong>General program:</strong> Launch a NIN <em>Regional Nurse AI Stewardship Fellowship</em> focused on high-gap states/settings, pairing nurses with mentors to identify burden-reduction workflows and governance safeguards.</li>
      </ol>
    </div>
  </div>
</section>
<section id="careers">
  <div class="grid"><div class="card span12"><h2>Nursing career-demand scorecard</h2><div id="careerScoreChart"></div><div id="scoreTable" class="scroll"></div></div><div class="card span6"><h2>ROI proxy</h2><div id="roiChart"></div></div><div class="card span6"><h2>Educational attainment shift</h2><div id="eduChart"></div></div>
    <div class="card span12"><h2>Analysis summary + implications for NIN-NAIO</h2>
      <p>The career dashboard shows that nursing demand is not one labor market. RN, LPN, and APRN pathways have different growth rates, wage returns, retirement-exit exposure, educational barriers, and shortage/surplus scenarios. This creates an opening for NIN-NAIO to guide nurses toward roles that combine clinical judgment, AI fluency, and governance authority.</p>
      <p><strong>Implication:</strong> NAIO should treat career mobility as governance infrastructure. The field needs more than prompt literacy; it needs nurses who can translate bedside realities into AI oversight, workflow redesign, product validation, and institutional decision rights.</p>
      <h3>3 strategic moves</h3>
      <ol>
        <li><strong>Course creation:</strong> Create <em>Nurse AI Career Pathways 2034</em> — a credential roadmap covering RN, LPN, APRN, informatics, AI governance, and Nurse AI Orchestrator roles with ROI and regional demand lenses.</li>
        <li><strong>App development:</strong> Build a NIN <em>Career ROI Navigator</em> that lets nurses compare credentials, wages, openings, retirement-exit pressure, and AI-governance career tracks by region.</li>
        <li><strong>General program:</strong> Stand up a <em>Nurse AI Orchestrator Accelerator</em> that converts experienced bedside nurses into governance fellows, workflow analysts, AI safety reviewers, and institutional AI council candidates.</li>
      </ol>
    </div>
  </div>
</section>
<section id="sources">
  <div class="card"><h2>Sources, assumptions, and limits</h2><div id="sourcesBlock"></div><p><a href="data/manifest.json">Download manifest</a> · <a href="data/market_prices.csv">Market prices CSV</a> · <a href="data/workforce_state_setting.csv">Workforce CSV</a></p></div>
</section>
</main>
<script id="payload" type="application/json">{payload_json}</script>
<script>
const data = JSON.parse(document.getElementById('payload').textContent);
function show(id) {{ document.querySelectorAll('section').forEach(s=>s.classList.remove('active')); document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active')); document.getElementById(id).classList.add('active'); event.target.classList.add('active'); setTimeout(()=>window.dispatchEvent(new Event('resize')), 50); }}
function table(rows) {{ if(!rows || !rows.length) return '<p class="muted">No data.</p>'; const cols=Object.keys(rows[0]); return '<table><thead><tr>'+cols.map(c=>`<th>${{c}}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>`<td>${{r[c] ?? ''}}</td>`).join('')+'</tr>').join('')+'</tbody></table>'; }}
function uniq(arr) {{ return [...new Set(arr)].sort(); }}
function fillSelect(id, vals) {{ const el=document.getElementById(id); el.innerHTML=vals.map(v=>`<option selected value="${{v}}">${{v}}</option>`).join(''); }}
const darkLayout = {{paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{{color:'#eaf2ff'}}, xaxis:{{gridcolor:'#1d3350'}}, yaxis:{{gridcolor:'#1d3350'}}, legend:{{orientation:'h'}}}};
function renderMarkets() {{
  const alerts=data.alerts||[]; document.getElementById('alertBox').innerHTML = alerts.length ? `<div class="card alert"><h2>⚠ 30DMA deviation alert</h2>${{table(alerts)}}</div><br>` : `<div class="card"><h2 class="good">No ±3% 30DMA deviation alerts</h2></div><br>`;
  document.getElementById('marketCards').innerHTML = data.metrics.map(m=>`<div class="card span4"><h3>${{m.index}}</h3><div class="metric">${{Number(m.latest_close).toLocaleString()}}</div><p class="muted">${{m.ticker}} · ${{m.region}} · 12m ${{m['12m_return_pct']}}% · Vol ${{m.ann_volatility_pct}}% · 30DMA dev ${{m.deviation_from_30dma_pct}}%</p></div>`).join('');
  const traces = uniq(data.prices.map(r=>r.index)).map(idx=>{{ const rows=data.prices.filter(r=>r.index===idx); return {{x:rows.map(r=>r.date), y:rows.map(r=>r.return_12m_pct), mode:'lines', name:idx}}; }});
  Plotly.newPlot('performanceChart', traces, {{...darkLayout, yaxis:{{title:'Return %', gridcolor:'#1d3350'}}}}, {{responsive:true}});
  document.getElementById('metricsTable').innerHTML=table(data.metrics); document.getElementById('holdingsTable').innerHTML=table(data.holdings); document.getElementById('corrTable').innerHTML=table(data.corr);
}}
function selected(id) {{ return [...document.getElementById(id).selectedOptions].map(o=>o.value); }}
function renderWorkforce() {{
  const states=selected('stateFilter'), occ=selected('occFilter'), settings=selected('settingFilter');
  let rows=data.workforce.filter(r=>states.includes(r.state)&&occ.includes(r.occupation)&&settings.includes(r.setting));
  const grouped={{}}; rows.forEach(r=>{{ const k=r.state+'|'+r.setting; grouped[k]=grouped[k]||{{state:r.state, setting:r.setting, supply:0, demand:0, shortage:0, n:0}}; grouped[k].supply+=r.supply_index; grouped[k].demand+=r.demand_index; grouped[k].shortage+=r.shortage_pct_proxy; grouped[k].n++; }});
  const g=Object.values(grouped).map(x=>({{...x, supply:x.supply/x.n, demand:x.demand/x.n, shortage:x.shortage/x.n}}));
  Plotly.newPlot('supplyDemandChart', [{{x:g.map(x=>x.supply), y:g.map(x=>x.demand), text:g.map(x=>x.state+' / '+x.setting), mode:'markers', marker:{{size:g.map(x=>Math.max(8,x.shortage)), color:g.map(x=>x.shortage), colorscale:'YlOrRd', showscale:true}}}}], {{...darkLayout, xaxis:{{title:'Supply index', gridcolor:'#1d3350'}}, yaxis:{{title:'Demand index', gridcolor:'#1d3350'}}}}, {{responsive:true}});
  const top=[...rows].sort((a,b)=>b.shortage_pct_proxy-a.shortage_pct_proxy).slice(0,30);
  Plotly.newPlot('shortageChart', [{{x:top.map(r=>r.state+' '+r.occupation), y:top.map(r=>r.shortage_pct_proxy), type:'bar', marker:{{color:'#ffcc66'}}}}], {{...darkLayout, yaxis:{{title:'Shortage-risk proxy %', gridcolor:'#1d3350'}}}}, {{responsive:true}});
  document.getElementById('workforceTable').innerHTML=table(rows.sort((a,b)=>b.shortage_pct_proxy-a.shortage_pct_proxy));
}}
function renderCareers() {{
  Plotly.newPlot('careerScoreChart', [{{x:data.scorecard.map(r=>r.occupation), y:data.scorecard.map(r=>r.career_demand_score_0_100), type:'bar', marker:{{color:'#4dd4ac'}}}}], {{...darkLayout, yaxis:{{title:'Score 0-100', gridcolor:'#1d3350'}}}}, {{responsive:true}});
  Plotly.newPlot('roiChart', [{{x:data.scorecard.map(r=>r.simple_payback_years_vs_45k_baseline), y:data.scorecard.map(r=>r.median_wage), text:data.scorecard.map(r=>r.occupation), mode:'markers+text', textposition:'top center', marker:{{size:data.scorecard.map(r=>Math.max(14,r.annual_openings/5000)), color:'#7be7ca'}}}}], {{...darkLayout, xaxis:{{title:'Simple payback years', gridcolor:'#1d3350'}}, yaxis:{{title:'Median wage', gridcolor:'#1d3350'}}}}, {{responsive:true}});
  Plotly.newPlot('eduChart', [{{x:data.education.map(r=>r.year), y:data.education.map(r=>r.associate_or_diploma_pct), mode:'lines+markers', name:'Associate/diploma'}}, {{x:data.education.map(r=>r.year), y:data.education.map(r=>r.bachelor_or_higher_pct), mode:'lines+markers', name:'Bachelor+'}}], darkLayout, {{responsive:true}});
  document.getElementById('scoreTable').innerHTML=table(data.scorecard);
}}
function renderSources() {{ document.getElementById('sourcesBlock').innerHTML='<pre style="white-space:pre-wrap">'+JSON.stringify(data.manifest.sources,null,2)+'</pre>'; }}
fillSelect('stateFilter', uniq(data.workforce.map(r=>r.state))); fillSelect('occFilter', uniq(data.workforce.map(r=>r.occupation))); fillSelect('settingFilter', uniq(data.workforce.map(r=>r.setting)));
renderMarkets(); renderWorkforce(); renderCareers(); renderSources();
</script>
</body>
</html>"""
(DOCS / "index.html").write_text(html)
print(f"Wrote {DOCS / 'index.html'} with {len(html):,} bytes")
