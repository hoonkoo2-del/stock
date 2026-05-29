// ------------------------------------------------------------- 유틸
const $ = (s) => document.querySelector(s);
const C = $("#content"), NAV = $("#bottomnav"), TR = $("#topright"), TT = $("#title");
const won = (n) => n == null ? "-" : Number(n).toLocaleString("ko-KR") + "원";
const num = (n, d = 2) => n == null ? "-" : Number(n).toLocaleString("ko-KR", { maximumFractionDigits: d });
const cls = (n) => n > 0 ? "up" : n < 0 ? "down" : "";
const sign = (n) => (n > 0 ? "+" : "") + won(n);

async function api(path, opts = {}) {
  const r = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin", ...opts,
  });
  if (r.status === 401) { showAuth(); throw new Error("auth"); }
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "오류"); }
  return r.status === 204 ? null : r.json();
}

let state = { stock: null };

// ------------------------------------------------------------- 인증
function showAuth() {
  NAV.classList.add("hidden"); TR.innerHTML = ""; TT.textContent = "주식 매매 저널";
  C.innerHTML = `
    <div class="card">
      <h2>로그인</h2>
      <div class="field"><label>아이디</label><input id="u" autocomplete="username"></div>
      <div class="field"><label>비밀번호</label><input id="p" type="password" autocomplete="current-password"></div>
      <button class="btn" id="login">로그인</button>
      <button class="btn sec" id="reg">회원가입</button>
      <p id="err" class="sub" style="color:var(--up);margin-top:10px"></p>
    </div>`;
  const go = async (path) => {
    try {
      await api(path, { method: "POST", body: JSON.stringify({ username: $("#u").value, password: $("#p").value }) });
      start();
    } catch (e) { $("#err").textContent = e.message; }
  };
  $("#login").onclick = () => go("/login");
  $("#reg").onclick = () => go("/register");
}

// ------------------------------------------------------------- 대시보드
async function viewDashboard() {
  setNav("dashboard"); TT.textContent = "인사이트"; C.innerHTML = `<div class="center">불러오는 중…</div>`;
  const d = await api("/dashboard");
  const comp = d.composition, perf = d.performance, hab = d.habits;
  let html = "";

  d.alerts.forEach(a => html += `<div class="alert">⚠️ ${a.message}</div>`);

  // 자산 구성
  html += `<div class="card"><h3>자산 구성</h3>
    <div class="big">${won(comp.total_krw)}</div>
    <div class="compbar"><div class="s" style="width:${comp.stock_pct}%"></div><div class="c" style="width:${comp.cash_pct}%"></div></div>
    <div class="legend"><span><i style="background:var(--accent2)"></i>주식 ${comp.stock_pct}% · ${won(comp.stock_krw)}</span>
    <span><i style="background:#5a6473"></i>현금 ${comp.cash_pct}% · ${won(comp.cash_krw)}</span></div>
    <div class="sub" style="margin-top:8px">한국 ${won(comp.by_market.KR)} · 미국 ${won(comp.by_market.US)}</div></div>`;

  // 성과 통계
  if (perf.trade_count) {
    html += `<div class="card"><h3>성과 통계</h3>
      <div class="stat"><span>실현손익 누계</span><b class="${cls(perf.total_realized_krw)}">${sign(perf.total_realized_krw)}</b></div>
      <div class="stat"><span>승률</span><b>${perf.win_rate}% (${perf.win_count}/${perf.trade_count})</b></div>
      <div class="stat"><span>평균 수익 / 손실</span><b>${won(perf.avg_win_krw)} / ${won(perf.avg_loss_krw)}</b></div>
      <div class="stat"><span>손익비</span><b>${perf.profit_factor}</b></div>
      <div class="stat"><span>기대값(1회당)</span><b class="${cls(perf.expectancy_krw)}">${sign(perf.expectancy_krw)}</b></div></div>`;
  }

  // 매매 습관
  let hh = "";
  if (hab.early_sell) hh += `<div class="stat"><span>매도 후 상승 비율</span><b>${hab.early_sell.ratio_pct}% (평균 ${hab.early_sell.avg_change_pct > 0 ? "+" : ""}${hab.early_sell.avg_change_pct}%)</b></div>`;
  if (hab.disposition) hh += `<div class="stat"><span>평균 보유기간 (이익/손실)</span><b>${hab.disposition.win_avg_days}일 / ${hab.disposition.loss_avg_days}일</b></div>`;
  if (hab.average_down) hh += `<div class="stat"><span>물타기 성과</span><b>${hab.average_down.success_pct}% (${hab.average_down.success_count}/${hab.average_down.count}, 평균 ${hab.average_down.avg_contrib_pct > 0 ? "+" : ""}${hab.average_down.avg_contrib_pct}%)</b></div>`;
  if (hh) html += `<div class="card"><h3>매매 습관 진단</h3>${hh}<p class="disc">본인의 과거 매매 데이터에 대한 회고 분석이며 투자 권유가 아닙니다.</p></div>`;

  if (!perf.trade_count && !hh) html += `<div class="center">거래를 등록하면 인사이트가 표시됩니다.</div>`;
  C.innerHTML = html;
}

// ------------------------------------------------------------- 포트폴리오
async function viewPortfolio() {
  setNav("portfolio"); TT.textContent = "포트폴리오"; C.innerHTML = `<div class="center">불러오는 중…</div>`;
  const list = await api("/stocks");
  if (!list.length) { C.innerHTML = `<div class="center">＋ 종목 탭에서 종목을 추가하세요.</div>`; return; }
  let html = "";
  list.forEach(s => {
    html += `<div class="card" onclick="openStock(${s.id})">
      <div class="row"><div><b>${s.name}</b> <span class="pill ${s.market.toLowerCase()}">${s.ticker}</span></div>
      <div style="text-align:right">${s.current_price != null ? num(s.current_price) + (s.currency === "USD" ? "$" : "원") : "<span class='sub'>시세 -</span>"}</div></div>
      <div class="row" style="margin-top:8px">
        <div class="sub">${s.qty > 0 ? `${num(s.qty, 4)}주 · 평단 ${num(s.avg_cost)}` : "보유 없음"}</div>
        <div style="text-align:right">${s.unrealized_krw != null ? `<span class="${cls(s.unrealized_krw)}">평가 ${sign(s.unrealized_krw)}</span><br>` : ""}<span class="sub ${cls(s.realized_krw)}">실현 ${sign(s.realized_krw)}</span></div>
      </div></div>`;
  });
  C.innerHTML = html;
}

// ------------------------------------------------------------- 종목 추가 (검색)
function viewAddStock() {
  setNav("addstock"); TT.textContent = "종목 추가"; TR.innerHTML = "";
  C.innerHTML = `<div class="card"><div class="field"><label>종목 검색 (이름/티커)</label>
    <input id="q" placeholder="예: 엔비디아, NVDA, 삼성전자"></div></div><div id="res"></div>`;
  let timer;
  $("#q").oninput = (e) => {
    clearTimeout(timer);
    const q = e.target.value.trim();
    timer = setTimeout(async () => {
      if (q.length < 1) { $("#res").innerHTML = ""; return; }
      $("#res").innerHTML = `<div class="center">검색 중…</div>`;
      try {
        const r = await api("/search?q=" + encodeURIComponent(q));
        if (!r.length) { $("#res").innerHTML = `<div class="center">결과 없음 (네트워크/검색어 확인)</div>`; return; }
        $("#res").innerHTML = `<div class="card">` + r.map(x =>
          `<div class="searchitem" onclick='addStock(${JSON.stringify(x)})'>
            <span><b>${x.name}</b> <span class="pill ${x.market.toLowerCase()}">${x.ticker}</span></span>
            <span class="sub">${x.market}</span></div>`).join("") + `</div>`;
      } catch (e) { $("#res").innerHTML = `<div class="center">${e.message}</div>`; }
    }, 350);
  };
}
async function addStock(x) {
  const s = await api("/stocks", { method: "POST", body: JSON.stringify(x) });
  openStock(s.id);
}

// ------------------------------------------------------------- 종목 상세
async function openStock(id) {
  NAV.classList.remove("hidden");
  const [list, txs] = await Promise.all([api("/stocks"), api(`/stocks/${id}/transactions`)]);
  const s = list.find(x => x.id === id); state.stock = s;
  TT.textContent = s.name; TR.innerHTML = `<button onclick="viewPortfolio()">‹ 목록</button>`;
  let html = `<div class="card">
    <div class="row"><div><b>${s.name}</b> <span class="pill ${s.market.toLowerCase()}">${s.ticker}</span></div>
    <div class="big" style="font-size:20px">${s.current_price != null ? num(s.current_price) + (s.currency === "USD" ? "$" : "원") : "-"}</div></div>
    <div class="row" style="margin-top:10px">
      <div class="sub">${s.qty > 0 ? `${num(s.qty, 4)}주 · 평단 ${num(s.avg_cost)}` : "보유 없음"}</div>
      <div style="text-align:right">${s.unrealized_krw != null ? `<span class="${cls(s.unrealized_krw)}">평가 ${sign(s.unrealized_krw)}</span> · ` : ""}<span class="${cls(s.realized_krw)}">실현 ${sign(s.realized_krw)}</span></div>
    </div></div>
    <div class="seg"><button class="sec btn sm" style="flex:1" onclick="viewSimulation(${id})">안 팔았다면?</button>
      <button class="sec btn sm" style="flex:1" onclick="viewTA(${id})">차트 신호</button></div>
    <h3>매매 내역 <span class="link" style="float:right" onclick="addTxForm(${id})">＋ 직접입력</span></h3>`;
  if (!txs.length) html += `<div class="center">거래를 추가하세요.</div>`;
  txs.forEach(t => {
    const dt = new Date(t.dt);
    html += `<div class="tx">
      <div><div class="side ${t.side}">${t.side === "buy" ? "매수" : "매도"}</div><div class="date">${dt.toLocaleDateString("ko-KR")} ${dt.toTimeString().slice(0, 5)}</div></div>
      <div class="qp">${num(t.qty, 4)}주<br>${num(t.price)}</div>
      <div class="amt">${num(t.amount)}<div class="tag">${t.tag || ""} <span class="link" onclick="delTx(${t.id},${id})">삭제</span></div></div>
    </div>`;
  });
  C.innerHTML = html;
}

const BUY_TAGS = ["실적/펀더멘털", "차트/기술적신호", "뉴스·이슈", "저평가 판단", "분할매수", "단순감/기타"];
const SELL_TAGS = ["목표가 도달", "손절룰", "차트/기술적신호", "자금 필요", "비중 조절", "단순감/기타"];

function addTxForm(id) {
  let side = "buy";
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  const tagOpts = () => (side === "buy" ? BUY_TAGS : SELL_TAGS).map(t => `<option>${t}</option>`).join("");
  C.innerHTML = `<div class="card"><h2>거래 등록</h2>
    <div class="seg"><button id="b" class="on buy" onclick="setSide('buy')">매수</button>
      <button id="s" onclick="setSide('sell')">매도</button></div>
    <div class="field"><label>일시</label><input id="dt" type="datetime-local" value="${now.toISOString().slice(0, 16)}"></div>
    <div class="field"><label>단가 (${state.stock.currency})</label><input id="price" type="number" inputmode="decimal"></div>
    <div class="field"><label>수량</label><input id="qty" type="number" inputmode="decimal"></div>
    <div class="field"><label>사유 태그</label><select id="tag">${tagOpts()}</select></div>
    <div class="field"><label>메모 (선택)</label><input id="memo"></div>
    <button class="btn" id="save">저장${state.stock.currency === "USD" ? " (환율 자동)" : ""}</button>
    <button class="btn sec" onclick="openStock(${id})">취소</button>
    <p id="err" class="sub" style="color:var(--up)"></p></div>`;
  window.setSide = (sd) => { side = sd; $("#b").className = sd === "buy" ? "on buy" : ""; $("#s").className = sd === "sell" ? "on sell" : ""; $("#tag").innerHTML = tagOpts(); };
  $("#save").onclick = async () => {
    try {
      await api(`/stocks/${id}/transactions`, {
        method: "POST", body: JSON.stringify({
          dt: $("#dt").value, side, price: parseFloat($("#price").value),
          qty: parseFloat($("#qty").value), tag: $("#tag").value, memo: $("#memo").value,
        })
      });
      openStock(id);
    } catch (e) { $("#err").textContent = e.message; }
  };
}
async function delTx(txid, sid) { if (confirm("이 거래를 삭제할까요?")) { await api(`/transactions/${txid}`, { method: "DELETE" }); openStock(sid); } }

// ------------------------------------------------------------- 시뮬레이션
async function viewSimulation(id) {
  TT.textContent = "안 팔았다면?"; C.innerHTML = `<div class="center">계산 중…</div>`;
  try {
    const d = await api(`/stocks/${id}/simulation`);
    let html = `<div class="card"><div class="sub">현재 종가 ${num(d.current_price)} 기준</div></div>`;
    if (!d.simulations.length) html += `<div class="center">매도 기록이 없습니다.</div>`;
    d.simulations.forEach(x => {
      const dt = new Date(x.dt);
      html += `<div class="card"><div class="row"><b>${dt.toLocaleDateString("ko-KR")} 매도 ${num(x.qty, 4)}주</b></div>
        <div class="stat"><span>실제 실현손익</span><b class="${cls(x.actual_pnl_krw)}">${sign(x.actual_pnl_krw)}</b></div>
        <div class="stat"><span>안 팔았다면 (현재)</span><b class="${cls(x.hypothetical_pnl_krw)}">${sign(x.hypothetical_pnl_krw)}</b></div>
        <div class="stat"><span>기회손익</span><b class="${cls(x.opportunity_krw)}">${sign(x.opportunity_krw)}</b></div></div>`;
    });
    html += `<button class="btn sec" onclick="openStock(${id})">‹ 종목으로</button>`;
    C.innerHTML = html;
  } catch (e) { C.innerHTML = `<div class="center">${e.message}</div><button class="btn sec" onclick="openStock(${id})">‹ 종목으로</button>`; }
}

// ------------------------------------------------------------- TA
async function viewTA(id) {
  TT.textContent = "차트 신호"; C.innerHTML = `<div class="center">분석 중…</div>`;
  try {
    const t = await api(`/stocks/${id}/ta`);
    if (!t.ok) { C.innerHTML = `<div class="center">${t.reason}</div><button class="btn sec" onclick="openStock(${id})">‹ 종목으로</button>`; return; }
    const oc = t.overall.includes("매수") ? "up" : t.overall.includes("매도") ? "down" : "";
    let html = `<div class="card"><div class="row"><span class="sub">종합 신호</span><b class="${oc}" style="font-size:18px">${t.overall}</b></div>
      <div class="stat"><span>추세</span><b>${t.trend}</b></div>
      <div class="stat"><span>RSI</span><b>${t.rsi}</b></div>
      <div class="stat"><span>20 / 60일선</span><b>${num(t.ma20)} / ${num(t.ma60)}</b></div></div>
      <div class="card"><h3>근거</h3>${t.signals.map(s => `<div class="stat"><span>${s}</span></div>`).join("")}
      <p class="disc">${t.disclaimer}</p></div>
      <button class="btn sec" onclick="openStock(${id})">‹ 종목으로</button>`;
    C.innerHTML = html;
  } catch (e) { C.innerHTML = `<div class="center">${e.message}</div><button class="btn sec" onclick="openStock(${id})">‹ 종목으로</button>`; }
}

// ------------------------------------------------------------- 현금 (포트폴리오 상단 메뉴)
async function viewCash() {
  TT.textContent = "현금"; const cash = await api("/cash");
  const find = (c) => (cash.find(x => x.currency === c) || {}).balance || 0;
  C.innerHTML = `<div class="card"><h2>현금 자산</h2>
    <div class="field"><label>원화 (KRW)</label><input id="krw" type="number" value="${find("KRW")}"></div>
    <div class="field"><label>달러 (USD)</label><input id="usd" type="number" value="${find("USD")}"></div>
    <button class="btn" id="save">저장</button>
    <button class="btn sec" onclick="viewDashboard()">완료</button></div>`;
  $("#save").onclick = async () => {
    await api("/cash", { method: "POST", body: JSON.stringify({ currency: "KRW", balance: parseFloat($("#krw").value) || 0 }) });
    await api("/cash", { method: "POST", body: JSON.stringify({ currency: "USD", balance: parseFloat($("#usd").value) || 0 }) });
    viewDashboard();
  };
}

// ------------------------------------------------------------- 네비/부트
function setNav(v) {
  NAV.classList.remove("hidden");
  NAV.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.view === v));
  TR.innerHTML = `<button onclick="viewCash()">현금</button> <button onclick="logout()">로그아웃</button>`;
}
NAV.querySelectorAll("button").forEach(b => b.onclick = () => {
  state.stock = null;
  ({ dashboard: viewDashboard, portfolio: viewPortfolio, addstock: viewAddStock }[b.dataset.view])();
});
async function logout() { await api("/logout", { method: "POST" }); showAuth(); }

async function start() {
  try { await api("/me"); viewDashboard(); }
  catch { showAuth(); }
}
start();
