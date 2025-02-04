import streamlit as st
import requests
import openai
import pandas as pd
from datetime import datetime

# **Load API Keys**
FMP_API_KEY = st.secrets["FMP_API_KEY"]  # ✅ Financial Modeling Prep for all data
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]  # ✅ OpenAI for AI analysis

# **Initialize OpenAI client**
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# **Format Large Numbers**
def format_large_number(value):
    try:
        value = float(value)
        if value >= 1e9:
            return f"{value / 1e9:.2f}B"
        elif value >= 1e6:
            return f"{value / 1e6:.2f}M"
        return f"{value:.2f}"
    except (ValueError, TypeError):
        return "N/A"

# **Fetch Company Profile from FMP**
def fetch_company_profile(ticker):
    url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    response = requests.get(url).json()
    if response and isinstance(response, list):
        company_data = response[0]
        return {
            "Company Name": company_data.get("companyName", "N/A"),
            "Sector": company_data.get("sector", "N/A"),
            "Industry": company_data.get("industry", "N/A"),
            "Stock Price": f"${company_data.get('price', 'N/A')}",
            "Market Cap": format_large_number(company_data.get("mktCap", "N/A")),
        }
    return None

# **Fetch Fundamental Data from FMP**
def fetch_fundamentals(ticker):
    url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
    response = requests.get(url).json()
    if response and isinstance(response, list):
        fundamentals = response[0]
        return {
            "Revenue": format_large_number(fundamentals.get("revenueTTM", "N/A")),
            "Net Income": format_large_number(fundamentals.get("netIncomeTTM", "N/A")),
            "Total Assets": format_large_number(fundamentals.get("totalAssets", "N/A")),
            "Total Liabilities": format_large_number(fundamentals.get("totalLiabilities", "N/A")),
            "P/E Ratio": fundamentals.get("peRatioTTM", "N/A"),
        }
    return None

# **Fetch Sector P/E from FMP**
def fetch_sector_pe(sector):
    url = f"https://financialmodelingprep.com/api/v4/sector_price_earning_ratio?date={datetime.today().strftime('%Y-%m-%d')}&exchange=NYSE&apikey={FMP_API_KEY}"
    response = requests.get(url).json()
    for entry in response:
        if entry["sector"].lower() == sector.lower():
            return entry["pe"]
    return "N/A"

# **Generate AI Analysis**
def generate_ai_analysis(data):
    prompt = f"""
    Analyze the following fundamental data for {data['Company Name']} ({data['Ticker']}):
    
    - Sector: {data['Sector']}
    - Industry: {data['Industry']}
    - Stock Price: {data['Stock Price']}
    - Market Cap: {data['Market Cap']}
    - Revenue: {data['Revenue']}
    - Net Income: {data['Net Income']}
    - Total Assets: {data['Total Assets']}
    - Total Liabilities: {data['Total Liabilities']}
    - P/E Ratio: {data['P/E Ratio']}
    - Sector P/E: {data['Sector P/E']}
    
    Provide an investment analysis and estimate a fair value price.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# **Streamlit UI**
st.title("📈 AI-Powered Stock Screener")
st.write("Enter a stock ticker below to get AI-powered fundamental analysis and a fair value estimate.")

ticker = st.text_input("Enter a stock ticker (e.g., TSLA, AAPL):", value="AAPL").upper()
if st.button("Analyze Stock"):
    with st.spinner("Fetching data..."):
        company_profile = fetch_company_profile(ticker)
        fundamentals = fetch_fundamentals(ticker)
        sector_pe = fetch_sector_pe(company_profile["Sector"]) if company_profile else "N/A"

        if company_profile and fundamentals:
            data = {
                "Ticker": ticker,
                **company_profile,
                **fundamentals,
                "Sector P/E": sector_pe
            }

            # **Display Fundamental Data**
            st.subheader("📊 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            # **Run AI Analysis**
            with st.spinner("Running AI analysis..."):
                ai_analysis = generate_ai_analysis(data)

            # **Display AI Analysis**
            st.subheader("🤖 AI Analysis")
            st.write(ai_analysis)
