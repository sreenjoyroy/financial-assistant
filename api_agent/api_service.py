from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import requests
import yfinance as yf
import logging
import os
from dotenv import load_dotenv

# -----------------------------
# Environment Setup
# -----------------------------
load_dotenv()
LOG_FILE = os.getenv("LOG_FILE", "../logs/api_service_logs.json")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

# -----------------------------
# FastAPI Init
# -----------------------------
app = FastAPI(title="API Service - Dynamic Finance Lookup")

# -----------------------------
# Request Models
# -----------------------------
class CompanyRequest(BaseModel):
    companies: List[str]

# -----------------------------
# Helper Functions
# -----------------------------
def search_company_ticker(company_name: str) -> str:
    """
    Search Yahoo Finance and return the best-matching ticker symbol for a company name.
    """
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            "q": company_name,
            "lang": "en-US",
            "region": "US"
        }
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("quotes"):
            top_result = data["quotes"][0]
            symbol = top_result.get("symbol")
            longname = top_result.get("longname", "")
            exch = top_result.get("exchange", "")
            print(f"✅ Found: {longname} → {symbol} ({exch})")
            return symbol

        print("❌ No matching ticker found.")
        return None

    except Exception as e:
        print(f"⚠️ Error during search: {e}")
        return None

def fetch_yfinance_data(ticker: str) -> List[Dict[str, Any]]:
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="7d")

        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No historical data for ticker {ticker}")

        return [{
            "date": date.strftime("%Y-%m-%d"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
        } for date, row in hist.tail(5).iterrows()]

    except Exception as e:
        logging.error(f"Failed to fetch data for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_company_metadata(ticker: str) -> Dict[str, str]:
    try:
        info = yf.Ticker(ticker).info
        return {
            "region": info.get("region", "Unknown"),
            "sector": info.get("sector", "Unknown"),
        }
    except Exception:
        return {"region": "Unknown", "sector": "Unknown"}

# -----------------------------
# Endpoint
# -----------------------------
@app.post("/get-company-financials")
def get_company_financials(request: CompanyRequest):
    results = []
    for name in request.companies:
        try:
            ticker = search_company_ticker(name)
            history = fetch_yfinance_data(ticker)
            metadata = get_company_metadata(ticker)
            results.append({
                "company_name": name,
                "ticker": ticker,
                "region": metadata["region"],
                "sector": metadata["sector"],
                "history": history
            })
        except HTTPException as he:
            logging.error(f"Error for {name}: {he.detail}")
            results.append({
                "company_name": name,
                "error": he.detail
            })
    return {"status": "success", "company_data": results}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
