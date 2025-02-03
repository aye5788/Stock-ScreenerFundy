import streamlit as st
import requests
import openai
import pandas as pd
from datetime import datetime

# Load API Keys
FMP_API_KEY = st.secrets["FMP_API_KEY"]
AV_API_KEY = st.secrets["AV_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# **Fetch Company Profile (Sector, Industry) from FMP**
def fetch_company_profile(ticker):
    """Fetches the company profile, sector, and industry from FMP."""
    fmp_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    response = requests.get(fmp_url).json()

    if response and isinstance(response, list):
        company_data = response[0]
        return {
            "Company Name": company_data.get("companyName", "N/A"),
            "Sector": company_data.get("sector", "N/A"),
            "Industry": company_data.get("industry", "N/A")
        }
    return None

# **Fetch Fundamental Data (Revenue, Net Income, Market Cap) from AV**
def fetch_fundamental_data(ticker):
    """Fetches financial metrics from Alpha Vantage."""
    av_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}"
    response = requests.get(av_url).json()

    if "Symbol" not in response:
        return None

    return {
        "Market Cap": format_large_number(response.get("MarketCapitalization", "N/A")),
        "Stock Price": f"${response.get('52WeekHigh', 'N/A')}",  # AV does not provide real-time price in this endpoint
        "Revenue": format_large_number(response.get("RevenueTTM", "N/A")),
        "Net Income": format_large_number(response.get("NetIncomeTTM", "N/A")),
        "Total Assets": format_large_number(response.get("TotalAssets", "N/A")),
        "Total Liabilities": format_large_number(response.get("TotalLiabilities", "N/A")),
        "P/E Ratio": response.get("PERatio", "N/A")
    }

# **Fetch Sector P/E Ratio from FMP**
def fetch_sector_pe_ratio(sector):
    """Fetches the sector P/E ratio for a given sector from FMP."""
    date_today = datetime.today().strftime('%Y-%m-%d')
    sector_pe_url = f"https://financialmodelingprep.com/api/v4/sector_price_earning_ratio?date={date_today}&exchange=NYSE&apikey={FMP_API_KEY}"
    
    response = requests.get(sector_pe_url).json()

    if response:
        for entry in response:
            if entry["sector"] == sector:
                return round(float(entry["pe"]), 2)

    return "N/A"

# **Helper Function to Format Large Numbers**
def format_large_number(value):
    """Converts large numbers into readable formats like 1.2B, 3.4M, etc."""
    try:
        num = float(value)
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        return f"{num:,}"
    except:
        return value

# **Streamlit UI**
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker to get AI-powered fundamental analysis and a fair value estimate.")

ticker = st.text_input("Enter a stock ticker (e.g., TSLA, AAPL):", value="AAPL")

if st.button("Analyze Stock"):
    with st.spinner("Fetching data..."):
        company_profile = fetch_company_profile(ticker)
        fundamentals = fetch_fundamental_data(ticker)

        if not company_profile or not fundamentals:
            st.error("❌ Data not found for the given ticker.")
        else:
            sector_pe = fetch_sector_pe_ratio(company_profile["Sector"])
            data = {**company_profile, **fundamentals, "Sector P/E": sector_pe}

            st.subheader("📜 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

    with st.spinner("Running AI analysis..."):
        ai_analysis = generate_ai_analysis(data)
        st.markdown("### 🤖 AI Analysis")
        st.write(ai_analysis)

