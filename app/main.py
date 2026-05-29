"""FastAPI 앱 — 주식 매매 히스토리 관리·분석 서비스."""
from __future__ import annotations
import os, time
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models, auth, engine as calc, insights, ta, market_data

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Stock Journal")
app.add_middleware(SessionMiddleware,
                   secret_key=os.environ.get("SECRET_KEY", "change-me-in-prod"))

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


# ----------------------------------------------------------------- 시세 캐시 (TTL)
_price_cache: dict[str, tuple[float, float | None]] = {}
_TTL = 60 * 30  # 30분


def price_of(ticker: str, market: str) -> float | None:
    key = f"{market}:{ticker}"
    now = time.time()
    if key in _price_cache and now - _price_cache[key][0] < _TTL:
        return _price_cache[key][1]
    p = market_data.get_current_price(ticker, market)
    _price_cache[key] = (now, p)
    return p


def build_position(stock: models.Stock) -> calc.Position:
    trades = [calc.Trade(t.dt, t.side, t.price, t.qty, t.fx or 1.0, t.tag)
              for t in stock.transactions]
    return calc.compute_position(trades)


# ----------------------------------------------------------------- 인증
class Credentials(BaseModel):
    username: str
    password: str


@app.post("/api/register")
def register(c: Credentials, request: Request, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(username=c.username).first():
        raise HTTPException(400, "이미 존재하는 사용자입니다")
    u = models.User(username=c.username, password_hash=auth.hash_password(c.password))
    db.add(u); db.commit(); db.refresh(u)
    request.session["uid"] = u.id
    return {"username": u.username}


@app.post("/api/login")
def login(c: Credentials, request: Request, db: Session = Depends(get_db)):
    u = db.query(models.User).filter_by(username=c.username).first()
    if not u or not auth.verify_password(c.password, u.password_hash):
        raise HTTPException(401, "아이디 또는 비밀번호가 틀립니다")
    request.session["uid"] = u.id
    return {"username": u.username}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(user: models.User = Depends(auth.current_user)):
    return {"username": user.username}


# ----------------------------------------------------------------- 종목 검색
@app.get("/api/search")
def search(q: str, user: models.User = Depends(auth.current_user)):
    return market_data.search_symbols(q)


# ----------------------------------------------------------------- 종목 CRUD
class StockIn(BaseModel):
    ticker: str
    name: str
    market: str
    currency: str
    holding_period: str = ""
    memo: str = ""


def serialize_stock(s: models.Stock) -> dict:
    pos = build_position(s)
    cur = price_of(s.ticker, s.market)
    fx_latest = market_data.get_fx_latest() if s.currency == "USD" else 1.0
    fx_latest = fx_latest or 1.0
    value_krw = None
    unreal_krw = None
    if cur is not None and pos.qty > 0:
        value_krw = round(pos.qty * cur * fx_latest)
        unreal_krw = round((cur - pos.avg_cost) * pos.qty * fx_latest)
    return {
        "id": s.id, "ticker": s.ticker, "name": s.name,
        "market": s.market, "currency": s.currency,
        "holding_period": s.holding_period, "memo": s.memo,
        "qty": round(pos.qty, 4), "avg_cost": round(pos.avg_cost, 4),
        "current_price": round(cur, 4) if cur is not None else None,
        "realized_krw": round(pos.realized_krw),
        "value_krw": value_krw, "unrealized_krw": unreal_krw,
        "tx_count": len(s.transactions),
    }


@app.get("/api/stocks")
def list_stocks(user: models.User = Depends(auth.current_user)):
    return [serialize_stock(s) for s in user.stocks]


@app.post("/api/stocks")
def add_stock(s: StockIn, user: models.User = Depends(auth.current_user),
              db: Session = Depends(get_db)):
    stock = models.Stock(user_id=user.id, **s.dict())
    db.add(stock); db.commit(); db.refresh(stock)
    return serialize_stock(stock)


@app.delete("/api/stocks/{stock_id}")
def delete_stock(stock_id: int, user: models.User = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    s = db.query(models.Stock).filter_by(id=stock_id, user_id=user.id).first()
    if not s:
        raise HTTPException(404, "종목을 찾을 수 없습니다")
    db.delete(s); db.commit()
    return {"ok": True}


# ----------------------------------------------------------------- 거래 CRUD
class TxIn(BaseModel):
    dt: datetime
    side: str
    price: float
    qty: float
    tag: str = ""
    memo: str = ""


def _owned_stock(stock_id, user, db):
    s = db.query(models.Stock).filter_by(id=stock_id, user_id=user.id).first()
    if not s:
        raise HTTPException(404, "종목을 찾을 수 없습니다")
    return s


@app.get("/api/stocks/{stock_id}/transactions")
def list_tx(stock_id: int, user: models.User = Depends(auth.current_user),
            db: Session = Depends(get_db)):
    s = _owned_stock(stock_id, user, db)
    txs = sorted(s.transactions, key=lambda t: t.dt, reverse=True)
    return [{"id": t.id, "dt": t.dt.isoformat(), "side": t.side, "price": t.price,
             "qty": t.qty, "amount": round(t.price * t.qty, 2), "fx": t.fx,
             "tag": t.tag, "memo": t.memo} for t in txs]


@app.post("/api/stocks/{stock_id}/transactions")
def add_tx(stock_id: int, tx: TxIn, user: models.User = Depends(auth.current_user),
           db: Session = Depends(get_db)):
    s = _owned_stock(stock_id, user, db)
    # 환율 자동: 미국주식은 거래일 환율, 한국주식은 1.0
    fx = 1.0
    if s.currency == "USD":
        fx = (market_data.get_fx_on(tx.dt.strftime("%Y-%m-%d"))
              or market_data.get_fx_latest() or 0.0)
    t = models.Transaction(stock_id=s.id, dt=tx.dt, side=tx.side, price=tx.price,
                           qty=tx.qty, fx=fx, tag=tx.tag, memo=tx.memo)
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id, "fx": t.fx}


@app.delete("/api/transactions/{tx_id}")
def delete_tx(tx_id: int, user: models.User = Depends(auth.current_user),
              db: Session = Depends(get_db)):
    t = db.query(models.Transaction).get(tx_id)
    if not t or t.stock.user_id != user.id:
        raise HTTPException(404, "거래를 찾을 수 없습니다")
    db.delete(t); db.commit()
    return {"ok": True}


# ----------------------------------------------------------------- 현금
class CashIn(BaseModel):
    currency: str
    balance: float
    memo: str = ""


@app.get("/api/cash")
def list_cash(user: models.User = Depends(auth.current_user)):
    return [{"id": c.id, "currency": c.currency, "balance": c.balance, "memo": c.memo}
            for c in user.cash]


@app.post("/api/cash")
def upsert_cash(c: CashIn, user: models.User = Depends(auth.current_user),
                db: Session = Depends(get_db)):
    existing = next((x for x in user.cash if x.currency == c.currency), None)
    if existing:
        existing.balance = c.balance; existing.memo = c.memo
    else:
        db.add(models.Cash(user_id=user.id, currency=c.currency,
                           balance=c.balance, memo=c.memo))
    db.commit()
    return {"ok": True}


# ----------------------------------------------------------------- 대시보드
@app.get("/api/dashboard")
def dashboard(user: models.User = Depends(auth.current_user)):
    fx_latest = market_data.get_fx_latest() or 1300.0
    positions, pos_with_price = [], []
    stock_value, by_market = 0.0, {"KR": 0.0, "US": 0.0}

    for s in user.stocks:
        pos = build_position(s)
        positions.append(pos)
        cur = price_of(s.ticker, s.market)
        pos_with_price.append((pos, cur if cur is not None else pos.avg_cost))
        if cur is not None and pos.qty > 0:
            f = fx_latest if s.currency == "USD" else 1.0
            v = pos.qty * cur * f
            stock_value += v
            by_market[s.market] += v

    # 현금 (원 환산)
    cash_krw = 0.0
    by_currency = {"KRW": 0.0, "USD": 0.0}
    for c in user.cash:
        v = c.balance * (fx_latest if c.currency == "USD" else 1.0)
        cash_krw += v
        by_currency[c.currency] += v

    total = stock_value + cash_krw
    composition = {
        "total_krw": round(total),
        "stock_krw": round(stock_value),
        "cash_krw": round(cash_krw),
        "stock_pct": round(stock_value / total * 100, 1) if total else 0,
        "cash_pct": round(cash_krw / total * 100, 1) if total else 0,
        "by_market": {k: round(v) for k, v in by_market.items()},
        "by_currency": {k: round(v) for k, v in by_currency.items()},
    }
    return {
        "composition": composition,
        "performance": insights.performance_stats(positions),
        "habits": insights.trading_habits(pos_with_price),
        "alerts": insights.trend_alerts(pos_with_price),
    }


# ----------------------------------------------------------------- 시뮬레이션
@app.get("/api/stocks/{stock_id}/simulation")
def simulation(stock_id: int, user: models.User = Depends(auth.current_user),
               db: Session = Depends(get_db)):
    s = _owned_stock(stock_id, user, db)
    pos = build_position(s)
    cur = price_of(s.ticker, s.market)
    if cur is None:
        raise HTTPException(503, "현재 시세를 가져올 수 없습니다 (네트워크 확인)")
    fx_latest = (market_data.get_fx_latest() or 1.0) if s.currency == "USD" else 1.0
    sims = calc.simulate_not_sold(pos, cur, fx_latest)
    return {"current_price": round(cur, 4), "simulations": [
        {**x, "dt": x["dt"].isoformat()} for x in sims]}


# ----------------------------------------------------------------- TA
@app.get("/api/stocks/{stock_id}/ta")
def technical(stock_id: int, user: models.User = Depends(auth.current_user),
              db: Session = Depends(get_db)):
    s = _owned_stock(stock_id, user, db)
    hist = market_data.get_history(s.ticker, s.market)
    if hist is None:
        raise HTTPException(503, "시세 이력을 가져올 수 없습니다 (네트워크 확인)")
    return ta.analyze(hist)


# ----------------------------------------------------------------- 정적 서빙
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
