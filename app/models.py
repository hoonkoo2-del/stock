"""데이터 모델 — 사용자/종목/거래/현금."""
from sqlalchemy import (Column, Integer, String, Float, DateTime, ForeignKey, Text)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    stocks = relationship("Stock", back_populates="user", cascade="all, delete-orphan")
    cash = relationship("Cash", back_populates="user", cascade="all, delete-orphan")


class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker = Column(String, nullable=False)
    name = Column(String, nullable=False)
    market = Column(String, nullable=False)      # KR | US
    currency = Column(String, nullable=False)    # KRW | USD
    holding_period = Column(String, default="")
    memo = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="stocks")
    transactions = relationship("Transaction", back_populates="stock",
                                cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    dt = Column(DateTime, nullable=False)        # 거래 일시 (날짜+시간)
    side = Column(String, nullable=False)        # buy | sell
    price = Column(Float, nullable=False)        # 거래 통화 기준 단가
    qty = Column(Float, nullable=False)
    fx = Column(Float, default=1.0)              # 거래일 환율 (KRW/통화)
    tag = Column(String, default="")             # 사유 태그
    memo = Column(Text, default="")

    stock = relationship("Stock", back_populates="transactions")


class Cash(Base):
    __tablename__ = "cash"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    currency = Column(String, nullable=False)    # KRW | USD
    balance = Column(Float, default=0.0)
    memo = Column(String, default="")

    user = relationship("User", back_populates="cash")
