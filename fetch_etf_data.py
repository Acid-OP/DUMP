"""
ETF Data Fetcher
Combines data from FMP API and Gemini AI to create comprehensive ETF profiles.
"""

import requests
import google.generativeai as genai
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
FMP_API_KEY = os.getenv("FMP_API_KEY", "NLbC4l1XMZkXVw2xUWCsGz3KW3Z0E2ZH")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDEBGiXpDaJbAvJftx2AzaOapQnu8W8eGE")
FMP_BASE_URL = "https://financialmodelingprep.com/stable/profile"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')


def get_fmp_data(symbol):
    """
    Fetch ETF profile data from FMP API.
    
    Args:
        symbol (str): ETF ticker symbol
        
    Returns:
        dict: Extracted profile data or None if error
    """
    try:
        print(f"  📡 Fetching FMP data for {symbol}...")
        url = f"{FMP_BASE_URL}?symbol={symbol}&apikey={FMP_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or len(data) == 0:
            print(f"  ⚠️  No data returned from FMP for {symbol}")
            return None
        
        # Extract first result
        profile = data[0] if isinstance(data, list) else data
        
        # Map FMP fields to our structure with unavailable tracking
        extracted_data = {
            "domicile": profile.get("country", "") or "Not Available",
            "exchange": profile.get("exchange", "") or "Not Available",
            "volume": profile.get("volume", 0) or 0,
            "aum": profile.get("marketCap", 0) or 0,
            "currency": profile.get("currency", "") or "Not Available",
            "amc": profile.get("companyName", "") or "Not Available"
        }
        
        print(f"  ✓ FMP data retrieved successfully")
        
        # Track unavailable fields
        unavailable_fields = []
        if extracted_data['domicile'] == "Not Available":
            unavailable_fields.append("domicile")
        if extracted_data['exchange'] == "Not Available":
            unavailable_fields.append("exchange")
        if extracted_data['volume'] == 0:
            unavailable_fields.append("volume")
        if extracted_data['aum'] == 0:
            unavailable_fields.append("aum")
        if extracted_data['currency'] == "Not Available":
            unavailable_fields.append("currency")
        if extracted_data['amc'] == "Not Available":
            unavailable_fields.append("amc")
        
        if unavailable_fields:
            print(f"  ⚠️  FMP missing fields: {', '.join(unavailable_fields)}")
        
        print(f"     └─ FMP provided: domicile={extracted_data['domicile']}, exchange={extracted_data['exchange']}")
        print(f"     └─ FMP provided: volume={extracted_data['volume']:,}, aum=${extracted_data['aum']:,}")
        amc_display = extracted_data['amc'][:50] + "..." if len(extracted_data['amc']) > 50 else extracted_data['amc']
        print(f"     └─ FMP provided: currency={extracted_data['currency']}, amc={amc_display}")
        return extracted_data
        
    except requests.exceptions.RequestException as e:
        print(f"  ✗ FMP API error: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"  ✗ FMP data parsing error: {e}")
        return None


def get_gemini_analysis(symbol, fmp_data):
    """
    Use Gemini AI to analyze ETF and extract additional fields.
    
    Args:
        symbol (str): ETF ticker symbol
        fmp_data (dict): Data from FMP API
        
    Returns:
        dict: Gemini analysis results or None if error
    """
    try:
        print(f"  🤖 Asking Gemini AI to analyze {symbol}...")
        
        prompt = f"""You are a financial data analyst specializing in ETFs.
DO NOT assume or fabricate information.
If uncertain about any field, return 'Not Available'.

Analyze this ETF data from FMP:
{json.dumps(fmp_data, indent=2)}

ETF Symbol: {symbol}

Extract these 4 fields ONLY:
1. index - The actual index this ETF tracks (e.g., 'S&P 500', 'MSCI World Index')
2. ucit - UCITS classification: 'UCITS' or 'Non-UCITS'
3. asset_class - ONE of: Equity, Bond, Commodity, Real Estate, Money Market
4. accumulating_or_distributing - 'Accumulating' or 'Distributing'

Return ONLY valid JSON with these exact keys:
{{
  "index": "",
  "ucit": "",
  "asset_class": "",
  "accumulating_or_distributing": ""
}}

No explanation, just the JSON."""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Extract JSON from response (Gemini might wrap it in markdown)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        gemini_data = json.loads(text)
        print(f"  ✓ Gemini analysis completed")
        
        # Track unavailable fields from Gemini
        unavailable_fields = []
        if gemini_data.get('index', 'Not Available') == 'Not Available':
            unavailable_fields.append("index")
        if gemini_data.get('ucit', 'Not Available') == 'Not Available':
            unavailable_fields.append("ucit")
        if gemini_data.get('asset_class', 'Not Available') == 'Not Available':
            unavailable_fields.append("asset_class")
        if gemini_data.get('accumulating_or_distributing', 'Not Available') == 'Not Available':
            unavailable_fields.append("accumulating_or_distributing")
        
        if unavailable_fields:
            print(f"  ⚠️  Gemini unable to determine: {', '.join(unavailable_fields)}")
        
        print(f"     └─ Gemini provided: index={gemini_data.get('index', 'N/A')}")
        print(f"     └─ Gemini provided: ucit={gemini_data.get('ucit', 'N/A')}, asset_class={gemini_data.get('asset_class', 'N/A')}")
        print(f"     └─ Gemini provided: accumulating_or_distributing={gemini_data.get('accumulating_or_distributing', 'N/A')}")
        
        return gemini_data
        
    except Exception as e:
        print(f"  ✗ Gemini AI error: {e}")
        return {
            "index": "Not Available",
            "ucit": "Not Available",
            "asset_class": "Not Available",
            "accumulating_or_distributing": "Not Available"
        }


def process_etf(symbol, name):
    """
    Process a single ETF by combining FMP and Gemini data.
    
    Args:
        symbol (str): ETF ticker symbol
        name (str): ETF full name
        
    Returns:
        dict: Combined ETF data
    """
    print(f"\n🔄 Processing {symbol} - {name}")
    print("=" * 60)
    
    # Fetch FMP data
    fmp_data = get_fmp_data(symbol)
    
    if not fmp_data:
        print(f"  ⚠️  FMP API failed completely - Using default values for {symbol}")
        print(f"  ⚠️  All FMP fields marked as: Not Available")
        fmp_data = {
            "domicile": "Unable to fetch from FMP",
            "exchange": "Unable to fetch from FMP",
            "volume": 0,
            "aum": 0,
            "currency": "Unable to fetch from FMP",
            "amc": "Unable to fetch from FMP"
        }
    
    # Add delay to avoid rate limits
    time.sleep(1)
    
    # Get Gemini analysis
    gemini_data = get_gemini_analysis(symbol, fmp_data)
    
    # Combine all data
    combined_data = {
        "symbol": symbol,
        "name": name,
        "domicile": fmp_data.get("domicile", ""),
        "exchange": fmp_data.get("exchange", ""),
        "index": gemini_data.get("index", "Not Available"),
        "volume": fmp_data.get("volume", 0),
        "aum": fmp_data.get("aum", 0),
        "currency": fmp_data.get("currency", ""),
        "ucit": gemini_data.get("ucit", "Not Available"),
        "asset_class": gemini_data.get("asset_class", "Not Available"),
        "amc": fmp_data.get("amc", ""),
        "expense_ratio": None,
        "accumulating_or_distributing": gemini_data.get("accumulating_or_distributing", "Not Available"),
        "dividend_yield": None
    }
    
    # Log data source mapping
    print(f"\n  📊 Data Source Mapping for {symbol}:")
    print(f"     ┌─ FMP API provided:")
    print(f"     │  ├─ domicile: {combined_data['domicile']}")
    print(f"     │  ├─ exchange: {combined_data['exchange']}")
    print(f"     │  ├─ volume: {combined_data['volume']:,}")
    print(f"     │  ├─ aum: ${combined_data['aum']:,}")
    print(f"     │  ├─ currency: {combined_data['currency']}")
    print(f"     │  └─ amc: {combined_data['amc'][:40]}...")
    print(f"     │")
    print(f"     ├─ Gemini AI provided:")
    print(f"     │  ├─ index: {combined_data['index']}")
    print(f"     │  ├─ ucit: {combined_data['ucit']}")
    print(f"     │  ├─ asset_class: {combined_data['asset_class']}")
    print(f"     │  └─ accumulating_or_distributing: {combined_data['accumulating_or_distributing']}")
    print(f"     │")
    print(f"     └─ Manual (null values):")
    print(f"        ├─ expense_ratio: {combined_data['expense_ratio']}")
    print(f"        └─ dividend_yield: {combined_data['dividend_yield']}")
    
    print(f"\n✓ {symbol} processing complete")
    return combined_data


def main():
    """
    Main function to process all ETFs and save results.
    """
    print("\n" + "=" * 60)
    print("🚀 ETF Data Fetcher - Starting Process")
    print("=" * 60)
    print("\n📌 Data Source Configuration:")
    print("   ├─ FMP API: domicile, exchange, volume, aum, currency, amc")
    print("   ├─ Gemini AI: index, ucit, asset_class, accumulating_or_distributing")
    print("   └─ Manual: expense_ratio (null), dividend_yield (null)")
    print("\n" + "=" * 60)
    
    # ETFs to process
    etfs = [
        {"symbol": "CSPX.L", "name": "iShares Core SP 500 UCITS ETF"},
        {"symbol": "IWDA.L", "name": "iShares Core MSCI World UCITS ETF"},
        {"symbol": "IUAA.L", "name": "iShares US Aggregate Bond UCITS ETF"},
        {"symbol": "IBTA.L", "name": "iShares Treasury Bond 1-3yr UCITS ETF"},
        {"symbol": "LQDA.L", "name": "iShares Corp Bond UCITS ETF"},
        {"symbol": "CSNDX.SW", "name": "iShares NASDAQ 100 UCITS ETF"},
        {"symbol": "EIMI.L", "name": "iShares Core MSCI EM IMI UCITS ETF"},
        {"symbol": "ICHN.AS", "name": "iShares MSCI China UCITS ETF USD Acc"},
        {"symbol": "IGBSF", "name": "iShares MSCI Global Semiconductors UCITS ETF"},
        {"symbol": "IHYA.L", "name": "iShares High Yield Corp Bond UCITS ETF"},
        {"symbol": "EMCP.L", "name": "iShares JP Morgan EM Corp Bond UCITS ETF"},
        {"symbol": "MCHT.L", "name": "Invesco MSCI China Technology All Shares Stock Connect UCITS ETF"},
        {"symbol": "NASD.L", "name": "Amundi Nasdaq-100 II UCITS ETF Acc"}
    ]
    
    all_etf_data = []
    
    # Process each ETF
    for etf in etfs:
        try:
            etf_data = process_etf(etf["symbol"], etf["name"])
            all_etf_data.append(etf_data)
            
            # Delay between ETFs
            time.sleep(1)
            
        except Exception as e:
            print(f"\n✗ Error processing {etf['symbol']}: {e}")
            continue
    
    # Save to JSON file
    output_file = "etf_data.json"
    try:
        with open(output_file, "w") as f:
            json.dump(all_etf_data, f, indent=2)
        
        print("\n" + "=" * 60)
        print(f"✅ SUCCESS! Data saved to {output_file}")
        print("=" * 60)
        print(f"\n📊 Processed {len(all_etf_data)} ETF(s)")
        
        # Calculate data quality statistics
        total_fields = len(all_etf_data) * 14  # 14 fields per ETF
        unavailable_count = 0
        for etf in all_etf_data:
            for key, value in etf.items():
                if value == "Not Available" or value == "Unable to fetch from FMP":
                    unavailable_count += 1
        
        data_quality = ((total_fields - unavailable_count) / total_fields) * 100
        print(f"📈 Data Quality: {data_quality:.1f}% ({total_fields - unavailable_count}/{total_fields} fields populated)")
        print(f"⚠️  Unavailable/Missing: {unavailable_count} fields")
        
        # Print summary
        print("\n📋 Summary by Data Source:")
        print("\n" + "─" * 60)
        for etf in all_etf_data:
            print(f"\n🔹 {etf['symbol']} - {etf['name']}")
            print(f"\n   FROM FMP API:")
            print(f"   ├─ Domicile: {etf['domicile']}")
            print(f"   ├─ Exchange: {etf['exchange']}")
            print(f"   ├─ Volume: {etf['volume']:,}")
            print(f"   ├─ AUM: ${etf['aum']:,}")
            print(f"   ├─ Currency: {etf['currency']}")
            print(f"   └─ AMC: {etf['amc'][:50]}...")
            print(f"\n   FROM GEMINI AI:")
            print(f"   ├─ Index Tracked: {etf['index']}")
            print(f"   ├─ UCITS Status: {etf['ucit']}")
            print(f"   ├─ Asset Class: {etf['asset_class']}")
            print(f"   └─ Distribution Type: {etf['accumulating_or_distributing']}")
            print(f"\n   MANUAL (NULL):")
            print(f"   ├─ Expense Ratio: {etf['expense_ratio']}")
            print(f"   └─ Dividend Yield: {etf['dividend_yield']}")
            print("\n" + "─" * 60)
        
    except IOError as e:
        print(f"\n✗ Error saving to file: {e}")


if __name__ == "__main__":
    main()

