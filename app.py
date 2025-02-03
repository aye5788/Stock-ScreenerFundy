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

# Function to Format Large Numbers (e.g., 1,234,567,890 → "1.23B")
def format_large_number(value):
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        else:
            return f"{value:,.0f}"
    except (TypeError, ValueError):
        return "N/A"

# Function to Fetch Sector P/E Ratio from FMP
def fetch_sector_pe_ratio(sector):
    base_url_fmp = "https://financialmodelingprep.com/api/v4/sector_price_earning_ratio"
    today_date = datetime.today().strftime('%Y-%m-%d')  # Required "YYYY-MM-DD" format

    try:
        response = requests.get(f"{base_url_fmp}?date={today_date}&apikey={FMP_API_KEY}")
        data = response.json()

        # Ensure case-insensitive sector matching
        sector_upper = sector.strip().upper()
        for entry in data:
            if entry.get("sector", "").strip().upper() == sector_upper:
                return round(float(entry.get("pe", "N/A")), 2)

        print(f"❌ No Sector Match Found for {sector}, returning N/A")
        return "N/A"

    except Exception as e:
        print(f"❌ Sector P/E API Request Failed: {str(e)}")
        return "N/A"

# Function to Fetch Stock Data from Alpha Vantage
def fetch_fundamental_data(ticker):
    base_url_av = "https://www.alphavantage.co/query"

    # Fetch Company Overview
    overview_response = requests.get(f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()
    company_sector = overview_response.get("Sector", "N/A")
    sector_pe = fetch_sector_pe_ratio(company_sector)

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
        "Sector": company_sector,
        "Sector P/E": sector_pe,
        "Market Cap": format_large_number(overview_response.get("MarketCapitalization", "N/A")),
        "Revenue": format_large_number(latest_income.get("totalRevenue", "N/A")),
        "Net Income": format_large_number(latest_income.get("netIncome", "N/A")),
        "Total Assets": format_large_number(total_assets),
        "Total Liabilities": format_large_number(total_liabilities),
        "P/E Ratio": overview_response.get("PERatio", "N/A"),
        "EPS": overview_response.get("EPS", "N/A"),
        "Debt/Equity Ratio": str(round(debt_equity_ratio, 2)) if debt_equity_ratio != "N/A" else "N/A",
        "ROE": f"{float(overview_response.get('ReturnOnEquityTTM', 0)) * 100:.2f}%",
        "ROA": f"{float(overview_response.get('ReturnOnAssetsTTM', 0)) * 100:.2f}%",
    }
    
    return fundamental_data

# Function to Estimate Fair Value Price
def estimate_fair_value(fundamental_data):
    pe_ratio = float(fundamental_data["P/E Ratio"]) if fundamental_data["P/E Ratio"] != "N/A" else None
    sector_pe = float(fundamental_data["Sector P/E"]) if fundamental_data["Sector P/E"] != "N/A" else None
    eps = float(fundamental_data["EPS"]) if fundamental_data["EPS"] != "N/A" else None

    if pe_ratio and eps:
        # Valuation based on Sector P/E
        if sector_pe:
            fair_value = round(sector_pe * eps, 2)
        else:
            fair_value = round(pe_ratio * eps, 2)

        return f"${fair_value:.2f}"

    return "N/A"

# AI-Based Stock Analysis
def analyze_with_gpt(fundamental_data, fair_value):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    You are a financial analyst evaluating {fundamental_data['Ticker']} ({fundamental_data['Company Name']}).
    
    Based on these fundamentals, provide a summary:
    - Sector: {fundamental_data['Sector']}
    - Sector P/E: {fundamental_data['Sector P/E']}
    - P/E Ratio: {fundamental_data['P/E Ratio']}
    - Market Cap: {fundamental_data['Market Cap']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}
    - ROE: {fundamental_data['ROE']}
    - ROA: {fundamental_data['ROA']}
    - Fair Value Price: {fair_value}

    Structure the response with:
    - **Key Takeaways** (bullet points)
    - **Fair Value Price: $XXX.XX** (on its own line)
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial analyst providing investment insights."},
            {"role": "user", "content": prompt}
        ]
    )

    full_response = response.choices[0].message.content
    return full_response

# Streamlit UI
st.set_page_config(page_title="AI Stock Screener", page_icon="📈", layout="centered")
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker below to get AI-generated fundamental analysis and a recommended fair value price.")

ticker = st.text_input("🔎 Enter a stock ticker (e.g., TSLA, AAPL):", max_chars=10)

if st.button("Analyze Stock"):
    if ticker:
        with st.spinner("Fetching data..."):
            data = fetch_fundamental_data(ticker)
            fair_value = estimate_fair_value(data)

            st.subheader("🏦 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            with st.spinner("Running AI analysis..."):
                analysis = analyze_with_gpt(data, fair_value)

                st.subheader("🤖 AI Analysis")
                st.success(analysis)

            st.subheader("💰 Fair Value Estimate")
            st.warning(fair_value if fair_value != "N/A" else "Not Available")

    else:
        st.error("❌ Please enter a valid stock ticker.")
