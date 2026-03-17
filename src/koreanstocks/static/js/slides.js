/**
 * slides.js — API 데이터를 받아 Reveal.js 슬라이드 동적 생성
 */

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function fmt(n, digits = 0) {
  if (n == null) return "-";
  return Number(n).toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function esc(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function chgClass(v) { return v >= 0 ? "pos" : "neg"; }

function chgText(v) {
  if (v == null) return "-";
  return (v >= 0 ? "▲" : "▼") + " " + Math.abs(v).toFixed(2) + "%";
}

function badgeClass(action) {
  const a = (action || "").toUpperCase();
  if (a === "BUY")  return "badge badge-buy";
  if (a === "SELL") return "badge badge-sell";
  return "badge badge-hold";
}

function slScoreBar(label, value, highlight) {
  const pct   = Math.min(100, Math.max(0, value || 0));
  const color = highlight
    ? "var(--accent)"
    : pct >= 70 ? "var(--buy)" : pct >= 40 ? "#ffaa00" : "var(--hold)";
  const weight = highlight ? "font-weight:700" : "";
  return `
    <div class="sl-score-row">
      <span class="sl-score-label" style="${weight}">${label}</span>
      <div class="sl-score-track">
        <div class="sl-score-fill" style="width:${pct}%;background:${color}"></div>
      </div>
      <span class="sl-score-val" style="${weight}">${pct.toFixed(0)}</span>
    </div>`;
}

// ── 거시경제 레짐 헬퍼 ──────────────────────────────────────────
function regimeStyle(regime) {
  if (regime === "risk_on")  return { color: "var(--buy)",  label: "위험선호 📈" };
  if (regime === "risk_off") return { color: "var(--sell)", label: "위험회피 📉" };
  return { color: "#ffaa00", label: "불확실 ⚠️" };
}

// ── 표지 슬라이드 ────────────────────────────────────────────────
function coverSlide(market, date, recs, macro) {
  const kospi  = market.KOSPI  || {};
  const kosdaq = market.KOSDAQ || {};
  const usd    = market.USDKRW || {};

  function mktCard(label, info) {
    if (!info || !info.close) return "";
    const chg = info.change || 0;
    return `
      <div class="sl-mkt-card">
        <div class="sl-mkt-label">${label}</div>
        <div class="sl-mkt-val">${fmt(info.close, 2)}</div>
        <div class="sl-mkt-chg ${chgClass(chg)}">${chgText(chg)}</div>
      </div>`;
  }

  // BUY/HOLD/SELL 분포
  const actions = { BUY: 0, HOLD: 0, SELL: 0 };
  let totalScore = 0;
  for (const r of recs) {
    const a = (r.ai_opinion?.action || "HOLD").toUpperCase();
    actions[a] = (actions[a] || 0) + 1;
    totalScore += r.composite_score || r.tech_score || 0;
  }
  const avgScore = recs.length > 0 ? (totalScore / recs.length).toFixed(1) : "-";

  // 거시경제 레짐 배지 (인라인)
  let macroBadge = "";
  let macroSummary = "";
  if (macro && macro.macro_regime) {
    const rs = regimeStyle(macro.macro_regime);
    macroBadge = `<span style="background:${rs.color}22;color:${rs.color};border:1px solid ${rs.color}55;
                               padding:1px 10px;border-radius:10px;font-size:.78em;font-weight:700;
                               vertical-align:middle">${rs.label}</span>`;
    if (macro.macro_summary) {
      macroSummary = `<div style="font-size:.8em;color:var(--muted);margin-top:2px">${esc(macro.macro_summary)}</div>`;
    }
  }

  // 상위 3종목 (좌정렬 칩)
  const top3 = recs.slice(0, 3);
  const top3Html = top3.length > 0
    ? top3.map(r => {
        const a = r.ai_opinion?.action || "HOLD";
        const c = a === "BUY" ? "var(--buy)" : a === "SELL" ? "var(--sell)" : "#ffaa00";
        const score = (r.composite_score || r.tech_score || 0).toFixed(0);
        return `<span style="background:var(--card-bg);border:1px solid var(--border);
                              padding:3px 10px;border-radius:6px;font-size:.8em;white-space:nowrap">
          <span style="color:${c}">●</span> ${esc(r.name || r.code)}
          <span style="color:var(--muted);margin-left:4px">${score}점</span>
        </span>`;
      }).join("") : "";

  const sep = `<div style="border-top:1px solid var(--border);margin:2px 0"></div>`;

  return `
    <section>
      <div class="sl-cover">
        <!-- 헤더 행: 제목 + 거시 배지 -->
        <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
          <div class="cover-title" style="margin:0">📊 오늘의 시장 브리핑</div>
          ${macroBadge}
        </div>

        <!-- 메타 행: 날짜 · 종목수 · 분포 · 평균 -->
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:.82em;color:var(--muted)">
          <span>${esc(date || "")}</span>
          <span style="color:var(--border)">·</span>
          <span>분석 ${recs.length}종목</span>
          <span style="color:var(--border)">·</span>
          ${actions.BUY  > 0 ? `<span style="color:var(--buy)">🟢 BUY ${actions.BUY}</span>`   : ""}
          ${actions.HOLD > 0 ? `<span style="color:#ffaa00">🟡 HOLD ${actions.HOLD}</span>`     : ""}
          ${actions.SELL > 0 ? `<span style="color:var(--sell)">🔴 SELL ${actions.SELL}</span>` : ""}
          <span>평균 ${avgScore}점</span>
        </div>

        <!-- 거시 요약 -->
        ${macroSummary}

        ${sep}

        <!-- 상위 3종목 -->
        ${top3Html ? `<div style="display:flex;gap:8px;flex-wrap:wrap">${top3Html}</div>` : ""}

        <!-- 시장 지수 -->
        <div class="sl-mkt-row">
          ${mktCard("KOSPI",   kospi)}
          ${mktCard("KOSDAQ",  kosdaq)}
          ${usd.close ? mktCard("USD/KRW", { close: usd.close, change: 0 }) : ""}
        </div>

        ${sep}

        <!-- 하단 안내 -->
        <div class="sl-disclaimer">⏱️ 단기 신호 (ML 10거래일 · 기술지표 5~60일 · 뉴스 당일 기준) &nbsp;·&nbsp; ← / → 키 또는 터치로 탐색</div>
      </div>
    </section>`;
}

// ── 종목 슬라이드 ────────────────────────────────────────────────
function toStrList(val) {
  if (!val) return "";
  if (Array.isArray(val)) return val.join(" · ");
  return String(val);
}

function bucketBadge(bucket, label) {
  if (!bucket || !label) return "";
  const cls = { volume: "bucket-volume", momentum: "bucket-momentum", rebound: "bucket-rebound" };
  return `<span class="bucket-badge ${cls[bucket] || "bucket-volume"}">${label}</span>`;
}

function _indicatorChips(indic, currentPrice, targetPrice) {
  if (!indic) return "";
  const chips = [];

  // RSI
  if (indic.rsi != null) {
    const rsi = indic.rsi;
    const rsiColor = rsi <= 30 ? "var(--buy)" : rsi >= 70 ? "var(--sell)" : "var(--muted)";
    const rsiLabel = rsi <= 30 ? "과매도" : rsi >= 70 ? "과매수" : "보통";
    chips.push(`<span style="background:var(--card-bg);border:1px solid var(--border);
                              padding:2px 8px;border-radius:6px;font-size:.76em;white-space:nowrap">
      RSI <span style="color:${rsiColor};font-weight:700">${rsi.toFixed(0)}</span>
      <span style="color:${rsiColor}">(${rsiLabel})</span>
    </span>`);
  }

  // MACD
  if (indic.macd != null && indic.macd_sig != null) {
    const bull = indic.macd > indic.macd_sig;
    const macdColor = bull ? "var(--buy)" : "var(--sell)";
    const macdLabel = bull ? "↑상승" : "↓하락";
    chips.push(`<span style="background:var(--card-bg);border:1px solid var(--border);
                              padding:2px 8px;border-radius:6px;font-size:.76em;white-space:nowrap">
      MACD <span style="color:${macdColor};font-weight:700">${macdLabel}</span>
    </span>`);
  }

  // BB 위치
  if (indic.bb_pos != null) {
    const bp = indic.bb_pos;
    const bpColor = bp <= 0.2 ? "var(--buy)" : bp >= 0.8 ? "var(--sell)" : "var(--muted)";
    const bpLabel = bp <= 0.2 ? "하단" : bp >= 0.8 ? "상단" : "중간";
    chips.push(`<span style="background:var(--card-bg);border:1px solid var(--border);
                              padding:2px 8px;border-radius:6px;font-size:.76em;white-space:nowrap">
      BB <span style="color:${bpColor};font-weight:700">${bpLabel}</span>
      <span style="color:var(--muted)">${(bp * 100).toFixed(0)}%</span>
    </span>`);
  }

  // 목표 상승여력
  if (currentPrice > 0 && targetPrice > 0) {
    const upside = ((targetPrice - currentPrice) / currentPrice * 100);
    const uColor = upside >= 0 ? "var(--buy)" : "var(--sell)";
    chips.push(`<span style="background:var(--card-bg);border:1px solid var(--border);
                              padding:2px 8px;border-radius:6px;font-size:.76em;white-space:nowrap">
      🎯 <span style="color:${uColor};font-weight:700">${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%</span>
    </span>`);
  }

  if (!chips.length) return "";
  return `<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:7px">${chips.join("")}</div>`;
}

function stockSlide(rec) {
  const opinion    = rec.ai_opinion || {};
  const action     = opinion.action || "HOLD";
  const si         = rec.sentiment_info || {};
  const news       = si.headlines || si.articles?.slice(0,3).map(a => a.title) || [];
  const strength   = toStrList(opinion.strength);
  const weakness   = toStrList(opinion.weakness);
  const ml_score   = rec.ml_score != null ? rec.ml_score : (rec.tech_score || 0);
  const sent_norm  = Math.min(100, Math.max(0, ((rec.sentiment_score || 0) + 100) / 2));
  const composite  = rec.composite_score || 0;
  const indic      = rec.indicators || {};
  const curPrice   = parseInt(rec.current_price || 0);
  const tgtPrice   = parseInt(opinion.target_price || 0);

  const newsHtml = news.slice(0, 3).map(h =>
    `<div class="sl-news-item">· ${esc(h)}</div>`
  ).join("");

  const swHtml = (strength || weakness) ? `
    <div class="sl-sw-grid">
      ${strength ? `<div class="sl-sw-box">
        <div class="sl-sw-title buy">💪 강점</div>
        <div>${esc(strength)}</div>
      </div>` : ""}
      ${weakness ? `<div class="sl-sw-box">
        <div class="sl-sw-title hold">⚠️ 약점</div>
        <div>${esc(weakness)}</div>
      </div>` : ""}
    </div>` : "";

  // composite_score 색상
  const compColor = composite >= 65 ? "var(--buy)" : composite >= 45 ? "#ffaa00" : "var(--sell)";

  return `
    <section>
      <div class="sl-stock">
        <!-- 헤더 -->
        <div class="sl-stock-header">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span class="sl-stock-name">${esc(rec.name || rec.code)}</span>
            <span class="sl-stock-code">${esc(rec.code)}</span>
            ${bucketBadge(rec.bucket, rec.bucket_label)}
            <span class="${badgeClass(action)}">${action}</span>
            <span style="background:${compColor}22;color:${compColor};border:1px solid ${compColor}66;
                         padding:2px 10px;border-radius:10px;font-size:.82em;font-weight:700">
              종합 ${composite.toFixed(1)}점
            </span>
          </div>
          <div class="sl-stock-price">
            <div class="sl-price-val">₩${fmt(curPrice)}</div>
            <div class="sl-price-chg ${chgClass(rec.change_pct)}">${chgText(rec.change_pct)}</div>
          </div>
        </div>

        <!-- 본문 2열 -->
        <div class="sl-stock-body">
          <!-- 좌측: 점수 + 지표 칩 + 뉴스 -->
          <div class="sl-col">
            ${slScoreBar("종합점수", composite, true)}
            ${slScoreBar("기술점수", rec.tech_score)}
            ${slScoreBar("ML점수",   ml_score)}
            ${slScoreBar("감성점수", sent_norm)}
            ${_indicatorChips(indic, curPrice, tgtPrice)}
            ${tgtPrice > 0 ? `<div class="sl-target" style="margin-top:8px">🎯 목표가: ₩${fmt(tgtPrice)}</div>` : ""}
            ${newsHtml ? `<div class="sl-news-wrap">${newsHtml}</div>` : ""}
          </div>

          <!-- 우측: AI 요약 + 강점/약점 -->
          <div class="sl-col">
            <div class="sl-ai-box">${esc(opinion.summary) || "분석 내용 없음"}</div>
            ${swHtml}
          </div>
        </div>
      </div>
    </section>`;
}

// ── 종합 요약 슬라이드 (마지막) ──────────────────────────────────
function summarySlide(recs, macro) {
  // BUY/HOLD/SELL 분포 + 평균 점수
  const dist = { BUY: 0, HOLD: 0, SELL: 0 };
  let totalScore = 0;
  for (const r of recs) {
    const a = (r.ai_opinion?.action || "HOLD").toUpperCase();
    dist[a] = (dist[a] || 0) + 1;
    totalScore += r.composite_score || 0;
  }
  const avgScore = recs.length > 0 ? (totalScore / recs.length).toFixed(1) : "-";

  // 전체 종목 요약 테이블 행 (점수순 정렬은 이미 API에서 보장)
  const tableRows = recs.map((r, i) => {
    const action   = (r.ai_opinion?.action || "HOLD").toUpperCase();
    const comp     = r.composite_score || 0;
    const cur      = parseInt(r.current_price  || 0);
    const tgt      = parseInt(r.ai_opinion?.target_price || 0);
    const upside   = (tgt > 0 && cur > 0) ? ((tgt - cur) / cur * 100) : null;
    const indic    = r.indicators || {};
    const rsiRaw   = indic.rsi;
    const macdBull = (indic.macd != null && indic.macd_sig != null) ? indic.macd > indic.macd_sig : null;

    const aColor = action === "BUY" ? "var(--buy)" : action === "SELL" ? "var(--sell)" : "#ffaa00";
    const cColor = comp >= 65 ? "var(--buy)" : comp >= 45 ? "#ffaa00" : "var(--sell)";

    const uHtml = upside != null
      ? `<span style="color:${upside >= 0 ? "var(--buy)" : "var(--sell)"}">${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%</span>`
      : `<span style="color:var(--muted)">—</span>`;

    const rsiHtml = rsiRaw != null
      ? (() => {
          const v = rsiRaw.toFixed(0);
          const c = rsiRaw <= 30 ? "var(--buy)" : rsiRaw >= 70 ? "var(--sell)" : "var(--muted)";
          return `<span style="color:${c}">${v}</span>`;
        })()
      : `<span style="color:var(--muted)">—</span>`;

    const macdHtml = macdBull != null
      ? `<span style="color:${macdBull ? "var(--buy)" : "var(--sell)"}">${macdBull ? "↑" : "↓"}</span>`
      : `<span style="color:var(--muted)">—</span>`;

    const rowBg = i % 2 === 0 ? "" : "background:rgba(255,255,255,.025)";

    return `
      <tr style="${rowBg}">
        <td style="padding:4px 8px;font-weight:600">
          <span style="color:var(--muted);font-size:.82em;margin-right:4px">${i + 1}.</span>
          ${esc(r.name || r.code)}
          <span style="color:var(--muted);font-size:.74em;margin-left:4px">${esc(r.code)}</span>
        </td>
        <td style="padding:4px 6px;text-align:center">
          <span style="color:${aColor};font-weight:700;font-size:.84em">${action}</span>
        </td>
        <td style="padding:4px 6px;text-align:right">
          <span style="color:${cColor};font-weight:700">${comp.toFixed(0)}</span>
        </td>
        <td style="padding:4px 6px;text-align:right">${uHtml}</td>
        <td style="padding:4px 6px;text-align:center">${rsiHtml}</td>
        <td style="padding:4px 6px;text-align:center">${macdHtml}</td>
      </tr>`;
  }).join("");

  // 거시경제 한 줄
  let macroLine = "";
  if (macro && macro.macro_regime) {
    const rs = regimeStyle(macro.macro_regime);
    macroLine = `
      <div style="display:flex;align-items:center;gap:8px;font-size:.8em;flex-wrap:wrap">
        <span style="color:var(--muted)">거시 레짐</span>
        <span style="color:${rs.color};font-weight:700">${rs.label}</span>
        ${macro.macro_summary ? `<span style="color:var(--muted)">— ${esc(macro.macro_summary)}</span>` : ""}
      </div>`;
  }

  const sep = `<div style="border-top:1px solid var(--border);margin:2px 0"></div>`;

  return `
    <section>
      <div class="sl-cover">
        <!-- 헤더 -->
        <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
          <div class="cover-title" style="margin:0">📋 종합 요약</div>
          <span style="font-size:.82em;color:var(--muted)">${recs.length}개 종목 · 평균 ${avgScore}점</span>
          <span style="font-size:.82em">
            ${dist.BUY  > 0 ? `<span style="color:var(--buy)">🟢${dist.BUY}</span> ` : ""}
            ${dist.HOLD > 0 ? `<span style="color:#ffaa00">🟡${dist.HOLD}</span> ` : ""}
            ${dist.SELL > 0 ? `<span style="color:var(--sell)">🔴${dist.SELL}</span>` : ""}
          </span>
        </div>

        ${macroLine}
        ${sep}

        <!-- 전체 종목 요약 테이블 -->
        <table style="width:100%;border-collapse:collapse;font-size:.8em">
          <thead>
            <tr style="color:var(--muted);font-size:.84em;border-bottom:1px solid var(--border)">
              <th style="text-align:left;padding:3px 8px;font-weight:500">종목</th>
              <th style="padding:3px 6px;font-weight:500">시그널</th>
              <th style="text-align:right;padding:3px 6px;font-weight:500">종합</th>
              <th style="text-align:right;padding:3px 6px;font-weight:500">상승여력</th>
              <th style="text-align:center;padding:3px 6px;font-weight:500">RSI</th>
              <th style="text-align:center;padding:3px 6px;font-weight:500">MACD</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>

        ${sep}
        <div class="sl-disclaimer">※ 본 분석은 투자 참고용이며 투자 결정의 책임은 투자자 본인에게 있습니다.</div>
      </div>
    </section>`;
}

// ── 테마 토글 ────────────────────────────────────────────────────
function updateRevealTheme() {
  const link = document.getElementById("reveal-theme");
  if (!link) return;
  const isDark = (document.documentElement.getAttribute("data-theme") || "dark") === "dark";
  const base = "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/theme/";
  link.href = base + (isDark ? "black.css" : "white.css");
}

function toggleTheme() {
  const root = document.documentElement;
  const next = (root.getAttribute("data-theme") || "dark") === "dark" ? "light" : "dark";
  root.setAttribute("data-theme", next);
  localStorage.setItem("ks-theme", next);
  updateRevealTheme();
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.textContent = next === "dark" ? "☀️" : "🌙";
}

// ── 슬라이드 빌드 + Reveal 초기화 ───────────────────────────────
async function buildSlides() {
  const container = document.getElementById("slide-container");

  try {
    const [recData, marketData, macroData] = await Promise.all([
      fetchJSON("/api/recommendations"),
      fetchJSON("/api/market").catch(() => ({ KOSPI: {}, KOSDAQ: {} })),
      fetchJSON("/api/macro_context").catch(() => null),
    ]);

    const recs = recData.recommendations || [];
    const date = recData.date || "";

    let html = coverSlide(marketData, date, recs, macroData);
    html += recs.map(stockSlide).join("");
    html += summarySlide(recs, macroData);
    container.innerHTML = html;

  } catch (err) {
    container.innerHTML = `
      <section>
        <div class="sl-cover">
          <h2 style="color:var(--sell)">데이터 로드 실패</h2>
          <p>${esc(err.message)}</p>
          <p style="font-size:.85em;color:var(--muted)">
            서버가 실행 중인지 확인하거나
            <a href="/api/recommendations/run">분석을 실행</a>해 주세요.
          </p>
        </div>
      </section>`;
  }

  // 로딩 오버레이 숨기기
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.style.display = "none";

  // ── 진단: DOM 섹션 수 확인 ──────────────────────────────────────
  const domSections = container.querySelectorAll("section").length;
  console.log(`[KS] DOM sections: ${domSections}`);

  // ── Reveal.js 초기화 ─────────────────────────────────────────────
  try { Reveal.destroy(); } catch(e) { /* 미초기화 상태면 무시 */ }
  await Reveal.initialize({
    hash: false,
    controls: true,
    progress: true,
    center: false,
    slideNumber: "c/t",
    transition: "slide",
    backgroundTransition: "fade",
    width: 1100,
    height: 700,
    margin: 0.05,
    minScale: 0.5,
    maxScale: 1.5,
  });

  const revealTotal = typeof Reveal.getTotalSlides === "function" ? Reveal.getTotalSlides() : "?";
  console.log(`[KS] Reveal total slides: ${revealTotal}`);

  updateRevealTheme();
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    const isDark = (document.documentElement.getAttribute("data-theme") || "dark") === "dark";
    btn.textContent = isDark ? "☀️" : "🌙";
  }
}

buildSlides();
