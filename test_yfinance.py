import yfinance as yf
import json

def get_etf_info(symbol):
    """
    Extract ETF data matching your diagram parameters
    """
    etf = yf.Ticker(symbol)
    info = etf.info
    
    # Extract only the boxed parameters from your diagram
    etf_data = {
        "symbol": symbol,
        "name": info.get("longName", ""),
        
        # Parameters from your diagram boxes
        "domicile": info.get("region", ""),
        "exchange": info.get("exchange", ""),
        "index": info.get("category", ""),
        
        "volume": info.get("volume", 0),
        "aum": info.get("totalAssets", 0),
        "currency": info.get("currency", ""),
        "ucit": info.get("legalType", ""),
        
        "asset_class": info.get("category", ""),
        "amc": info.get("fundFamily", ""),
        "expense_ratio": info.get("netExpenseRatio", 0),
        
        "accumulating_or_distributing": "Distributing" if info.get("yield", 0) > 0 else "Accumulating",
        "dividend_yield": info.get("dividendYield", 0),
    }
    
    return etf_data

# ETFs to process
etfs = [
    {"symbol": "CSPX.L", "name": "iShares Core SP 500 UCITS ETF"},
    {"symbol": "IWDA.L", "name": "iShares Core MSCI World UCITS ETF"}
]

print("Fetching data from yfinance...\n")

all_data = {}

for etf in etfs:
    symbol = etf["symbol"]
    try:
        print(f"Processing {symbol}...")
        data = get_etf_info(symbol)
        all_data[symbol] = data
        print(f"✓ Got data for {symbol}\n")
    except Exception as e:
        print(f"✗ Error getting {symbol}: {e}\n")
        all_data[symbol] = {"error": str(e)}

# Save all data to single JSON file
output_file = "yfinance_responses.json"
with open(output_file, "w") as f:
    json.dump(all_data, f, indent=2)

print("\n" + "="*50)
print(f"✓ All yfinance data saved to {output_file}")
print("="*50)

# Print summary
print("\nData fetched for:")
for symbol in all_data.keys():
    print(f"  - {symbol}")