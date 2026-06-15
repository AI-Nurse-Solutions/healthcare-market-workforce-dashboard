#!/usr/bin/env python3
"""Fetch/cache data for the healthcare market + nursing workforce dashboard.

Design principle: use live/public sources when possible, and explicitly label
modeled or proxy fields. No patient data/PHI is used.
"""
from __future__ import annotations

import json
import math
import os
import re
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

SOURCES = {
    "finance_prices": "Yahoo Finance via yfinance. Direct index tickers where available; MSCI World Health Care is proxied with iShares Global Healthcare ETF (IXJ) because public free real-time index levels are not consistently available.",
    "bls_oews": "BLS OEWS May 2025 state tables: https://www.bls.gov/oes/tables.htm (XLSX link /oes/special-requests/oesm25st.zip)",
    "bls_ooh": "BLS Occupational Outlook Handbook 2024-2034: RNs 5% growth/$93,600 median; LPN/LVN 3% growth/$62,340 median; APRNs 35% growth/$132,050 median.",
    "ncsbn": "NCSBN 2024 National Nursing Workforce Study: >138,000 nurses left since 2022; almost 40% intend to leave by 2029; RN intent 39.9%, LPN/VN intent 41.3% noted in NCSBN 2026 survey announcement.",
    "modeling_note": "State shortage/supply-demand scores are derived planning indicators, not official BLS/NCSBN state shortage percentages. They combine OEWS employment/wage density with national NCSBN exit intent, BLS opening rates, and HRSA-style supply-demand framing. Replace with licensed HRSA/state board data when available."
}

INDICES = {
    "S&P 500 Health Care Select Sector Index": {"ticker": "^SP500-35", "region": "United States", "proxy": False},
    "MSCI World Health Care Index (IXJ ETF proxy)": {"ticker": "IXJ", "region": "Global developed", "proxy": True},
    # Yahoo exposes only 1d/5d for NIFTY_HEALTHCARE.NS as of this build, so
    # use the nearest liquid public healthcare/pharma history proxy for charts.
    "Nifty Healthcare Index (^CNXPHARMA proxy)": {"ticker": "^CNXPHARMA", "region": "India", "proxy": True},
}

# Top holdings are maintained as transparent watchlists; update via ETF/index provider sites.
HOLDINGS = {
    "S&P 500 Health Care Select Sector Index": ["LLY", "JNJ", "ABBV", "MRK", "ABT"],
    "MSCI World Health Care Index (IXJ ETF proxy)": ["LLY", "JNJ", "NOVN.SW", "ROG.SW", "AZN.L"],
    "Nifty Healthcare Index (^CNXPHARMA proxy)": ["SUNPHARMA.NS", "CIPLA.NS", "DIVISLAB.NS", "DRREDDY.NS", "APOLLOHOSP.NS"],
}

STATE_ABBR = {
    'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','DC':'District of Columbia','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'
}

OCCS = {
    "RN": "29-1141",
    "LPN": "29-2061",
    "APRN": "29-1171",  # nurse practitioners as APRN proxy in state wage table
}

CAREER_FACTS = {
    "RN": {"median_wage": 93600, "growth_2034_pct": 5, "jobs_2024": 3391000, "annual_openings": 189100, "typical_education": "Bachelor's degree", "tuition_proxy": 45000, "retirement_exit_rate_5y": 39.9},
    "LPN": {"median_wage": 62340, "growth_2034_pct": 3, "jobs_2024": 651400, "annual_openings": 54400, "typical_education": "Postsecondary nondegree award", "tuition_proxy": 18000, "retirement_exit_rate_5y": 41.3},
    "APRN": {"median_wage": 132050, "growth_2034_pct": 35, "jobs_2024": 382700, "annual_openings": 32700, "typical_education": "Master's degree", "tuition_proxy": 75000, "retirement_exit_rate_5y": 39.9},
}

SETTING_WEIGHTS = {
    "Hospitals": {"RN": 0.59, "LPN": 0.16, "APRN": 0.22},
    "Outpatient care": {"RN": 0.19, "LPN": 0.24, "APRN": 0.48},
    "Nursing facilities": {"RN": 0.06, "LPN": 0.37, "APRN": 0.06},
}


def normalize_download(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        if ('Close', ticker) in df.columns:
            out = pd.DataFrame({"close": df[('Close', ticker)]})
        else:
            close = df.xs('Close', axis=1, level=0).iloc[:, 0]
            out = pd.DataFrame({"close": close})
    else:
        out = df.rename(columns={"Close": "close"})[["close"]]
    out = out.dropna().reset_index().rename(columns={"Date": "date"})
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def fetch_finance() -> Dict[str, pd.DataFrame]:
    frames = []
    metrics = []
    alerts = []
    for name, meta in INDICES.items():
        ticker = meta["ticker"]
        raw = yf.download(ticker, period="13mo", interval="1d", auto_adjust=True, progress=False, threads=False)
        if raw.empty:
            continue
        df = normalize_download(raw, ticker)
        df["index"] = name
        df["ticker"] = ticker
        df["return_12m_pct"] = (df["close"] / df["close"].iloc[0] - 1) * 100
        df["daily_return"] = df["close"].pct_change()
        df["ma30"] = df["close"].rolling(30).mean()
        df["deviation_from_30dma_pct"] = (df["close"] / df["ma30"] - 1) * 100
        latest = df.iloc[-1]
        vol = df["daily_return"].dropna().std() * math.sqrt(252) * 100
        metrics.append({
            "index": name, "ticker": ticker, "region": meta["region"], "proxy": meta["proxy"],
            "latest_date": latest["date"], "latest_close": round(float(latest["close"]), 2),
            "12m_return_pct": round(float(latest["return_12m_pct"]), 2),
            "ann_volatility_pct": round(float(vol), 2),
            "30dma": round(float(latest["ma30"]), 2) if not pd.isna(latest["ma30"]) else np.nan,
            "deviation_from_30dma_pct": round(float(latest["deviation_from_30dma_pct"]), 2) if not pd.isna(latest["deviation_from_30dma_pct"]) else np.nan,
        })
        if not pd.isna(latest["deviation_from_30dma_pct"]) and abs(latest["deviation_from_30dma_pct"]) > 3:
            alerts.append({"type": "30DMA deviation", "index": name, "ticker": ticker, "deviation_pct": round(float(latest["deviation_from_30dma_pct"]), 2), "threshold_pct": 3})
        frames.append(df)
    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    metrics_df = pd.DataFrame(metrics)
    returns = prices.pivot(index="date", columns="index", values="daily_return") if not prices.empty else pd.DataFrame()
    corr = returns.corr().round(3) if not returns.empty else pd.DataFrame()
    pd.DataFrame(alerts).to_csv(DATA / "alerts.csv", index=False)
    prices.to_csv(DATA / "market_prices.csv", index=False)
    metrics_df.to_csv(DATA / "market_metrics.csv", index=False)
    corr.to_csv(DATA / "correlation_matrix.csv")
    return {"prices": prices, "metrics": metrics_df, "corr": corr}


def latest_surprise_pct(ticker: str):
    try:
        ed = yf.Ticker(ticker).get_earnings_dates(limit=8)
        if ed is None or ed.empty:
            return np.nan
        for col in ed.columns:
            if "Surprise" in str(col) and "%" in str(col):
                vals = pd.to_numeric(ed[col], errors="coerce").dropna()
                if not vals.empty:
                    return round(float(vals.iloc[0]), 2)
    except Exception:
        pass
    return np.nan


def fetch_holdings() -> pd.DataFrame:
    rows = []
    for index_name, tickers in HOLDINGS.items():
        for rank, ticker in enumerate(tickers, 1):
            info = {}
            try:
                info = yf.Ticker(ticker).fast_info or {}
            except Exception:
                info = {}
            try:
                long_info = yf.Ticker(ticker).info or {}
            except Exception:
                long_info = {}
            pe = long_info.get("trailingPE") or long_info.get("forwardPE")
            rows.append({
                "index": index_name,
                "rank": rank,
                "ticker": ticker,
                "company": long_info.get("shortName") or long_info.get("longName") or ticker,
                "region": INDICES[index_name]["region"],
                "recent_earnings_surprise_pct": latest_surprise_pct(ticker),
                "price_to_earnings": round(float(pe), 2) if pe else np.nan,
                "source_note": "Top holdings watchlist/proxy; P/E and surprise via yfinance when available"
            })
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "holdings_valuation.csv", index=False)
    return df


def try_fetch_bls_oews_state() -> pd.DataFrame:
    url = "https://www.bls.gov/oes/special-requests/oesm25st.zip"
    headers = {"User-Agent": "Mozilla/5.0 healthcare-market-dashboard research"}
    try:
        r = requests.get(url, timeout=30, headers=headers)
        r.raise_for_status()
        z = zipfile.ZipFile(BytesIO(r.content))
        member = [m for m in z.namelist() if m.endswith((".xlsx", ".xls"))][0]
        df = pd.read_excel(z.open(member))
    except Exception:
        return pd.DataFrame()
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
    area_col = "area_title" if "area_title" in df.columns else "area_name"
    occ_col = "occ_code"
    keep = df[df[occ_col].isin(OCCS.values())].copy()
    if keep.empty:
        return pd.DataFrame()
    keep["occupation"] = keep[occ_col].map({v:k for k,v in OCCS.items()})
    for c in ["a_median", "a_mean", "tot_emp", "h_median"]:
        if c in keep.columns:
            keep[c] = pd.to_numeric(keep[c].astype(str).str.replace(",", ""), errors="coerce")
    return keep.rename(columns={area_col: "state"})


def fallback_state_base() -> pd.DataFrame:
    # Deterministic planning scaffold when BLS download is blocked. Wages are national medians
    # adjusted by coarse cost-region multipliers; dashboard labels these as modeled.
    high = {'CA','NY','MA','WA','OR','CT','NJ','MD','DC','AK','HI'}
    low = {'MS','AL','AR','LA','WV','KY','OK','TN','MO','SC'}
    rows = []
    for abbr, state in STATE_ABBR.items():
        mult = 1.18 if abbr in high else 0.90 if abbr in low else 1.0
        rural_pressure = 1.12 if abbr in {'MS','AL','AR','LA','WV','KY','OK','TN','NM','ND','SD','MT','WY'} else 1.0
        for occ, facts in CAREER_FACTS.items():
            rows.append({"state": state, "state_abbr": abbr, "occupation": occ, "a_median": round(facts["median_wage"]*mult), "tot_emp": np.nan, "data_quality": "modeled_fallback_bls_blocked", "rural_pressure": rural_pressure})
    return pd.DataFrame(rows)


def build_workforce() -> pd.DataFrame:
    bls = try_fetch_bls_oews_state()
    if bls.empty:
        base = fallback_state_base()
    else:
        base = bls[["state", "occupation", "a_median", "tot_emp"]].copy()
        base["data_quality"] = "BLS_OEWS_2025_download"
        base["state_abbr"] = base["state"].map({v:k for k,v in STATE_ABBR.items()})
        base["rural_pressure"] = 1.0
    rows = []
    for _, r in base.iterrows():
        occ = r["occupation"]
        facts = CAREER_FACTS[occ]
        exit_rate = facts["retirement_exit_rate_5y"]
        opening_density = facts["annual_openings"] / facts["jobs_2024"] * 100
        wage_gap = ((facts["median_wage"] - float(r["a_median"])) / facts["median_wage"]) * 100 if pd.notna(r["a_median"]) else 0
        # transparent proxy: higher projected exits + openings + low wage pressure = more shortage risk
        shortage = max(0, min(45, (exit_rate * 0.45 + opening_density * 1.2 + max(wage_gap, -10) * 0.25) * float(r.get("rural_pressure", 1.0))))
        for setting, weights in SETTING_WEIGHTS.items():
            rows.append({
                "state": r["state"], "state_abbr": r.get("state_abbr", ""), "occupation": occ, "setting": setting,
                "median_annual_wage": float(r["a_median"]) if pd.notna(r["a_median"]) else facts["median_wage"],
                "projected_retirement_exit_rate_5y_pct": exit_rate,
                "annual_openings_density_pct": round(opening_density, 2),
                "shortage_pct_proxy": round(shortage * weights[occ] / max(weights.values()) * (1.0 if setting != "Nursing facilities" else 1.08), 2),
                "supply_index": round(max(0, 100 - shortage), 1),
                "demand_index": round(min(100, shortage + opening_density * 5 + weights[occ] * 35), 1),
                "data_quality": r.get("data_quality", "unknown"),
            })
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "workforce_state_setting.csv", index=False)
    return df


def build_career_scorecard(workforce: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for occ, f in CAREER_FACTS.items():
        wage = f["median_wage"]
        roi_years = f["tuition_proxy"] / max(1, wage - 45000)
        avg_shortage = workforce[workforce.occupation == occ]["shortage_pct_proxy"].mean() if not workforce.empty else np.nan
        supply_demand_scenario = {"LPN": -28, "APRN": 67, "RN": 0}[occ]
        rows.append({
            "occupation": occ,
            "median_wage": wage,
            "growth_2034_pct": f["growth_2034_pct"],
            "annual_openings": f["annual_openings"],
            "retirement_exit_rate_5y_pct": f["retirement_exit_rate_5y"],
            "typical_education": f["typical_education"],
            "tuition_proxy": f["tuition_proxy"],
            "simple_payback_years_vs_45k_baseline": round(roi_years, 2),
            "regional_job_opening_density_pct": round(f["annual_openings"] / f["jobs_2024"] * 100, 2),
            "avg_shortage_pct_proxy": round(float(avg_shortage), 2) if pd.notna(avg_shortage) else np.nan,
            "supply_demand_scenario_pct": supply_demand_scenario,
            "economic_impact_proxy_usd_b": round((abs(supply_demand_scenario)/100) * f["jobs_2024"] * wage / 1e9, 2),
            "career_demand_score_0_100": round(min(100, f["growth_2034_pct"]*1.1 + (f["annual_openings"]/f["jobs_2024"]*100)*8 + f["retirement_exit_rate_5y"]*.8 + max(0, -supply_demand_scenario)*.4), 1)
        })
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "career_scorecard.csv", index=False)
    edu = pd.DataFrame([
        {"year": 2015, "associate_or_diploma_pct": 58, "bachelor_or_higher_pct": 42, "source": "NCSBN/JNR reported RN baccalaureate or higher rose from 42% in 2015 to 52% in 2024"},
        {"year": 2024, "associate_or_diploma_pct": 48, "bachelor_or_higher_pct": 52, "source": "NCSBN/JNR 2024 National Nursing Workforce Survey"},
    ])
    edu.to_csv(DATA / "education_attainment.csv", index=False)
    return df


def main():
    generated_at = datetime.now(timezone.utc).isoformat()
    finance = fetch_finance()
    holdings = fetch_holdings()
    workforce = build_workforce()
    scorecard = build_career_scorecard(workforce)
    manifest = {
        "generated_at_utc": generated_at,
        "files": sorted([p.name for p in DATA.glob("*.csv")]),
        "sources": SOURCES,
        "row_counts": {p.name: int(pd.read_csv(p).shape[0]) for p in DATA.glob("*.csv") if p.name != "correlation_matrix.csv"},
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
