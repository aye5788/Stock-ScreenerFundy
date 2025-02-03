import streamlit as st
import openai
import requests
import pandas as pd
import re
from datetime import datetime
from difflib import get_close_matches  # For fuzzy sector matching

# Load API Keys from Streamlit Secrets
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
FMP_API_KEY = st.secrets["FMP_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# Cache Sector List to Avoid Multiple API Calls
@st.cache_data
def fetch_fmp_sector_list():
    """Fetch the latest list of sectors from FMP"""
    url = f"https://financialmodelingprep.com/api/v4/sector_price_earning_ratio?date={datetime.today().strftime('%Y-%m-%d')}&exchange=NYSE&apikey={FMP_API_KEY}"
    response = requests.get(url).json()
    return [entry["sector"] for entry in response] if isinstance(response, list) else []

# Get Closest Matching Sector
def get_best_sector_match(av_sector, fmp_sectors):
    """Find the closest matching sector from FMP's sector list"""
    matches = get_close_matches(av_sector, fmp_sectors, n=1, cutoff=0.6)
    return matches[0] if matches else "N/A"

# Fetch Stock Data from Alpha Vantage & Sector P/E from FMP
def fetch_fundamental_data(ticker):
    base_url_av = "https://www.alphavantage.co/query"
    
    # Fetch Company Overview
    overview_response = requests.get(f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()
    
    # Extract Sector & Dynamically Match to FMP
    av_sector = overview_response.get("Sector", "N/A").strip()
    fmp_sector_list = fetch_fmp_sector_list()
    matched_sector = get_best_sector_match(av_sector, fmp_sector_list)

    # Fetch Sector P/E Ratio
    sector_pe = fetch_sector_pe_ratio(matched_sector)

    # Fetch Latest Stock Price
    stock_price = fetch_stock_price(ticker)

    # Fetch Financial Statements
    income_response = requests.get(f"{base_url_av}?function=INCOME_STATEMENT&symbol={ticker}&apikey={AV_API_KEY}").json()
    balance_response = requests.get(f"{base_url_av}?function=BALANCE_SHEET&symbol={ticker}&apikey={AV_API_KEY}").json()

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
        "Sector (Alpha Vantage)": av_sector,
        "Sector (FMP Matched)": matched_sector,
        "Sector P/E": sector_pe,
        "Market Cap": format_large_number(overview_response.get('MarketCapitalization', '0')),
        "Stock Price": f"${stock_price}",
        "Revenue": format_large_number(latest_income.get('totalRevenue', '0')),
        "Net Income": format_large_number(latest_income.get('netIncome', '0')),
        "Total Assets": format_large_number(total_assets),
        "Total Liabilities": format_large_number(total_liabilities),
        "P/E Ratio": overview_response.get("PERatio", "N/A"),
        "EPS": overview_response.get("EPS", "N/A"),
        "Debt/Equity Ratio": str(round(debt_equity_ratio, 2)) if debt_equity_ratio != "N/A" else "N/A",
        "ROE": overview_response.get("ReturnOnEquityTTM", "N/A"),
        "ROA": overview_response.get("ReturnOnAssetsTTM", "N/A"),
    }
    
    return fundamental_data

# Fetch Sector P/E Ratio from FMP
def fetch_sector_pe_ratio(sector):
    """Fetch the P/E ratio for a matched sector from FMP"""
    base_url_fmp = "https://financialmodelingprep.com/api/v4/sector_price_earning_ratio"
    today_date = datetime.today().strftime('%Y-%m-%d')

    try:
        response = requests.get(f"{base_url_fmp}?date={today_date}&exchange=NYSE&apikey={FMP_API_KEY}")
        data = response.json()

        for entry in data:
            if entry.get("sector", "").strip().upper() == sector.upper():
                return round(float(entry.get("pe", "N/A")), 2)

        return "N/A"
    except Exception as e:
        return "N/A"

# Fetch Latest Stock Price
def fetch_stock_price(ticker):
    """Fetch the latest stock price from Alpha Vantage"""
    base_url_av = "https://www.alphavantage.co/query"
    try:
        response = requests.get(f"{base_url_av}?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={AV_API_KEY}")
        data = response.json()
        latest_date = list(data["Time Series (Daily)"].keys())[0]
        return float(data["Time Series (Daily)"][latest_date]["4. close"])
    except Exception:
        return "N/A"

# AI Analysis with OpenAI GPT-4
def analyze_with_gpt(fundamental_data):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    You are a financial analyst evaluating {fundamental_data['Company Name']} ({fundamental_data['Ticker']}).

    Key fundamentals:
    - Sector: {fundamental_data['Sector (FMP Matched)']}
    - Sector P/E: {fundamental_data['Sector P/E']}
    - Stock P/E: {fundamental_data['P/E Ratio']}
    - Market Cap: {fundamental_data['Market Cap']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}

    Given the above, analyze if the stock is overvalued or undervalued.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "Provide a financial analysis."},
                  {"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# Streamlit UI
st.set_page_config(page_title="AI Stock Screener", page_icon="📈", layout="centered")
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker to get AI-powered fundamental analysis and a fair value estimate.")

ticker = st.text_input("🔎 Enter a stock ticker (e.g., TSLA, AAPL):", max_chars=10)

if st.button("Analyze Stock"):
    if ticker:
        with st.spinner("Fetching data..."):
            data = fetch_fundamental_data(ticker)
            st.subheader("🏦 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            with st.spinner("Running AI analysis..."):
                ai_analysis = analyze_with_gpt(data)
                st.subheader("🤖 AI Analysis")
                st.success(ai_analysis)

    else:
        st.error("❌ Please enter a valid stock ticker.")

