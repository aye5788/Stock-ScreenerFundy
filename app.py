import streamlit as st
import openai
import requests
import pandas as pd
import re

# Load API Keys from Streamlit Secrets
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
FMP_API_KEY = st.secrets["FMP_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

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

# Function to Fetch Sector P/E Ratio from FMP
def fetch_sector_pe_ratio(sector):
    base_url_fmp = "https://financialmodelingprep.com/api/v4/sectors-pe-ratio"

    response = requests.get(f"{base_url_fmp}?apikey={FMP_API_KEY}").json()

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

    Based on the following fundamental data, summarize the company's financial health and investment potential:

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

    - Compare the stock’s P/E ratio to its **sector average P/E** to determine if it is **undervalued or overvalued.**
    - Apply a **discount (10-20%) if the stock appears overvalued.**
    
    Format the output as:

    **Key Takeaways:**  
    - (Insight 1)  
    - (Insight 2)  
    - (Insight 3)  

    **Target Entry Point: $XXX.XX** (on its own line)
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional stock analyst. Ensure the response is structured clearly with 'Key Takeaways' first and 'Target Entry Point' at the end."},
            {"role": "user", "content": prompt}
        ]
    )

    full_response = response.choices[0].message.content

    # Extract "Key Takeaways" and "Target Entry Point"
    takeaways_part = full_response.split("Target Entry Point:")[0].strip()
    target_price_match = re.search(r"Target Entry Point: \$(\d+\.\d+)", full_response)
    target_price = target_price_match.group(0) if target_price_match else "Not Available"

    return takeaways_part, target_price

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

            with st.spinner("Running AI analysis..."):
                analysis, target_price = analyze_with_gpt(data)

                st.subheader("🤖 AI Analysis")
                st.success("### Key Takeaways")
                for line in analysis.split("\n"):
                    if line.strip():
                        st.write(f"🔹 {line}")

                st.subheader("🎯 Target Entry Point")
                st.warning(target_price)

    else:
        st.error("❌ Please enter a valid stock ticker.")

