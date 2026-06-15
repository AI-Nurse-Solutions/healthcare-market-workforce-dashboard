import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.set_page_config(page_title="Healthcare Markets + Nursing Workforce Command Center", layout="wide")
st.title("Healthcare Markets + Nursing Workforce Command Center")
st.caption("NAIO operating dashboard — agents propose, humans judge, nurses steward. No PHI. Financial data is informational only, not investment advice.")

@st.cache_data(ttl=60*60)
def load_csv(name):
    path = DATA / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

@st.cache_data(ttl=60*60)
def load_manifest():
    p = DATA / "manifest.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())

manifest = load_manifest()
if not manifest:
    st.error("No cached data found. Run: `./run_update.sh` from the project directory.")
    st.stop()

st.sidebar.header("Filters")
st.sidebar.write(f"Last update: `{manifest.get('generated_at_utc','unknown')}`")
module = st.sidebar.radio("Module", ["A. Global healthcare markets", "B. 2026 nursing workforce", "C. Career-demand scorecard", "Sources + limits"])

prices = load_csv("market_prices.csv")
metrics = load_csv("market_metrics.csv")
holdings = load_csv("holdings_valuation.csv")
alerts = load_csv("alerts.csv")
workforce = load_csv("workforce_state_setting.csv")
scorecard = load_csv("career_scorecard.csv")
edu = load_csv("education_attainment.csv")

if module.startswith("A"):
    st.header("A) Global Healthcare Market Monitor")
    if not alerts.empty:
        st.warning("30-day moving-average deviation alert(s) active")
        st.dataframe(alerts, use_container_width=True, hide_index=True)
    else:
        st.success("No index is currently more than ±3% away from its 30-day moving average.")

    if not metrics.empty:
        c1, c2, c3 = st.columns(3)
        for i, row in metrics.iterrows():
            with [c1, c2, c3][i % 3]:
                st.metric(row["index"], f"{row['latest_close']:,.2f}", f"{row['deviation_from_30dma_pct']}% vs 30DMA")
                st.caption(f"12m: {row['12m_return_pct']}% | Vol: {row['ann_volatility_pct']}% | Ticker: {row['ticker']}")

    if not prices.empty:
        fig = px.line(prices, x="date", y="return_12m_pct", color="index", title="12-month indexed performance (%)")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns([1,1])
    with col1:
        st.subheader("Volatility and 30DMA metrics")
        st.dataframe(metrics, use_container_width=True, hide_index=True)
    with col2:
        st.subheader("Correlation matrix")
        corr = pd.read_csv(DATA / "correlation_matrix.csv", index_col=0) if (DATA / "correlation_matrix.csv").exists() else pd.DataFrame()
        if not corr.empty:
            st.dataframe(corr.style.background_gradient(cmap="RdBu", axis=None, vmin=-1, vmax=1), use_container_width=True)
        else:
            st.info("Correlation data unavailable.")

    st.subheader("Top-5 holdings valuation comparison")
    region = st.multiselect("Economic region", sorted(holdings["region"].dropna().unique()), default=sorted(holdings["region"].dropna().unique())) if not holdings.empty else []
    h = holdings[holdings["region"].isin(region)] if region else holdings
    st.dataframe(h, use_container_width=True, hide_index=True)
    st.caption("Earnings-surprise values may be blank when the free source does not expose the field for a symbol/exchange.")

elif module.startswith("B"):
    st.header("B) 2026 Nursing Workforce Shortage Monitor")
    if workforce.empty:
        st.error("Workforce data missing.")
    else:
        states = st.sidebar.multiselect("States", sorted(workforce["state"].unique()), default=[])
        occ = st.sidebar.multiselect("License group", sorted(workforce["occupation"].unique()), default=sorted(workforce["occupation"].unique()))
        settings = st.sidebar.multiselect("Care setting", sorted(workforce["setting"].unique()), default=sorted(workforce["setting"].unique()))
        df = workforce.copy()
        if states: df = df[df["state"].isin(states)]
        df = df[df["occupation"].isin(occ) & df["setting"].isin(settings)]

        supply_demand = st.radio("Side-by-side view", ["Supply vs demand", "Shortage %", "Median wage"], horizontal=True)
        if supply_demand == "Supply vs demand":
            grp = df.groupby(["state", "setting"], as_index=False)[["supply_index", "demand_index"]].mean()
            fig = px.scatter(grp, x="supply_index", y="demand_index", color="setting", hover_name="state", title="Supply vs demand index by state and setting", size=np.maximum(1, grp["demand_index"]-grp["supply_index"]+20))
        elif supply_demand == "Shortage %":
            grp = df.groupby(["state", "occupation"], as_index=False)["shortage_pct_proxy"].mean()
            fig = px.bar(grp.sort_values("shortage_pct_proxy", ascending=False).head(30), x="state", y="shortage_pct_proxy", color="occupation", title="Highest shortage-risk proxy by state")
        else:
            grp = df.groupby(["state", "occupation"], as_index=False)["median_annual_wage"].mean()
            fig = px.bar(grp.sort_values("median_annual_wage", ascending=False).head(30), x="state", y="median_annual_wage", color="occupation", title="Median annual wage by state")
        st.plotly_chart(fig, use_container_width=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avg shortage-risk proxy", f"{df['shortage_pct_proxy'].mean():.1f}%")
        k2.metric("Avg 5y retirement-exit", f"{df['projected_retirement_exit_rate_5y_pct'].mean():.1f}%")
        k3.metric("Median wage", f"${df['median_annual_wage'].median():,.0f}")
        k4.metric("Critical rows >25%", int((df['shortage_pct_proxy'] > 25).sum()))
        st.dataframe(df.sort_values("shortage_pct_proxy", ascending=False), use_container_width=True, hide_index=True)
        st.info("State shortage percentages are modeled planning indicators unless `data_quality` says BLS_OEWS_2025_download. Use them for triage, not formal regulatory filings.")

elif module.startswith("C"):
    st.header("C) Nursing Career-Demand Scorecard")
    if not scorecard.empty:
        st.dataframe(scorecard, use_container_width=True, hide_index=True)
        fig = px.bar(scorecard, x="occupation", y="career_demand_score_0_100", color="supply_demand_scenario_pct", title="Career demand score with shortage/surplus scenario")
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.scatter(scorecard, x="simple_payback_years_vs_45k_baseline", y="median_wage", size="annual_openings", color="occupation", title="ROI proxy: credential payback vs wage and openings")
        st.plotly_chart(fig2, use_container_width=True)
        st.subheader("Economic impact scenario")
        st.write("The requested scenario compares a projected **28% LPN shortage** against a **67% APRN supply surplus**. The dashboard converts each scenario into a wage-weighted exposure proxy: `abs(scenario %) × jobs × median wage`.")
    if not edu.empty:
        st.subheader("Educational attainment shift")
        e = edu.melt(id_vars=["year", "source"], value_vars=["associate_or_diploma_pct", "bachelor_or_higher_pct"], var_name="attainment", value_name="pct")
        st.plotly_chart(px.line(e, x="year", y="pct", color="attainment", markers=True, title="RN educational-attainment shift"), use_container_width=True)
        st.dataframe(edu, use_container_width=True, hide_index=True)

else:
    st.header("Sources, assumptions, and limits")
    st.json(manifest.get("sources", {}))
    st.subheader("Generated files")
    st.write(manifest.get("files", []))
    st.subheader("Row counts")
    st.write(manifest.get("row_counts", {}))
    st.warning("Governance note: this dashboard does not use PHI and should not be used as medical advice, staffing-ratio policy, or investment advice without human review and primary-source validation.")
