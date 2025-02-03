import streamlit as st
import openai
import requests
import pandas as pd

# Access API Keys Securely from Streamlit Secrets
AV_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# Function to Fetch Fundamental Data from Alpha Vantage
def fetch_fundamental_data(ticker):
    base_url = "https://www.alphavantage.co/query"

    # Fetch Company Overview
    overview_response = requests.get(f"{base_url}?function=OVERVIEW&symbol={ticker}&apikey={AV_API_KEY}").json()

    # Fetch Income Statement
    income_response = requests.get(f"{base_url}?function=INCOME_STATEMENT&symbol={ticker}&apikey={AV_API_KEY}").json()

    # Fetch Balance Sheet
    balance_response = requests.get(f"{base_url}?function=BALANCE_SHEET&symbol={ticker}&apikey={AV_API_KEY}").json()

    # Extract the latest financial reports
    latest_income = income_response.get("annualReports", [{}])[0]
    latest_balance = balance_response.get("annualReports", [{}])[0]

    # Extract values and compute Debt/Equity Ratio
    total_assets = float(latest_balance.get("totalAssets", "0")) if latest_balance.get("totalAssets") else None
    total_liabilities = float(latest_balance.get("totalLiabilities", "0")) if latest_balance.get("totalLiabilities") else None
    shareholder_equity = total_assets - total_liabilities if total_assets and total_liabilities else None
    debt_equity_ratio = total_liabilities / shareholder_equity if shareholder_equity else "N/A"

    # Convert all numeric values to strings for table display
    fundamental_data = {
        "Ticker": ticker,
        "Company Name": overview_response.get("Name", "N/A"),
        "Market Cap": str(overview_response.get("MarketCapitalization", "N/A")),
        "Revenue": str(latest_income.get("totalRevenue", "N/A")),
        "Net Income": str(latest_income.get("netIncome", "N/A")),
        "Total Assets": str(total_assets) if total_assets else "N/A",
        "Total Liabilities": str(total_liabilities) if total_liabilities else "N/A",
        "P/E Ratio": str(overview_response.get("PERatio", "N/A")),
        "EPS": str(overview_response.get("EPS", "N/A")),
        "Debt/Equity Ratio": str(round(debt_equity_ratio, 2)) if debt_equity_ratio != "N/A" else "N/A",
        "ROE": str(overview_response.get("ReturnOnEquityTTM", "N/A")),
        "ROA": str(overview_response.get("ReturnOnAssetsTTM", "N/A")),
        "Current Price": str(overview_response.get("AnalystTargetPrice", "N/A")),  # If available
    }
    
    return fundamental_data

# Function to Analyze Stock Data with OpenAI GPT-4
def analyze_with_gpt(fundamental_data):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    You are a financial analyst evaluating the stock {fundamental_data['Ticker']} ({fundamental_data['Company Name']}).
    
    Based on the following fundamental data, summarize the company's financial health and investment potential in 3-5 bullet points:

    - Market Cap: {fundamental_data['Market Cap']}
    - Revenue: {fundamental_data['Revenue']}
    - Net Income: {fundamental_data['Net Income']}
    - Total Assets: {fundamental_data['Total Assets']}
    - Total Liabilities: {fundamental_data['Total Liabilities']}
    - P/E Ratio: {fundamental_data['P/E Ratio']}
    - EPS: {fundamental_data['EPS']}
    - Debt/Equity Ratio: {fundamental_data['Debt/Equity Ratio']}
    - ROE: {fundamental_data['ROE']}
    - ROA: {fundamental_data['ROA']}
    
    Additionally, provide a **target buy price** based on valuation metrics such as:
    - Comparing the current P/E ratio to a reasonable range (e.g., 15-25).
    - Calculating a fair value estimate based on EPS and a reasonable P/E.
    - Applying a discount of 10-20% to ensure a margin of safety.

    **Return the response in plain text. Avoid using markdown formatting like underscores or asterisks.**
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional stock analyst. Ensure the response is in plain text without markdown formatting."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content

# 🎨 Streamlit UI - Enhanced Layout
st.set_page_config(page_title="AI Stock Screener", page_icon="📈", layout="centered")
st.title("📊 AI-Powered Stock Screener")
st.write("Enter a stock ticker below to get AI-generated fundamental analysis and a recommended buy price.")

# User Input for Stock Ticker
ticker = st.text_input("🔎 Enter a stock ticker (e.g., TSLA, AAPL):", max_chars=10)

if st.button("Analyze Stock"):
    if ticker:
        with st.spinner("Fetching data..."):
            data = fetch_fundamental_data(ticker)

            # ✅ Display Financial Data in a Clean Table
            st.subheader("🏦 Fundamental Data Summary")
            st.dataframe(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

            with st.spinner("Running AI analysis..."):
                analysis = analyze_with_gpt(data)

                # 🎯 AI Analysis with Target Buy Price
                st.subheader("🤖 AI Analysis")
                st.success("### Key Takeaways")
                
                # **Ensure text is displayed in a normal font**
                clean_text = analysis.replace("_", "").replace("*", "")  

                for line in clean_text.split("\n"):
                    if line.strip():
                        if "Target Buy Price" in line:
                            st.warning(f"🎯 {line}")  # Highlight target buy price
                        else:
                            st.write(f"🔹 {line}")

    else:
        st.error("❌ Please enter a valid stock ticker.")

