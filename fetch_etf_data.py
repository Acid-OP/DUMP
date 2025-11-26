"""
ETF Data Fetcher
Fetches ETF data from FMP API and enriches it with Gemini AI analysis.
Includes intelligent fallback when FMP data is incomplete.
"""

import requests
import google.generativeai as genai
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# API Configuration
FMP_API_KEY = os.getenv("FMP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FMP_BASE_URL = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable/profile")

# File Configuration
INPUT_FILE = os.getenv("INPUT_FILE", "12-nov-2025-ucits-list.json")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "etf_data.json")

# Batch Configuration
# Vikas, change the number here accordingly (e.g., 50, 100, 200)
BATCH_SIZE = 100  # Process ETFs in batches to manage API rate limits

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')


def get_fmp_data(symbol):
    """Fetch ETF profile data from FMP API."""
    try:
        url = f"{FMP_BASE_URL}?symbol={symbol}&apikey={FMP_API_KEY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        if not data or len(data) == 0:
            return None
        
        full_profile = data[0] if isinstance(data, list) else data
        
        return {
            "full_profile": full_profile,
            "domicile": full_profile.get("country", "") or "Not Available",
            "exchange": full_profile.get("exchange", "") or "Not Available",
            "volume": full_profile.get("volume", 0) or 0,
            "aum": full_profile.get("marketCap", 0) or 0,
            "currency": full_profile.get("currency", "") or "Not Available",
            "lastDividend": full_profile.get("lastDividend", 0) or 0,
            "price": full_profile.get("price", 0) or 0
        }
        
    except Exception:
        return None


def get_gemini_analysis(symbol, fmp_full_profile, etf_name):
    """Use Gemini AI to extract ETF metadata and fill missing FMP fields."""
    try:
        description = fmp_full_profile.get("description", "")
        company_name = fmp_full_profile.get("companyName", "")
        
        # Check what's missing from FMP
        fmp_has_domicile = fmp_full_profile.get("country")
        fmp_has_exchange = fmp_full_profile.get("exchange")
        fmp_has_currency = fmp_full_profile.get("currency")
        fmp_has_aum = fmp_full_profile.get("marketCap", 0) > 0
        
        prompt = f"""You are a financial data analyst specializing in ETFs.
                DO NOT assume or fabricate information. If uncertain, return null.

                ETF Information:
                - Symbol: {symbol}
                - Full Name: {etf_name}
                - Company Name: {company_name}
                - Description: {description[:500] if description else "Not available"}

                FMP Profile Data:
                {json.dumps(fmp_full_profile, indent=2)}

                Extract these fields:

                1. **index** - The actual index this ETF tracks (e.g., 'S&P 500', 'MSCI World Index')
                2. **asset_class** - ONE of: Equity, Bond, Commodity, Real Estate, Money Market
                3. **is_accumulating** - Boolean: true if dividends reinvested, false if distributed
                4. **amc** - Asset Management Company parent name (e.g., 'BlackRock' for iShares)
                """

        # Add fallback fields only if FMP is missing them
        if not fmp_has_domicile:
            prompt += "\n5. **domicile** - Country code (2-letter ISO code)\n"
        if not fmp_has_exchange:
            prompt += "6. **exchange** - Exchange code (e.g., LSE, NASDAQ)\n"
        if not fmp_has_currency:
            prompt += "7. **currency** - Currency code (3-letter ISO code)\n"
        if not fmp_has_aum:
            prompt += "8. **aum** - AUM in USD (number only)\n"

        prompt += "\nReturn ONLY valid JSON with these keys:\n{"
        prompt += '\n  "index": null,\n  "asset_class": null,\n  "is_accumulating": null,\n  "amc": null'
        
        if not fmp_has_domicile:
            prompt += ',\n  "domicile": null'
        if not fmp_has_exchange:
            prompt += ',\n  "exchange": null'
        if not fmp_has_currency:
            prompt += ',\n  "currency": null'
        if not fmp_has_aum:
            prompt += ',\n  "aum": null'
            
        prompt += "\n}\n\nUse JSON null for unknown values. No explanation, just JSON."

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        return json.loads(text)
        
    except Exception:
        return {
            "index": None,
            "asset_class": None,
            "is_accumulating": None,
            "amc": None
        }


def process_etf(symbol, name):
    """Process a single ETF by combining FMP and Gemini data."""
    fmp_data = get_fmp_data(symbol)
    
    if not fmp_data:
        fmp_data = {
            "full_profile": {},
            "domicile": "Not Available",
            "exchange": "Not Available",
            "volume": 0,
            "aum": 0,
            "currency": "Not Available",
            "lastDividend": 0,
            "price": 0
        }
    
    time.sleep(1)  # Rate limiting
    
    gemini_data = get_gemini_analysis(symbol, fmp_data.get("full_profile", {}), name)
    
    # Merge data: FMP takes priority, Gemini fills gaps
    domicile = fmp_data.get("domicile") if fmp_data.get("domicile") != "Not Available" else gemini_data.get("domicile")
    exchange = fmp_data.get("exchange") if fmp_data.get("exchange") != "Not Available" else gemini_data.get("exchange")
    currency = fmp_data.get("currency") if fmp_data.get("currency") != "Not Available" else gemini_data.get("currency")
    aum = fmp_data.get("aum") if fmp_data.get("aum", 0) > 0 else gemini_data.get("aum", 0)
    
    # Calculate dividend yield
    dividend_yield = None
    last_dividend = fmp_data.get("lastDividend", 0)
    price = fmp_data.get("price", 0)
    
    is_accumulating_by_name = (
        "(Acc)" in name or "(acc)" in name or 
        " Acc" in name or " acc" in name or
        name.endswith("Acc") or name.endswith("acc")
    )
    
    if is_accumulating_by_name:
        dividend_yield = 0
        gemini_data["is_accumulating"] = True
    elif last_dividend and last_dividend > 0 and price and price > 0:
        dividend_yield = round((last_dividend / price) * 100, 2)
        gemini_data["is_accumulating"] = False
    elif gemini_data.get("is_accumulating") == True:
        dividend_yield = 0
    
    return {
        "symbol": symbol,
        "name": name,
        "domicile": domicile,
        "exchange": exchange,
        "index": gemini_data.get("index"),
        "volume": fmp_data.get("volume", 0),
        "aum": aum or 0,
        "currency": currency,
        "asset_class": gemini_data.get("asset_class"),
        "amc": gemini_data.get("amc"),
        "is_accumulating": gemini_data.get("is_accumulating"),
        "expense_ratio": None,
        "dividend_yield": dividend_yield
    }


def load_etfs_from_file(input_file):
    """Load ETFs from JSON file."""
    try:
        with open(input_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_results(all_etf_data):
    """Save results to JSON file."""
    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(all_etf_data, f, indent=2)
        return OUTPUT_FILE
    except IOError:
        return None


def main():
    """Main function to process ETFs."""
    print("=" * 80)
    print("ETF Data Fetcher")
    print("=" * 80)
    
    etfs_raw = load_etfs_from_file(INPUT_FILE)
    if not etfs_raw:
        print("Error: No ETFs to process")
        return
    
    etfs = [{"symbol": etf.get("ticker", ""), "name": etf.get("name", "")} for etf in etfs_raw]
    etfs = [etf for etf in etfs if etf["symbol"]]
    
    total_etfs = len(etfs)
    total_batches = (total_etfs + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Processing {total_etfs} ETFs in {total_batches} batch(es) of {BATCH_SIZE}...\n")
    
    all_etf_data = []
    
    # Process in batches
    for batch_num in range(total_batches):
        batch_start = batch_num * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, total_etfs)
        batch_etfs = etfs[batch_start:batch_end]
        
        print(f"Batch {batch_num + 1}/{total_batches} (ETFs {batch_start + 1}-{batch_end}):")
        
        for idx, etf in enumerate(batch_etfs, start=batch_start + 1):
            try:
                print(f"[{idx}/{total_etfs}] {etf['symbol']}", end=" ")
                etf_data = process_etf(etf["symbol"], etf["name"])
                all_etf_data.append(etf_data)
                print("✓")
                time.sleep(1)
            except Exception as e:
                print(f"✗ {e}")
                continue
        
        # Save after each batch
        if all_etf_data:
            save_results(all_etf_data)
            print(f"Batch {batch_num + 1} saved.\n")
    
    print(f"{'=' * 80}")
    print(f"Completed: {len(all_etf_data)}/{total_etfs} ETFs")
    
    if all_etf_data:
        # Data quality statistics
        total_fields = len(all_etf_data) * 13
        unavailable_count = sum(1 for etf in all_etf_data for v in etf.values() if v == "Not Available")
        null_count = sum(1 for etf in all_etf_data for v in etf.values() if v is None)
        data_quality = ((total_fields - unavailable_count - null_count) / total_fields) * 100
        
        print(f"Data Quality: {data_quality:.1f}%")
        print(f"Saved to: {OUTPUT_FILE}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()