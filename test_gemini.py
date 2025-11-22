import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

def get_etf_data_from_gemini(symbol):
    """
    Ask Gemini to provide ETF data
    """
    prompt = f"""
You are a financial data expert providing ETF information.
DO NOT assume or fabricate information.
If a field is not available or you're uncertain, return "Not Available".

Provide detailed information for the ETF with symbol: {symbol}

Return ONLY a JSON object with these exact fields:
{{
  "symbol": "",
  "name": "",
  "domicile": "",
  "exchange": "",
  "index": "",
  "volume": 0,
  "aum": 0,
  "currency": "",
  "ucit": "",
  "asset_class": "",
  "amc": "",
  "expense_ratio": 0,
  "accumulating_or_distributing": "",
  "dividend_yield": 0
}}

Field descriptions:
- symbol: ETF ticker symbol
- name: Full ETF name
- domicile: Country of domicile
- exchange: Primary exchange
- index: Index being tracked (e.g., "S&P 500")
- volume: Daily trading volume
- aum: Assets under management (in USD)
- currency: Trading currency
- ucit: UCITS classification ("UCITS" or "Non-UCITS")
- asset_class: One of: Equity, Bond, Commodity, Real Estate, Money Market
- amc: Asset Management Company
- expense_ratio: Annual expense ratio
- accumulating_or_distributing: "Accumulating" or "Distributing"
- dividend_yield: Dividend yield percentage

Return ONLY the JSON, no explanation.
"""
    
    response = model.generate_content(prompt)
    text = response.text.strip()
    
    # Extract JSON from response
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    return json.loads(text)

# Test
if __name__ == "__main__":
    # ETFs to process
    etfs = [
        {"symbol": "CSPX.L", "name": "iShares Core SP 500 UCITS ETF"},
        {"symbol": "IWDA.L", "name": "iShares Core MSCI World UCITS ETF"}
    ]
    
    print("Fetching data from Gemini...\n")
    
    all_data = {}
    
    for etf in etfs:
        symbol = etf["symbol"]
        try:
            print(f"Asking Gemini for {symbol}...")
            data = get_etf_data_from_gemini(symbol)
            all_data[symbol] = data
            print(f"✓ Got data for {symbol}\n")
        except Exception as e:
            print(f"✗ Error getting {symbol}: {e}\n")
            all_data[symbol] = {"error": str(e)}
    
    # Save all data to single JSON file
    output_file = "gemini_responses.json"
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=2)
    
    print("\n" + "="*50)
    print(f"✓ All Gemini data saved to {output_file}")
    print("="*50)
    
    # Print summary
    print("\nData fetched for:")
    for symbol in all_data.keys():
        print(f"  - {symbol}")