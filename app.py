import streamlit as st
import requests
import openai
import pandas as pd
from datetime import datetime

# Load API Keys
FMP_API_KEY = st.secrets["FMP_API_KEY"]
ALPHA_VANTAGE_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# **Fetch Company Profile (Sector, Industry, Company Name) from FMP**
def fetch_company_profile(ticker):
    """Fetches the company profile, sector, and industry from FMP."""
    fmp_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    response = requests.get(fmp_url).json()

    if response and isinstance(response, list):
        company_data = response[0]
        return {
            "Company Name": company_data.get("companyName", "N/A"),
            "Sector": company_data.get("sector", "N/A"),
            "Industry": company_data.get("industry", "N/A"),
            "Stock Price": f"${company_data.get('price', 'N/A')}"
        }
    return None

# **Fetch Fundamental Data (Revenue, Net Income, Market Cap) from AV**
def fetch_fundamental_data(ticker):
    """Fetches financial metrics from Alpha Vantage."""
    av_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    response = requests.get(av_url).json()

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

# **AI Analysis Function**
def generate_ai_analysis(data):
    """Generates AI-driven fundamental analysis using OpenAI."""
    prompt = f"""
    Analyze the following stock's financial fundamentals:
    
    - **Company Name**: {data['Company Name']}
    - **Sector**: {data['Sector']}
    - **Industry**: {data['Industry']}
    - **Market Cap**: {data['Market Cap']}
    - **Stock Price**: {data['Stock Price']}
    - **Revenue**: {data['Revenue']}
    - **Net Income**: {data['Net Income']}
    - **Total Assets**: {data['Total Assets']}
    - **Total Liabilities**: {data['Total Liabilities']}
    - **P/E Ratio**: {data['P/E Ratio']}
    - **Sector P/E**: {data['Sector P/E']}
    
    Provide a **detailed fundamental analysis** highlighting:
    - How the stock compares to its sector P/E.
    - The company's financial strength based on assets and liabilities.
    - Profitability analysis based on revenue and net income.
    - Debt concerns if applicable.
    - Investment considerations based on valuation.
    
    End with a **fair value estimate** for this stock based on its fundamentals.
    """

    openai.api_key = OPENAI_API_KEY
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"]

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

