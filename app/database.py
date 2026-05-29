"""DB 연결/세션.

- 운영(Vercel): 환경변수 DATABASE_URL(Supabase Postgres) 사용. 서버리스에 맞춰 NullPool.
- 로컬 개발: DATABASE_URL이 없으면 SQLite 파일 사용.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # 일부 제공자는 'postgres://' 로 주는데 SQLAlchemy는 'postgresql://' 를 기대
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    # 서버리스: 연결을 풀에 두지 않고 매 요청마다 정리 (Supabase 트랜잭션 풀러 권장)
    engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "stock_journal.db")
    engine = create_engine(f"sqlite:///{DB_PATH}",
                           connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
