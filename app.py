import streamlit as st
import openai
import requests
import pandas as pd
import re

# Load API Keys from Streamlit Secrets
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
FMP_API_KEY = st.secrets["FMP_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# Function to Format Large Numbers
def format_large_number(value):
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        return str(round(value, 2))
    except:
        return value

# Function to Fetch Stock Data from Alpha Vantage & Sector P/E from FMP
def fetch_fundamental_data(ticker):
    base_url_av = "https://www.alphavantage.co/query"

    # Fetch Company Overview from Alpha Vantage
    overview_response = requests.get(f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()
    
    # Extract Correct **Sector**
    company_sector = overview_response.get("Sector", "N/A")

    # Fetch Sector P/E Ratio from FMP
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
        "Market Cap": format_large_number(overview_response.get("MarketCapitalization", "0")),
        "Revenue": format_large_number(latest_income.get("totalRevenue", "0")),
        "Net Income": format_large_number(latest_income.get("netIncome", "0")),
        "Total Assets": format_large_number(total_assets),
        "Total Liabilities": format_large_number(total_liabilities),
        "P/E Ratio": overview_response.get("PERatio", "N/A"),
        "EPS": overview_response.get("EPS", "N/A"),
        "Debt/Equity Ratio": str(round(debt_equity_ratio, 2)) if debt_equity_ratio != "N/A" else "N/A",
        "ROE": overview_response.get("ReturnOnEquityTTM", "N/A"),
        "ROA": overview_response.get("ReturnOnAssetsTTM", "N/A"),
    }
    
    return fundamental_data

# Function to Fetch Sector P/E Ratio from FMP
def fetch_sector_pe_ratio(sector):
    base_url_fmp = "https://financialmodelingprep.com/api/v4/sector_price_earning_ratio"

    response = requests.get(f"{base_url_fmp}?date=2025-02-03&exchange=NYSE&apikey={FMP_API_KEY}").json()

    # Search for Matching Sector in FMP Response
    for entry in response:
        if entry.get("sector") == sector:
            return entry.get("pe", "N/A")

    return "N/A"  # If sector not found, return "N/A"

# Function to Analyze Stock Data with OpenAI GPT-4
def analyze_with_gpt(fundamental_data):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    You are a financial analyst evaluating the stock {fundamental_data['Ticker']} ({fundamental_data['Company Name']}).

    Based on the following fundamental data, determine if the company is a **growth stock**, **stable stock**, or **asset-heavy (financial/REIT)** and apply the appropriate valuation model.

    - Sector: {fundamental_data['Sector']}
    - Sector Average P/E Ratio: {fundamental_data['Sector P/E']}
    - Stock P/E Ratio: {fundamental_data['P/E Ratio']}
    - Market Cap: {fundamental_data['Market Cap']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - Total Assets: {fundamental_data['Total Assets']}
    - Total Liabilities: {fundamental_data['Total Liabilities']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}
    - ROE: {fundamental_data['ROE']}
    - ROA: {fundamental_data['ROA']}

    - **If Growth Stock (EPS Growth > 15%)**, apply **PEG-based valuation**.
    - **If Stable Stock**, use **Discounted Cash Flow (DCF) valuation**.
    - **If Financial or REIT**, use **Price-to-Book Ratio (P/B)**.

    Format the output as:

    **Key Takeaways:**  
    - (Insight 1)  
    - (Insight 2)  
    - (Insight 3)  

    **Fair Value Price: $XXX.XX** (on its own line)
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional stock analyst. Ensure the response is structured clearly with 'Key Takeaways' first and 'Fair Value Price' at the end."},
            {"role": "user", "content": prompt}
        ]
    )

    full_response = response.choices[0].message.content

    # Extract "Key Takeaways" and "Fair Value Price"
    takeaways_part = full_response.split("Fair Value Price:")[0].strip()
    fair_value_match = re.search(r"Fair Value Price: \$(\d+\.\d+)", full_response)
    fair_value_price = fair_value_match.group(0) if fair_value_match else "Not Available"

    return takeaways_part, fair_value_price

# Streamlit UI
st.title("📊 AI-Powered Stock Screener")

ticker = st.text_input("🔎 Enter a stock ticker (e.g., TSLA, AAPL):", max_chars=10)

if st.button("Analyze Stock"):
    if ticker:
        with st.spinner("Fetching data..."):
            data = fetch_fundamental_data(ticker)
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            with st.spinner("Running AI analysis..."):
                analysis, fair_value_price = analyze_with_gpt(data)

                st.subheader("🤖 AI Analysis")
                st.write(analysis)

                st.subheader("🎯 Fair Value Price")
                st.warning(fair_value_price)

    else:
        st.error("❌ Please enter a valid stock ticker.")

