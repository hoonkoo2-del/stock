"""시세·종목검색·환율 어댑터.

런타임에 외부(야후/KRX) 네트워크가 필요하다. 라이브러리·네트워크가 없으면
함수가 빈 결과나 None을 반환하도록 방어적으로 작성했다.
실제 사용 환경(네트워크 열림)에서 정상 동작한다.

우선순위: FinanceDataReader(한국+미국 상장목록/시세/환율) → yfinance(미국 보조)
"""
from __future__ import annotations
import functools
from datetime import datetime, timedelta

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None

try:
    import yfinance as yf
except Exception:
    yf = None


# ---------------------------------------------------------------- 종목 마스터/검색
@functools.lru_cache(maxsize=1)
def _load_master():
    """KRX + 미국 상장 종목 마스터를 한 번 로드해 캐시. (앱 시작 후 1회)"""
    rows = []
    if fdr is None:
        return rows
    try:
        krx = fdr.StockListing("KRX")  # 한국
        for _, r in krx.iterrows():
            code = str(r.get("Code") or r.get("Symbol") or "").strip()
            name = str(r.get("Name") or "").strip()
            if code and name:
                rows.append({"ticker": code, "name": name,
                             "market": "KR", "currency": "KRW"})
    except Exception:
        pass
    for ex in ("NASDAQ", "NYSE", "AMEX"):
        try:
            us = fdr.StockListing(ex)
            for _, r in us.iterrows():
                sym = str(r.get("Symbol") or "").strip()
                name = str(r.get("Name") or "").strip()
                if sym and name:
                    rows.append({"ticker": sym, "name": name,
                                 "market": "US", "currency": "USD"})
        except Exception:
            pass
    return rows


def search_symbols(query: str, limit: int = 20) -> list[dict]:
    """종목명/티커로 실제 상장 종목 검색."""
    q = (query or "").strip().lower()
    if not q:
        return []
    master = _load_master()
    hits = []
    for row in master:
        if q in row["ticker"].lower() or q in row["name"].lower():
            hits.append(row)
            if len(hits) >= limit:
                break
    return hits


# ---------------------------------------------------------------- 시세
def get_current_price(ticker: str, market: str) -> float | None:
    """최신 종가."""
    try:
        if fdr is not None:
            df = fdr.DataReader(ticker)
            if df is not None and len(df):
                return float(df["Close"].iloc[-1])
    except Exception:
        pass
    if market == "US" and yf is not None:
        try:
            h = yf.Ticker(ticker).history(period="5d")
            if len(h):
                return float(h["Close"].iloc[-1])
        except Exception:
            pass
    return None


def get_history(ticker: str, market: str, days: int = 400):
    """일봉 종가 시계열(pandas Series). TA용."""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        if fdr is not None:
            df = fdr.DataReader(ticker, start)
            if df is not None and len(df):
                return df["Close"].dropna()
    except Exception:
        pass
    if market == "US" and yf is not None:
        try:
            h = yf.Ticker(ticker).history(period=f"{days}d")
            if len(h):
                return h["Close"].dropna()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- 환율
@functools.lru_cache(maxsize=512)
def get_fx_on(date_str: str) -> float | None:
    """거래일(YYYY-MM-DD) USD/KRW 환율. 주말/공휴일은 직전 영업일."""
    try:
        if fdr is None:
            return None
        end = datetime.strptime(date_str, "%Y-%m-%d")
        start = (end - timedelta(days=10)).strftime("%Y-%m-%d")
        df = fdr.DataReader("USD/KRW", start, date_str)
        if df is not None and len(df):
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return None


def get_fx_latest() -> float | None:
    return get_fx_on(datetime.now().strftime("%Y-%m-%d"))
