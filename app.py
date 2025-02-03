import streamlit as st
import openai
import requests
import pandas as pd
import re
from datetime import datetime

# Load API Keys from Streamlit Secrets
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
FMP_API_KEY = st.secrets["FMP_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# Function to Fetch Stock Data from Alpha Vantage & Sector P/E from FMP
def fetch_fundamental_data(ticker):
    base_url_av = "https://www.alphavantage.co/query"

    # Fetch Company Overview from Alpha Vantage
    overview_response = requests.get(f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()
    
    # Get FMP Sector & Industry (Override AV)
    fmp_sector, fmp_industry = fetch_fmp_sector(ticker)

    # Fetch Sector P/E Ratio using FMP's sector
    sector_pe = fetch_sector_pe_ratio(fmp_sector)

    # Fetch Income & Balance Sheet Data
    income_response = requests.get(f"{base_url_av}?function=INCOME_STATEMENT&symbol={ticker}&apikey={AV_API_KEY}").json()
    balance_response = requests.get(f"{base_url_av}?function=BALANCE_SHEET&symbol={ticker}&apikey={AV_API_KEY}").json()

    # Extract Latest Reports
    latest_income = income_response.get("annualReports", [{}])[0]
    latest_balance = balance_response.get("annualReports", [{}])[0]

    # Calculate Debt/Equity Ratio
    total_assets = float(latest_balance.get("totalAssets", "0")) if latest_balance.get("totalAssets") else None
    total_liabilities = float(latest_balance.get("totalLiabilities", "0")) if latest_balance.get("totalLiabilities") else None
    shareholder_equity = total_assets - total_liabilities if total_assets and total_liabilities else None
    debt_equity_ratio = total_liabilities / shareholder_equity if shareholder_equity else "N/A"

    # Format Data for Display
    fundamental_data = {
        "Ticker": ticker,
        "Company Name": overview_response.get("Name", "N/A"),
        "Sector": fmp_sector,  # Use FMP sector, NOT AV's
        "Industry": fmp_industry,
        "Sector P/E": sector_pe,
        "Market Cap": f"{int(overview_response.get('MarketCapitalization', '0')):,}" if overview_response.get("MarketCapitalization") else "N/A",
        "Revenue": f"{int(latest_income.get('totalRevenue', '0')):,}" if latest_income.get("totalRevenue") else "N/A",
        "Net Income": f"{int(latest_income.get('netIncome', '0')):,}" if latest_income.get("netIncome") else "N/A",
        "Total Assets": f"{int(total_assets):,}" if total_assets else "N/A",
        "Total Liabilities": f"{int(total_liabilities):,}" if total_liabilities else "N/A",
        "P/E Ratio": overview_response.get("PERatio", "N/A"),
        "EPS": overview_response.get("EPS", "N/A"),
        "Debt/Equity Ratio": str(round(debt_equity_ratio, 2)) if debt_equity_ratio != "N/A" else "N/A",
        "ROE": overview_response.get("ReturnOnEquityTTM", "N/A"),
        "ROA": overview_response.get("ReturnOnAssetsTTM", "N/A"),
    }
    
    return fundamental_data

# Function to Fetch FMP's Sector & Industry Classification
def fetch_fmp_sector(ticker):
    """Fetch the correct sector & industry for a given stock from FMP."""
    url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data and isinstance(data, list):
            sector = data[0].get("sector", "N/A")
            industry = data[0].get("industry", "N/A")
            return sector, industry

    return "N/A", "N/A"

# Function to Fetch Sector P/E Ratio from FMP
def fetch_sector_pe_ratio(sector):
    """Fetch the P/E ratio for a given sector from FMP API with the required date parameter."""
    today_date = datetime.today().strftime('%Y-%m-%d')

    url = f"https://financialmodelingprep.com/api/v4/sector_price_earning_ratio?date={today_date}&exchange=NYSE&apikey={FMP_API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            return "N/A"

        sector_pe_dict = {entry["sector"]: entry["pe"] for entry in data}

        if sector in sector_pe_dict:
            return sector_pe_dict[sector]

        return "N/A"

    except requests.exceptions.RequestException:
        return "N/A"

# Streamlit UI - Enhanced Layout
st.set_page_config(page_title="AI Stock Screener", page_icon="📈", layout="centered")
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker below to get AI-generated fundamental analysis and a recommended buy price.")

# User Input for Stock Ticker
ticker = st.text_input("🔎 Enter a stock ticker (e.g., TSLA, AAPL):", max_chars=10)

if st.button("Analyze Stock"):
    if ticker:
        with st.spinner("Fetching data..."):
            data = fetch_fundamental_data(ticker)

            st.subheader("🏦 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

    else:
        st.error("❌ Please enter a valid stock ticker.")

