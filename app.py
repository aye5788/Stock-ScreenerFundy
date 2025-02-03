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

# Function to Format Large Numbers
def format_large_number(value):
    try:
        value = float(value)
        if value >= 1e12:
            return f"{value / 1e12:.2f}T"
        elif value >= 1e9:
            return f"{value / 1e9:.2f}B"
        elif value >= 1e6:
            return f"{value / 1e6:.2f}M"
        return f"{value:.2f}"
    except:
        return value

# Fetch Stock Data from Alpha Vantage & Sector P/E from FMP
def fetch_fundamental_data(ticker):
    base_url_av = "https://www.alphavantage.co/query"
    
    # Fetch Company Overview
    overview_response = requests.get(f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()
    
    # Extract Sector
    company_sector = overview_response.get("Sector", "N/A").strip()

    # Fetch Sector P/E Ratio
    sector_pe = fetch_sector_pe_ratio(company_sector)

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
        "Sector": company_sector,
        "Sector P/E": sector_pe,
        "Market Cap": format_large_number(overview_response.get('MarketCapitalization', '0')),
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

# Determine Fair Value Price (Stable vs Growth)
def determine_fair_value(fundamental_data):
    pe_ratio = fundamental_data.get("P/E Ratio", "N/A")
    eps = fundamental_data.get("EPS", "N/A")

    try:
        pe_ratio = float(pe_ratio)
        eps = float(eps)

        if pe_ratio < 20:  # Likely a stable company
            fair_value = eps * 15  # Conservative multiple
        else:  # Growth stock
            fair_value = eps * 30  # Aggressive multiple

        return round(fair_value, 2)
    except:
        return "Not Available"

# Analyze Stock Data with OpenAI GPT-4
def analyze_with_gpt(fundamental_data):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    fair_value = determine_fair_value(fundamental_data)

    prompt = f"""
    You are a financial analyst evaluating {fundamental_data['Company Name']} ({fundamental_data['Ticker']}).

    - Sector: {fundamental_data['Sector']}
    - Sector P/E Ratio: {fundamental_data['Sector P/E']}
    - Stock P/E Ratio: {fundamental_data['P/E Ratio']}
    - Market Cap: {fundamental_data['Market Cap']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}
    - Fair Value Estimate: {fair_value}

    Provide a brief analysis.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional stock analyst."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content, fair_value

# Streamlit UI
st.set_page_config(page_title="AI Stock Screener", page_icon="📈", layout="centered")
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker to get fundamental analysis and a fair value price.")

ticker = st.text_input("🔎 Enter a stock ticker (e.g., TSLA, AAPL):", max_chars=10)

if st.button("Analyze Stock"):
    if ticker:
        with st.spinner("Fetching data..."):
            data = fetch_fundamental_data(ticker)
            st.subheader("🏦 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            with st.spinner("Running AI analysis..."):
                analysis, fair_value = analyze_with_gpt(data)

                st.subheader("🤖 AI Analysis")
                st.success(analysis)
                st.subheader("💰 Fair Value Estimate")
                st.warning(f"${fair_value}")

    else:
        st.error("❌ Please enter a valid stock ticker.")
