import streamlit as st
import openai
import requests
import pandas as pd
import re
from datetime import datetime
from difflib import get_close_matches

# Load API Keys from Streamlit Secrets
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
FMP_API_KEY = st.secrets["FMP_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

def format_large_number(value):
    """Convert large numbers to human-readable format (B for billion, M for million)."""
    try:
        num = float(value)
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        else:
            return f"{num:,}"
    except:
        return "N/A"

@st.cache_data
def fetch_fmp_sector_list():
    """Fetch latest sector list from FMP"""
    url = f"https://financialmodelingprep.com/api/v4/sector_price_earning_ratio?date={datetime.today().strftime('%Y-%m-%d')}&exchange=NYSE&apikey={FMP_API_KEY}"
    response = requests.get(url).json()
    return {entry["sector"]: round(float(entry["pe"]), 2) for entry in response if "pe" in entry}

def get_best_sector_match(av_sector, fmp_sectors):
    """Find closest matching sector from FMP"""
    matches = get_close_matches(av_sector, list(fmp_sectors.keys()), n=1, cutoff=0.6)
    return matches[0] if matches else "N/A"

def fetch_fundamental_data(ticker):
    base_url_av = "https://www.alphavantage.co/query"
    
    overview_response = requests.get(f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()
    av_sector = overview_response.get("Sector", "N/A").strip()
    
    fmp_sectors = fetch_fmp_sector_list()
    matched_sector = get_best_sector_match(av_sector, fmp_sectors)
    sector_pe = fmp_sectors.get(matched_sector, "N/A")

    stock_price = fetch_stock_price(ticker)

    income_response = requests.get(f"{base_url_av}?function=INCOME_STATEMENT&symbol={ticker}&apikey={AV_API_KEY}").json()
    balance_response = requests.get(f"{base_url_av}?function=BALANCE_SHEET&symbol={ticker}&apikey={AV_API_KEY}").json()

    latest_income = income_response.get("annualReports", [{}])[0]
    latest_balance = balance_response.get("annualReports", [{}])[0]

    total_assets = latest_balance.get("totalAssets", "0")
    total_liabilities = latest_balance.get("totalLiabilities", "0")
    shareholder_equity = float(total_assets) - float(total_liabilities) if total_assets and total_liabilities else None
    debt_equity_ratio = float(total_liabilities) / shareholder_equity if shareholder_equity else "N/A"

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

def fetch_stock_price(ticker):
    """Fetch the latest stock price from Alpha Vantage."""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={AV_API_KEY}"
    response = requests.get(url).json()
    return response.get("Global Quote", {}).get("05. price", "N/A")

def analyze_with_gpt(fundamental_data):
    """Use GPT-4 to analyze stock fundamentals and estimate fair value."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    You are a financial analyst evaluating the stock {fundamental_data['Ticker']} ({fundamental_data['Company Name']}).

    Based on the following fundamental data, provide an analysis of the company's financial health and estimate a fair value price:

    - Sector: {fundamental_data['Sector (FMP Matched)']}
    - Sector P/E: {fundamental_data['Sector P/E']}
    - Stock P/E Ratio: {fundamental_data['P/E Ratio']}
    - Market Cap: {fundamental_data['Market Cap']}
    - Stock Price: {fundamental_data['Stock Price']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}
    - ROE: {fundamental_data['ROE']}
    - ROA: {fundamental_data['ROA']}

    Format the output as:

    **Key Takeaways:**  
    - (Insight 1)  
    - (Insight 2)  
    - (Insight 3)  

    **Fair Value Estimate: $XXX.XX**
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial analyst. Provide a well-structured financial evaluation."},
            {"role": "user", "content": prompt}
        ]
    )

    full_response = response.choices[0].message.content
    takeaways_part = full_response.split("Fair Value Estimate:")[0].strip()
    fair_value_match = re.search(r"Fair Value Estimate: \$(\d+\.\d+)", full_response)
    fair_value = fair_value_match.group(0) if fair_value_match else "N/A"

    return takeaways_part, fair_value

# Streamlit UI
st.set_page_config(page_title="AI Stock Screener", page_icon="📈", layout="centered")
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker below to get AI-generated fundamental analysis and a fair value estimate.")

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
                st.success("### Key Takeaways")
                for line in analysis.split("\n"):
                    if line.strip():
                        st.write(f"🔹 {line}")

                st.subheader("💰 Fair Value Estimate")
                st.warning(fair_value)

    else:
        st.error("❌ Please enter a valid stock ticker.")
