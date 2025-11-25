"""
ETF Data Fetcher - SIMPLIFIED VERSION
EXACT same logic as original, just cleaner and optimized.
"""

import requests
import google.generativeai as genai
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
FMP_API_KEY = os.getenv("FMP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FMP_BASE_URL = os.getenv("FMP_BASE_URL", "https://financialmodelingprep.com/stable/profile")

# File Configuration
INPUT_FILE = os.getenv("INPUT_FILE", "12-nov-2025-ucits-list.json")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "etf_data.json")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')


def get_fmp_data(symbol):
    """Fetch ETF profile data from FMP API - EXACT original logic."""
    try:
        print(f"  📡 Fetching FMP data for {symbol}...")
        url = f"{FMP_BASE_URL}?symbol={symbol}&apikey={FMP_API_KEY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"  ⚠️  No data from FMP for {symbol}")
            return None
            
        data = response.json()
        if not data or len(data) == 0:
            print(f"  ⚠️  No data from FMP for {symbol}")
            return None
        
        # Extract first result - keep FULL profile for Gemini (EXACT original)
        full_profile = data[0] if isinstance(data, list) else data
        
        # Extract specific fields - EXACT original logic
        extracted_data = {
            "full_profile": full_profile,  # Keep full profile for Gemini
            "domicile": full_profile.get("country", "") or "Not Available",
            "exchange": full_profile.get("exchange", "") or "Not Available",
            "volume": full_profile.get("volume", 0) or 0,
            "aum": full_profile.get("marketCap", 0) or 0,
            "currency": full_profile.get("currency", "") or "Not Available",
            "lastDividend": full_profile.get("lastDividend", 0) or 0,
            "price": full_profile.get("price", 0) or 0
        }
        
        print(f"  ✓ FMP data retrieved")
        return extracted_data
        
    except Exception as e:
        print(f"  ✗ FMP error: {e}")
        return None


def get_gemini_analysis(symbol, fmp_full_profile, etf_name):
    """
    Use Gemini AI to analyze ETF - EXACT original logic.
    Single unified call instead of multiple fallback calls.
    """
    try:
        print(f"  🤖 Asking Gemini AI to analyze {symbol}...")
        
        # Extract key fields for better AMC identification - EXACT original
        description = fmp_full_profile.get("description", "")
        company_name = fmp_full_profile.get("companyName", "")
        
        # Check what's missing from FMP - for fallback fields
        fmp_has_domicile = fmp_full_profile.get("country")
        fmp_has_exchange = fmp_full_profile.get("exchange")
        fmp_has_currency = fmp_full_profile.get("currency")
        fmp_has_aum = fmp_full_profile.get("marketCap", 0) > 0
        
        prompt = f"""You are a financial data analyst specializing in ETFs and Asset Management Companies.
DO NOT assume or fabricate information.
If uncertain about any field, return null (JSON null, not string).

ETF Information:
- Symbol: {symbol}
- Full Name: {etf_name}
- Company Name (from FMP): {company_name}
- Description: {description[:500] if description else "Not available"}

COMPLETE FMP Profile Data:
{json.dumps(fmp_full_profile, indent=2)}

Extract these fields:

1. **index** - CRITICAL PRIORITY FIELD - The actual index this ETF tracks:
   - Look CAREFULLY at the ETF name "{etf_name}" for index keywords
   - Examples: "S&P 500", "MSCI World", "NASDAQ 100", "FTSE 100", "Russell 2000"
   - Variations: "SP 500" = "S&P 500", "MSCI EM" = "MSCI Emerging Markets"
   - Sector indices: "MSCI China", "MSCI Europe", etc.
   - Bond indices: "Bloomberg Barclays", "JP Morgan EM Bond", etc.
   - Try VERY HARD to identify this - it's in the name 90% of the time
   - Return proper full name: "S&P 500 Index", "MSCI World Index", etc.
   - Return null ONLY if you absolutely cannot determine

2. **asset_class** - ONE of: Equity, Bond, Commodity, Real Estate, Money Market:
   - Look for keywords: "Bond", "Equity", "Stock", "Treasury", "Corporate Bond"
   - "REIT" or "Real Estate" → Real Estate
   - "Gold", "Oil", "Commodity" → Commodity
   - Return null if unknown

3. **is_accumulating** - Boolean value:
   - true if dividends are reinvested (Accumulating, often has "Acc" in name)
   - false if dividends are paid out (Distributing, often has "Dist" or no suffix)
   - null if you cannot determine

4. **amc** (Asset Management Company):
   - The first word(s) in the ETF name "{etf_name}" often indicate the AMC or brand
   - Return the PARENT COMPANY name, not just the brand
   - Examples:
     * "iShares" products → AMC is "BlackRock" (iShares is BlackRock's brand)
     * "Vanguard" products → AMC is "Vanguard"
     * "Amundi" products → AMC is "Amundi"
     * "Invesco" products → AMC is "Invesco"
     * "SPDR" products → AMC is "State Street Global Advisors"
     * "Xtrackers" products → AMC is "DWS Group"
   - Look at the description and company fields for hints
   - Return null only if you truly cannot determine
"""

        # Add fallback fields only if FMP is missing them
        if not fmp_has_domicile:
            prompt += """
5. **domicile** - Country code (ONLY if FMP missing):
   - "PLC" often means Ireland (IE)
   - "SICAV" often means Luxembourg (LU)
   - Return 2-letter country code
"""
        
        if not fmp_has_exchange:
            prompt += """
6. **exchange** - Exchange code (ONLY if FMP missing):
   - .L → LSE, .AS → AMS, .SW → SIX, no suffix → NASDAQ/NYSE
   - Return exchange code only
"""
        
        if not fmp_has_currency:
            prompt += """
7. **currency** - Currency code (ONLY if FMP missing):
   - USD/EUR/GBP from name or infer from exchange
   - Return 3-letter code
"""
        
        if not fmp_has_aum:
            prompt += """
8. **aum** - AUM in USD (ONLY if FMP missing):
   - Only if you know this specific ETF
   - Return number only, or null
"""

        prompt += """
Return ONLY valid JSON with these exact keys:
{
  "index": null,
  "asset_class": null,
  "is_accumulating": null,
  "amc": null"""
        
        if not fmp_has_domicile:
            prompt += ',\n  "domicile": null'
        if not fmp_has_exchange:
            prompt += ',\n  "exchange": null'
        if not fmp_has_currency:
            prompt += ',\n  "currency": null'
        if not fmp_has_aum:
            prompt += ',\n  "aum": null'
            
        prompt += """
}

IMPORTANT: 
- INDEX is the MOST CRITICAL field - try your absolute best to find it
- Use JSON null (not string "null" or "Not Available") for unknown values
- No explanation, just the JSON"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Extract JSON from response - EXACT original logic
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        gemini_data = json.loads(text)
        print(f"  ✓ Gemini analysis completed")
        print(f"     └─ index: {gemini_data.get('index')}")
        print(f"     └─ amc: {gemini_data.get('amc')}")
        
        return gemini_data
        
    except Exception as e:
        print(f"  ✗ Gemini error: {e}")
        return {
            "index": None,
            "asset_class": None,
            "is_accumulating": None,
            "amc": None
        }


def process_etf(symbol, name):
    """
    Process a single ETF - EXACT original logic.
    """
    print(f"\n🔄 Processing {symbol} - {name}")
    print("=" * 60)
    
    # Fetch FMP data - EXACT original
    fmp_data = get_fmp_data(symbol)
    
    if not fmp_data:
        print(f"  ⚠️  FMP API failed completely - Using default values")
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
    
    # Add delay to avoid rate limits - EXACT original
    time.sleep(1)
    
    # Get Gemini analysis - EXACT original (now unified in one call)
    gemini_data = get_gemini_analysis(symbol, fmp_data.get("full_profile", {}), name)
    
    # Merge FMP and Gemini data - FMP takes priority
    domicile = fmp_data.get("domicile") if fmp_data.get("domicile") != "Not Available" else gemini_data.get("domicile")
    exchange = fmp_data.get("exchange") if fmp_data.get("exchange") != "Not Available" else gemini_data.get("exchange")
    currency = fmp_data.get("currency") if fmp_data.get("currency") != "Not Available" else gemini_data.get("currency")
    aum = fmp_data.get("aum") if fmp_data.get("aum", 0) > 0 else gemini_data.get("aum", 0)
    
    # Calculate dividend yield - EXACT original logic with exact same priority
    dividend_yield = None
    last_dividend = fmp_data.get("lastDividend", 0)
    price = fmp_data.get("price", 0)
    
    # Check if it's an accumulating ETF by name - EXACT original
    is_accumulating_by_name = (
        "(Acc)" in name or "(acc)" in name or 
        " Acc" in name or " acc" in name or
        name.endswith("Acc") or name.endswith("acc")
    )
    
    # EXACT original priority logic:
    # 1. If name contains "Acc" → accumulating (dividend_yield = 0)
    if is_accumulating_by_name:
        dividend_yield = 0
        gemini_data["is_accumulating"] = True
    # 2. If FMP has lastDividend > 0 → distributing (calculate yield, set is_accumulating = false)
    elif last_dividend and last_dividend > 0 and price and price > 0:
        dividend_yield = round((last_dividend / price) * 100, 2)
        gemini_data["is_accumulating"] = False
    # 3. If Gemini says is_accumulating = true → dividend_yield = 0
    elif gemini_data.get("is_accumulating") == True:
        dividend_yield = 0
    # 4. Otherwise → null
    else:
        dividend_yield = None
    
    # Combine all data - EXACT original structure
    combined_data = {
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
    
    print(f"✓ {symbol} processing complete")
    return combined_data


def load_etfs_from_file(input_file):
    """Load ETFs from JSON file - EXACT original."""
    try:
        with open(input_file, 'r') as f:
            etfs = json.load(f)
        print(f"✓ Loaded {len(etfs)} ETFs from {input_file}")
        return etfs
    except FileNotFoundError:
        print(f"✗ Error: Input file '{input_file}' not found!")
        return []
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON in '{input_file}': {e}")
        return []


def save_results(all_etf_data):
    """Save results to JSON file - EXACT original."""
    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(all_etf_data, f, indent=2)
        print(f"\n💾 Saved {len(all_etf_data)} ETF(s) to {OUTPUT_FILE}")
        return OUTPUT_FILE
    except IOError as e:
        print(f"\n✗ Error saving: {e}")
        return None


def main():
    """Main function - EXACT original logic, simplified structure."""
    print("\n" + "=" * 80)
    print("🚀 ETF Data Fetcher - OPTIMIZED (Same Logic, 1 Gemini Call)")
    print("=" * 80)
    
    # Load ETFs - EXACT original
    etfs_raw = load_etfs_from_file(INPUT_FILE)
    if not etfs_raw:
        print("\n✗ No ETFs to process. Exiting.")
        return
    
    # Convert to required format - EXACT original
    etfs = [{"symbol": etf.get("ticker", ""), "name": etf.get("name", "")} for etf in etfs_raw]
    etfs = [etf for etf in etfs if etf["symbol"]]
    etfs = etfs[:30]
    
    total_etfs = len(etfs)
    print(f"\n📊 Total ETFs to process: {total_etfs}")
    print("=" * 80)
    
    all_etf_data = []
    
    # Process all ETFs - EXACT original logic
    for idx, etf in enumerate(etfs, start=1):
        try:
            print(f"\n[{idx}/{total_etfs}] ", end="")
            etf_data = process_etf(etf["symbol"], etf["name"])
            all_etf_data.append(etf_data)
            
            # Delay between ETFs - EXACT original
            time.sleep(1)
            
        except Exception as e:
            print(f"\n✗ Error processing {etf['symbol']}: {e}")
            print(f"   Continuing with next ETF...")
            continue
    
    # Save results - EXACT original
    print("\n" + "=" * 80)
    print(f"✅ Processed {len(all_etf_data)}/{total_etfs} ETFs")
    
    if all_etf_data:
        save_results(all_etf_data)
        
        # Calculate data quality statistics - EXACT original
        total_fields = len(all_etf_data) * 13
        unavailable_count = 0
        null_count = 0
        for etf in all_etf_data:
            for key, value in etf.items():
                if value == "Not Available":
                    unavailable_count += 1
                elif value is None:
                    null_count += 1
        
        data_quality = ((total_fields - unavailable_count - null_count) / total_fields) * 100
        print(f"\n📈 Data Quality: {data_quality:.1f}%")
        print(f"   Populated: {total_fields - unavailable_count - null_count}/{total_fields} fields")
    
    print("=" * 80)
    print("✓ Complete\n")


if __name__ == "__main__":
    main()