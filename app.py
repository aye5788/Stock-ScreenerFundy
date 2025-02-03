import streamlit as st
import requests
import openai
import pandas as pd
from datetime import datetime

# **Load API Keys Correctly**
FMP_API_KEY = st.secrets["FMP_API_KEY"]  # ✅ Used for Company Profile & Sector P/E
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]  # ✅ Used for Fundamental Data from AV
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]  # ✅ Used for AI analysis

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
            "Stock Price": f"${company_data.get('price', 'N/A')}"
        }
    return None

# **Fetch Fundamental Data from Alpha Vantage (Corrected AV Endpoint)**
def fetch_fundamental_data(ticker):
    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}"
    response = requests.get(url).json()
    if "Symbol" not in response:
        return None
    return {
        "Market Cap": format_large_number(response.get("MarketCapitalization", "N/A")),
        "Revenue": format_large_number(response.get("RevenueTTM", "N/A")),
        "Net Income": format_large_number(response.get("NetIncomeTTM", "N/A")),
        "Total Assets": format_large_number(response.get("TotalAssets", "N/A")),
        "Total Liabilities": format_large_number(response.get("TotalLiabilities", "N/A")),
        "P/E Ratio": response.get("PERatio", "N/A")
    }

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
        fundamental_data = fetch_fundamental_data(ticker)
        sector_pe = fetch_sector_pe(company_profile["Sector"]) if company_profile else "N/A"

        if company_profile and fundamental_data:
            data = {
                "Ticker": ticker,
                **company_profile,
                **fundamental_data,
                "Sector P/E": sector_pe
            }

            # **Display Fundamental Data**
            st.subheader("📊 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            with st.spinner("Running AI analysis..."):
                ai_analysis = generate_ai_analysis(data)
                st.subheader("🤖 AI Analysis")
                st.markdown(f"<div style='background-color: #e8f5e9; padding: 10px; border-radius: 5px;'>{ai_analysis}</div>", unsafe_allow_html=True)


