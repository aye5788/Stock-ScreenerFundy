import streamlit as st
import openai
import requests
import pandas as pd

# Set API keys
FMP_API_KEY = "YOUR_FMP_API_KEY"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# Function to fetch fundamental data from FMP
def fetch_fundamental_data(ticker):
    base_url = "https://financialmodelingprep.com/api/v3"
    
    # Fetch company profile
    profile_url = f"{base_url}/profile/{ticker}?apikey={FMP_API_KEY}"
    profile_response = requests.get(profile_url).json()

    # Validate profile response
    if not profile_response or not isinstance(profile_response, list):
        st.error("Error fetching company profile data!")
        return {}

    company_data = profile_response[0] if profile_response else {}

    # Fetch P/E Ratio from Ratios API
    ratios_url = f"{base_url}/ratios/{ticker}?period=annual&limit=1&apikey={FMP_API_KEY}"
    ratios_response = requests.get(ratios_url).json()

    # Validate ratios response
    pe_ratio = "N/A"
    if ratios_response and isinstance(ratios_response, list) and ratios_response[0].get("peRatio"):
        pe_ratio = ratios_response[0]["peRatio"]

    # Format large numbers
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

    # Create data dictionary
    data = {
        "Ticker": ticker,
        "Company Name": company_data.get("companyName", "N/A"),
        "Sector": company_data.get("sector", "N/A"),
        "Industry": company_data.get("industry", "N/A"),
        "Stock Price": format_large_number(company_data.get("price", "N/A")),
        "Market Cap": format_large_number(company_data.get("mktCap", "N/A")),
        "Revenue": format_large_number(company_data.get("revenue", "N/A")),
        "Net Income": format_large_number(company_data.get("netIncome", "N/A")),
        "Total Assets": format_large_number(company_data.get("totalAssets", "N/A")),
        "Total Liabilities": format_large_number(company_data.get("totalLiabilities", "N/A")),
        "P/E Ratio": pe_ratio,
    }

    return data

# Function to generate AI analysis using OpenAI
def generate_ai_analysis(data):
    openai.api_key = OPENAI_API_KEY

    prompt = f"""
    Analyze the following company's fundamentals and provide insights:
    
    - Sector: {data['Sector']}
    - Industry: {data['Industry']}
    - Stock Price: {data['Stock Price']}
    - Market Cap: {data['Market Cap']}
    - Revenue: {data['Revenue']}
    - Net Income: {data['Net Income']}
    - P/E Ratio: {data['P/E Ratio']}

    Provide a structured financial analysis.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a financial analyst."},
                  {"role": "user", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"]

# Streamlit UI
st.title("📈 AI-Powered Stock Screener")
st.write("Enter a stock ticker below to get AI-powered fundamental analysis and a fair value estimate.")

ticker = st.text_input("Enter a stock ticker (e.g., TSLA, AAPL):", value="AAPL")
if st.button("Analyze Stock"):
    with st.spinner("Fetching data..."):
        data = fetch_fundamental_data(ticker)
        if data:  # Ensure data is valid before displaying
            st.subheader("📊 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))
        else:
            st.error("No data retrieved. Please check the ticker or API response.")

    with st.spinner("Running AI analysis..."):
        if data:  # Only run AI analysis if data is available
            ai_analysis = generate_ai_analysis(data)
            st.subheader("🤖 AI Analysis")
            st.write(ai_analysis)
