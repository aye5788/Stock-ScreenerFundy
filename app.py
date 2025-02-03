import streamlit as st
import requests
import openai
import difflib
from datetime import datetime

# Load API Keys from Streamlit Secrets
FMP_API_KEY = st.secrets["FMP_API_KEY"]
ALPHA_VANTAGE_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# **Sector Mapping Fix**
SECTOR_MAPPING = {
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Healthcare": "Health Care",
    "Technology": "Information Technology",
    "Industrials": "Industrials",
    "Utilities": "Utilities",
    "Financial Services": "Financials",
    "Real Estate": "Real Estate",
    "Basic Materials": "Materials",
    "Energy": "Energy",
    "Communication Services": "Communication Services",
    "Life Sciences": "Health Care"  # Fix for ABBV
}

# **Function to Fetch Fundamental Data**
def fetch_fundamental_data(ticker):
    """Fetch fundamental data from Alpha Vantage & sector P/E from FMP."""
    base_url_av = "https://www.alphavantage.co/query"

    # **Company Overview from Alpha Vantage**
    overview_response = requests.get(
        f"{base_url_av}?function=OVERVIEW&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    ).json()

    # **Sector Mapping for Accuracy**
    av_sector = overview_response.get("Sector", "N/A")
    matched_sector = SECTOR_MAPPING.get(av_sector, av_sector)

    # **Fetch Stock Price**
    stock_price_response = requests.get(
        f"{base_url_av}?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    ).json()
    stock_price = stock_price_response.get("Global Quote", {}).get("05. price", "N/A")

    # **Fetch Sector P/E from FMP**
    sector_pe = fetch_sector_pe_ratio(matched_sector)

    # **Fetch Income Statement**
    income_response = requests.get(
        f"{base_url_av}?function=INCOME_STATEMENT&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    ).json()
    latest_income = income_response.get("annualReports", [{}])[0]

    # **Fetch Balance Sheet**
    balance_response = requests.get(
        f"{base_url_av}?function=BALANCE_SHEET&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    ).json()
    latest_balance = balance_response.get("annualReports", [{}])[0]

    # **Calculate Debt/Equity Ratio**
    total_assets = float(latest_balance.get("totalAssets", "0")) if latest_balance.get("totalAssets") else None
    total_liabilities = float(latest_balance.get("totalLiabilities", "0")) if latest_balance.get("totalLiabilities") else None
    shareholder_equity = total_assets - total_liabilities if total_assets and total_liabilities else None
    debt_equity_ratio = total_liabilities / shareholder_equity if shareholder_equity else "N/A"

    # **Prepare Data Dictionary**
    fundamental_data = {
        "Ticker": ticker,
        "Company Name": overview_response.get("Name", "N/A"),
        "Sector (Alpha Vantage)": av_sector,
        "Sector (FMP Matched)": matched_sector,
        "Sector P/E": sector_pe,
        "Market Cap": format_large_number(overview_response.get("MarketCapitalization", "0")),
        "Stock Price": f"${stock_price}",
        "Revenue": format_large_number(latest_income.get("totalRevenue", "0")),
        "Net Income": format_large_number(latest_income.get("netIncome", "0")),
        "Total Assets": format_large_number(latest_balance.get("totalAssets", "0")),
        "Total Liabilities": format_large_number(latest_balance.get("totalLiabilities", "0")),
        "P/E Ratio": overview_response.get("PERatio", "N/A"),
        "EPS": overview_response.get("EPS", "N/A"),
        "Debt/Equity Ratio": str(round(debt_equity_ratio, 2)) if debt_equity_ratio != "N/A" else "N/A",
    }

    return fundamental_data

# **Fetch Sector P/E Ratio from FMP**
def fetch_sector_pe_ratio(sector):
    """Fetches the sector P/E ratio from FMP API."""
    date_today = datetime.today().strftime("%Y-%m-%d")
    url = f"https://financialmodelingprep.com/api/v4/sector_price_earning_ratio?date={date_today}&exchange=NYSE&apikey={FMP_API_KEY}"
    
    response = requests.get(url).json()
    
    for entry in response:
        if entry.get("sector") == sector:
            return round(float(entry.get("pe", "N/A")), 2)

    return "N/A"

# **Format Large Numbers**
def format_large_number(value):
    """Converts large numbers into human-readable format (e.g., 2M, 3B)."""
    try:
        value = float(value)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        else:
            return f"{value:.2f}"
    except ValueError:
        return value

# **Analyze Stock with AI**
def analyze_with_gpt(fundamental_data):
    """Uses OpenAI GPT-4 to analyze the stock."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    You are a financial analyst evaluating the stock {fundamental_data['Ticker']} ({fundamental_data['Company Name']}).
    
    Based on the following data, analyze the company's financial health and estimate its fair value:
    - Sector: {fundamental_data['Sector (FMP Matched)']}
    - Sector P/E Ratio: {fundamental_data['Sector P/E']}
    - Stock P/E Ratio: {fundamental_data['P/E Ratio']}
    - Market Cap: {fundamental_data['Market Cap']}
    - Stock Price: {fundamental_data['Stock Price']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}
    
    Provide key takeaways and a **Fair Value Estimate** for the stock.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial analyst. Ensure response is structured with 'Key Takeaways' and 'Fair Value Estimate'."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content

# **Streamlit UI**
st.set_page_config(page_title="AI Stock Screener", page_icon="📈")
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
                ai_analysis = analyze_with_gpt(data)

                st.subheader("🤖 AI Analysis")
                st.success(ai_analysis)

    else:
        st.error("❌ Please enter a valid stock ticker.")

