# 주식 매매 저널 (Stock Journal)

한국/미국 주식의 매매 히스토리를 기록하고, "안 팔았다면?" 시뮬레이션 ·
차트 기반 참고 신호 · 매매 습관 인사이트를 제공하는 모바일 우선 웹 서비스.
지인 몇 명과 공유하는 소규모 사용을 전제로 한다.

## 실행 방법

```bash
# 1) 가상환경 (선택)
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 실행
export SECRET_KEY="아무_긴_랜덤_문자열"        # 세션 암호화 키 (권장)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저(모바일 우선 디자인)에서 `http://localhost:8000` 접속 → 회원가입 후 사용.

> ⚠️ 시세·환율·종목검색은 외부 데이터(yfinance / pykrx / FinanceDataReader)에서
> 가져오므로 **인터넷 연결이 필요**합니다. 현재 종가/시뮬레이션/차트 신호/종목 검색이
> 동작하려면 이 라이브러리들이 외부에 접근할 수 있어야 합니다.

## 주요 기능

- **종목 등록**: 검색 → 실제 상장 종목 선택 (티커·종목명·시장·통화 자동)
- **매매 기록**: 일시(날짜+시간)·구분·단가·수량·사유 태그. 미국주식은 거래일 환율 자동 입력
- **손익 계산**: 이동평균법 평균단가, 실현손익(원 환산)
- **자산 구성**: 주식 평가액 + 현금(통화별) → 주식/현금 비중
- **시뮬레이션**: "그때 안 팔았다면 현재 +/− 얼마" (종가 기준)
- **차트 신호**: 이동평균·RSI·MACD·볼린저밴드 종합 신호 (참고용 보조지표)
- **인사이트 대시보드**: 승률·기대값, 조기매도/처분효과/물타기 성과
- **매매 경향 알림**: 매수 후 하락 多 / 매도 후 상승 多 경향 감지 시 회고 유도

## 구조

```
app/
  main.py         FastAPI 라우트 + 정적 서빙
  engine.py       이동평균 손익/평균단가/시뮬레이션 (순수 계산, 테스트 검증됨)
  insights.py     성과통계·매매습관·경향알림
  ta.py           기술적 지표·신호
  market_data.py  시세/검색/환율 어댑터 (FDR·yfinance·pykrx)
  models.py       SQLAlchemy 모델 (User/Stock/Transaction/Cash)
  database.py     SQLite 연결
  auth.py         로그인/세션 (pbkdf2_sha256)
static/           모바일 우선 프론트 (HTML/CSS/JS)
tests/            엔진 검증 테스트 (브로드컴·엔비디아 실데이터)
```

## 테스트

```bash
PYTHONPATH=. python tests/test_engine.py
```

## 배포 (Vercel + Supabase)

서버리스(Vercel)는 영구 디스크가 없어 SQLite 대신 외부 DB가 필요하다.
무료 Postgres인 Supabase를 사용한다.

### 1) Supabase에서 DB 연결 문자열 얻기
1. supabase.com 프로젝트 → **Project Settings → Database**
2. **Connection string → "Connection pooling"(Transaction, 포트 6543)** 복사
   - 형태: `postgresql://postgres.xxxx:[PASSWORD]@...pooler.supabase.com:6543/postgres`
3. `[PASSWORD]` 를 본인 DB 비밀번호로 교체 → 이게 `DATABASE_URL`

### 2) GitHub에 코드 올리기
- GitHub Desktop으로 이 폴더를 새 저장소로 push (또는 vercel CLI)

### 3) Vercel에서 배포
1. vercel.com → **Add New → Project → 방금 만든 깃허브 저장소 Import**
2. **Environment Variables** 에 2개 입력:
   - `DATABASE_URL` = 위 Supabase 연결 문자열
   - `SECRET_KEY` = 아무 긴 랜덤 문자열
3. **Deploy** → 발급된 URL을 친구들에게 공유

> 첫 접속 시 테이블이 자동 생성된다. (별도 마이그레이션 불필요)
> 무료 티어는 유휴 시 함수가 잠들어 첫 요청이 잠깐 느릴 수 있다.

## 환경변수 정리

| 변수 | 용도 | 없을 때 |
| --- | --- | --- |
| `DATABASE_URL` | Postgres(Supabase) 연결 | 로컬 SQLite로 동작 |
| `SECRET_KEY` | 세션 암호화 | 기본값(운영 비권장) |

## 메모

- 손익은 **이동평균법**. 매도는 평균단가를 바꾸지 않고 수량만 줄인다.
- 환율은 거래일 기준(USD 종목). 자산 구성의 USD 평가는 최근 환율로 환산.
- 차트 신호는 투자 권유가 아닌 참고용이며, 최종 판단·책임은 사용자에게 있다.
- 향후: 세금/수수료, 배당, 주식 분할 보정, 매매-현금 자동 연동, 푸시 알림 등.
