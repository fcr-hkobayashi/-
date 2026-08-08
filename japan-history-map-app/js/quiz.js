// クイズ機能: 年号当て / 場所当て / できごと当て + 間違えた問題の復習(簡易間隔反復)
import { EVENTS, PREFECTURES, CATEGORY_META, ERAS, eraOf } from './data.js';

const STATS_KEY = 'jhma_quiz_stats_v1';
const HISTORY_KEY = 'jhma_quiz_history_v1';
const QUESTIONS_PER_ROUND = 10;

function loadStats() {
  try { return JSON.parse(localStorage.getItem(STATS_KEY)) ?? {}; }
  catch { return {}; }
}
function saveStats(stats) { localStorage.setItem(STATS_KEY, JSON.stringify(stats)); }

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) ?? []; }
  catch { return []; }
}
function saveHistory(history) { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-20))); }

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function sample(arr, n) { return shuffle(arr).slice(0, n); }

function recordAnswer(stats, eventId, correct) {
  const s = stats[eventId] ?? { seen: 0, correct: 0, wrong: 0, box: 1 };
  s.seen++;
  if (correct) { s.correct++; s.box = Math.min(5, s.box + 1); }
  else { s.wrong++; s.box = 1; }
  s.lastSeen = Date.now();
  stats[eventId] = s;
  return stats;
}

function buildQuestion(mode, event, pool) {
  const others = pool.filter(e => e.id !== event.id);
  if (mode === 'pref') {
    const distractorPrefs = sample([...new Set(others.map(e => e.pref))].filter(p => p !== event.pref), 3);
    while (distractorPrefs.length < 3) {
      const p = PREFECTURES[Math.floor(Math.random() * PREFECTURES.length)];
      if (p !== event.pref && !distractorPrefs.includes(p)) distractorPrefs.push(p);
    }
    return {
      event,
      prompt: `${event.year}年に起きた「${event.title}」。関係が深い都道府県はどれ?`,
      choices: shuffle([event.pref, ...distractorPrefs]),
      answer: event.pref,
    };
  }
  if (mode === 'event') {
    const distractors = sample(others.filter(e => e.cat === event.cat), 3);
    const pad = sample(others.filter(e => !distractors.includes(e)), 3 - distractors.length);
    const options = [...distractors, ...pad].slice(0, 3);
    return {
      event,
      prompt: `${event.year}年、${event.pref}で起きたできごとはどれ?`,
      choices: shuffle([event.title, ...options.map(e => e.title)]),
      answer: event.title,
    };
  }
  // mode === 'year'
  const nearYears = sample(others, 8).map(e => e.year).filter(y => y !== event.year);
  const distractorYears = [];
  for (const y of shuffle(nearYears)) {
    if (distractorYears.length >= 3) break;
    if (!distractorYears.includes(y)) distractorYears.push(y);
  }
  while (distractorYears.length < 3) {
    const y = event.year + (Math.floor(Math.random() * 20) - 10) * (Math.random() < 0.5 ? 1 : 3);
    if (y !== event.year && y >= 1600 && y <= new Date().getFullYear() && !distractorYears.includes(y)) distractorYears.push(y);
  }
  return {
    event,
    prompt: `「${event.title}」(${event.pref})が起きたのは何年?`,
    choices: shuffle([event.year, ...distractorYears]).map(String),
    answer: String(event.year),
  };
}

export function initQuiz(root) {
  root.innerHTML = `
    <div class="quiz-setup" id="quizSetup">
      <h2>クイズで復習</h2>
      <p class="quiz-intro">全${EVENTS.length}件の出来事から出題します。繰り返し挑戦して定着させましょう。</p>
      <fieldset class="quiz-mode-group">
        <legend>出題モード</legend>
        <label><input type="radio" name="qmode" value="year" checked>年号当て</label>
        <label><input type="radio" name="qmode" value="pref">場所当て</label>
        <label><input type="radio" name="qmode" value="event">できごと当て</label>
        <label><input type="radio" name="qmode" value="mix">ミックス</label>
      </fieldset>
      <fieldset class="quiz-era-group" id="quizEraGroup">
        <legend>出題範囲(時代)</legend>
      </fieldset>
      <div class="quiz-actions">
        <button id="startQuizBtn" class="primary">クイズ開始(${QUESTIONS_PER_ROUND}問)</button>
        <button id="reviewQuizBtn" class="secondary">苦手を復習する</button>
      </div>
      <div class="quiz-stats" id="quizStats"></div>
    </div>
    <div class="quiz-play" id="quizPlay" hidden>
      <div class="quiz-progress"><span id="qProgress"></span><span id="qScoreLive"></span></div>
      <p class="quiz-prompt" id="qPrompt"></p>
      <div class="quiz-choices" id="qChoices"></div>
      <p class="quiz-feedback" id="qFeedback" aria-live="polite"></p>
      <button id="qNextBtn" class="primary" hidden>次の問題へ</button>
    </div>
    <div class="quiz-result" id="quizResult" hidden>
      <h2>結果</h2>
      <p class="result-score" id="resultScore"></p>
      <ul class="result-list" id="resultList"></ul>
      <div class="quiz-actions">
        <button id="retryBtn" class="primary">もう一度挑戦</button>
        <button id="backBtn" class="secondary">設定に戻る</button>
      </div>
    </div>
  `;

  const eraGroup = root.querySelector('#quizEraGroup');
  const eraChecks = [];
  const allLabel = document.createElement('label');
  const allInput = document.createElement('input');
  allInput.type = 'checkbox'; allInput.checked = true; allInput.id = 'eraAll';
  allLabel.append(allInput, 'すべて');
  eraGroup.appendChild(allLabel);
  for (const era of ERAS) {
    const label = document.createElement('label');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = true;
    input.dataset.era = era.id;
    input.addEventListener('change', () => {
      allInput.checked = eraChecks.every(c => c.checked);
    });
    eraChecks.push(input);
    label.append(input, era.label);
    eraGroup.appendChild(label);
  }
  allInput.addEventListener('change', () => {
    for (const c of eraChecks) c.checked = allInput.checked;
  });

  function selectedEras() {
    return new Set(eraChecks.filter(c => c.checked).map(c => c.dataset.era));
  }

  const setupEl = root.querySelector('#quizSetup');
  const playEl = root.querySelector('#quizPlay');
  const resultEl = root.querySelector('#quizResult');
  const statsEl = root.querySelector('#quizStats');

  function renderStats() {
    const stats = loadStats();
    const entries = Object.values(stats);
    const totalSeen = entries.reduce((a, s) => a + s.seen, 0);
    const totalCorrect = entries.reduce((a, s) => a + s.correct, 0);
    const weakCount = Object.entries(stats).filter(([, s]) => s.wrong > 0 && s.box <= 2).length;
    const history = loadHistory();
    const lastLine = history.length
      ? `直近: ${history[history.length - 1].score}/${history[history.length - 1].total}問正解 (${new Date(history[history.length - 1].date).toLocaleDateString('ja-JP')})`
      : 'まだ記録がありません';
    statsEl.innerHTML = `
      <div class="stat-row"><span>累計解答数</span><b>${totalSeen}問</b></div>
      <div class="stat-row"><span>累計正答率</span><b>${totalSeen ? Math.round((totalCorrect / totalSeen) * 100) : 0}%</b></div>
      <div class="stat-row"><span>復習が必要な項目</span><b>${weakCount}件</b></div>
      <div class="stat-row muted">${lastLine}</div>
    `;
  }
  renderStats();

  let session = null; // { mode, questions, idx, score, wrongList }

  function poolByEra() {
    const eras = selectedEras();
    return EVENTS.filter(e => eras.has(eraOf(e.year)));
  }

  function startSession(pool, mode) {
    if (pool.length < 4) pool = EVENTS; // 選択範囲が狭すぎる場合は全体から
    const targets = sample(pool, Math.min(QUESTIONS_PER_ROUND, pool.length));
    const questions = targets.map(ev => buildQuestion(mode === 'mix' ? sample(['year', 'pref', 'event'], 1)[0] : mode, ev, EVENTS));
    session = { questions, idx: 0, score: 0, wrongList: [] };
    setupEl.hidden = true;
    resultEl.hidden = true;
    playEl.hidden = false;
    renderQuestion();
  }

  root.querySelector('#startQuizBtn').addEventListener('click', () => {
    const mode = root.querySelector('input[name="qmode"]:checked').value;
    startSession(poolByEra(), mode);
  });

  root.querySelector('#reviewQuizBtn').addEventListener('click', () => {
    const stats = loadStats();
    const weakIds = Object.entries(stats)
      .filter(([, s]) => s.wrong > 0 && s.box <= 3)
      .sort((a, b) => a[1].box - b[1].box)
      .map(([id]) => id);
    let pool = EVENTS.filter(e => weakIds.includes(e.id));
    if (pool.length < 4) {
      const rest = EVENTS.filter(e => !weakIds.includes(e.id));
      pool = [...pool, ...sample(rest, 8 - pool.length)];
    }
    const mode = root.querySelector('input[name="qmode"]:checked').value;
    startSession(pool, mode);
  });

  const progressEl = root.querySelector('#qProgress');
  const scoreLiveEl = root.querySelector('#qScoreLive');
  const promptEl = root.querySelector('#qPrompt');
  const choicesEl = root.querySelector('#qChoices');
  const feedbackEl = root.querySelector('#qFeedback');
  const nextBtn = root.querySelector('#qNextBtn');

  function renderQuestion() {
    const q = session.questions[session.idx];
    progressEl.textContent = `第${session.idx + 1}問 / 全${session.questions.length}問`;
    scoreLiveEl.textContent = `正解 ${session.score}`;
    promptEl.textContent = q.prompt;
    feedbackEl.textContent = '';
    feedbackEl.className = 'quiz-feedback';
    nextBtn.hidden = true;
    choicesEl.innerHTML = '';
    for (const choice of q.choices) {
      const btn = document.createElement('button');
      btn.className = 'choice-btn';
      btn.textContent = choice;
      btn.addEventListener('click', () => answer(choice, btn));
      choicesEl.appendChild(btn);
    }
  }

  function answer(choice, btnEl) {
    const q = session.questions[session.idx];
    const correct = String(choice) === String(q.answer);
    const stats = loadStats();
    recordAnswer(stats, q.event.id, correct);
    saveStats(stats);

    for (const btn of choicesEl.querySelectorAll('.choice-btn')) {
      btn.disabled = true;
      if (String(btn.textContent) === String(q.answer)) btn.classList.add('correct');
    }
    if (correct) {
      session.score++;
      btnEl.classList.add('correct');
      feedbackEl.textContent = '正解!';
      feedbackEl.classList.add('is-correct');
    } else {
      btnEl.classList.add('incorrect');
      feedbackEl.textContent = `不正解。正解は「${q.answer}」。${q.event.desc}`;
      feedbackEl.classList.add('is-incorrect');
      session.wrongList.push(q);
    }
    scoreLiveEl.textContent = `正解 ${session.score}`;
    nextBtn.hidden = false;
  }

  nextBtn.addEventListener('click', () => {
    session.idx++;
    if (session.idx >= session.questions.length) {
      finishSession();
    } else {
      renderQuestion();
    }
  });

  function finishSession() {
    playEl.hidden = true;
    resultEl.hidden = false;
    const total = session.questions.length;
    root.querySelector('#resultScore').textContent = `${session.score} / ${total} 問正解`;
    const listEl = root.querySelector('#resultList');
    listEl.innerHTML = '';
    if (session.wrongList.length === 0) {
      listEl.innerHTML = '<li class="result-perfect">全問正解でした!すばらしい!</li>';
    } else {
      for (const q of session.wrongList) {
        const li = document.createElement('li');
        const meta = CATEGORY_META[q.event.cat];
        li.innerHTML = `<b>${q.event.year}年 ${q.event.title}</b>(${q.event.pref}・${meta.label}) — ${q.event.desc}`;
        listEl.appendChild(li);
      }
    }
    const history = loadHistory();
    history.push({ date: Date.now(), score: session.score, total });
    saveHistory(history);
    renderStats();
  }

  root.querySelector('#retryBtn').addEventListener('click', () => {
    const mode = root.querySelector('input[name="qmode"]:checked').value;
    startSession(poolByEra(), mode);
  });
  root.querySelector('#backBtn').addEventListener('click', () => {
    resultEl.hidden = true;
    setupEl.hidden = false;
  });
}
