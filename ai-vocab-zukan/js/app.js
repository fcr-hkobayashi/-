(() => {
  'use strict';

  const STORAGE_COLLECTED = 'aivocab_collected_v1';
  const STORAGE_BEST_STREAK = 'aivocab_best_streak_v1';
  const STORAGE_LAST_VISIT = 'aivocab_last_visit_v1';
  const STORAGE_DAY_STREAK = 'aivocab_day_streak_v1';

  const catById = Object.fromEntries(CATEGORIES.map(c => [c.id, c]));
  let activeCategory = 'all';
  let searchQuery = '';
  let collected = loadCollected();
  let currentDetailTermId = null;

  // ---------------- storage ----------------
  function loadCollected() {
    try {
      const raw = localStorage.getItem(STORAGE_COLLECTED);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch (e) {
      return new Set();
    }
  }
  function saveCollected() {
    localStorage.setItem(STORAGE_COLLECTED, JSON.stringify([...collected]));
  }
  function loadBestStreak() {
    return Number(localStorage.getItem(STORAGE_BEST_STREAK) || 0);
  }
  function saveBestStreak(v) {
    localStorage.setItem(STORAGE_BEST_STREAK, String(v));
  }

  // ---------------- daily streak ----------------
  function todayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function updateDayStreak() {
    const today = todayKey();
    const lastVisit = localStorage.getItem(STORAGE_LAST_VISIT);
    let streak = Number(localStorage.getItem(STORAGE_DAY_STREAK) || 0);

    if (lastVisit === today) {
      // 今日はすでにカウント済み
    } else if (lastVisit) {
      const diffDays = Math.round((new Date(today) - new Date(lastVisit)) / 86400000);
      streak = diffDays === 1 ? streak + 1 : 1;
    } else {
      streak = 1;
    }

    localStorage.setItem(STORAGE_LAST_VISIT, today);
    localStorage.setItem(STORAGE_DAY_STREAK, String(streak));
    return streak;
  }

  function renderStreakBanner() {
    const streak = updateDayStreak();
    const banner = document.getElementById('streak-banner');
    if (!banner) return;
    if (streak >= 2) {
      banner.classList.add('has-streak');
      banner.innerHTML = `<span class="streak-flame">🔥</span> <strong>${streak}日連続</strong>で学習中！この調子で続けよう`;
    } else {
      banner.classList.remove('has-streak');
      banner.textContent = '📖 今日も1語、学んでいこう！';
    }
  }

  // ---------------- tabs ----------------
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => { b.classList.remove('is-active'); b.setAttribute('aria-selected', 'false'); });
      tabPanels.forEach(p => p.classList.remove('is-active'));
      btn.classList.add('is-active');
      btn.setAttribute('aria-selected', 'true');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('is-active');
      if (btn.dataset.tab === 'quiz' && !quizState.current) nextQuizQuestion();
    });
  });

  // ---------------- category chips ----------------
  const chipRow = document.getElementById('category-chips');
  function renderChips() {
    const frag = document.createDocumentFragment();

    const allChip = document.createElement('button');
    allChip.className = 'chip' + (activeCategory === 'all' ? ' is-active' : '');
    allChip.style.background = activeCategory === 'all' ? '#1f2430' : '';
    allChip.innerHTML = `すべて <span class="chip-count">${TERMS.length}</span>`;
    allChip.addEventListener('click', () => { activeCategory = 'all'; renderChips(); renderGrid(); });
    frag.appendChild(allChip);

    CATEGORIES.forEach(cat => {
      const count = TERMS.filter(t => t.category === cat.id).length;
      const chip = document.createElement('button');
      const isActive = activeCategory === cat.id;
      chip.className = 'chip' + (isActive ? ' is-active' : '');
      if (isActive) chip.style.background = cat.color;
      chip.innerHTML = `${cat.emoji} ${cat.name} <span class="chip-count">${count}</span>`;
      chip.addEventListener('click', () => { activeCategory = cat.id; renderChips(); renderGrid(); });
      frag.appendChild(chip);
    });

    chipRow.innerHTML = '';
    chipRow.appendChild(frag);
  }

  // ---------------- search ----------------
  const searchInput = document.getElementById('term-search');
  const searchClearBtn = document.getElementById('search-clear-btn');

  searchInput.addEventListener('input', () => {
    searchQuery = searchInput.value.trim();
    searchClearBtn.style.display = searchQuery ? 'flex' : 'none';
    renderGrid();
  });
  searchClearBtn.addEventListener('click', () => {
    searchQuery = '';
    searchInput.value = '';
    searchClearBtn.style.display = 'none';
    searchInput.focus();
    renderGrid();
  });

  // ---------------- grid ----------------
  const grid = document.getElementById('card-grid');
  function visibleTerms() {
    let terms = activeCategory === 'all' ? TERMS : TERMS.filter(t => t.category === activeCategory);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      terms = terms.filter(t =>
        t.term.toLowerCase().includes(q) ||
        (t.reading && t.reading.toLowerCase().includes(q)) ||
        t.summary.toLowerCase().includes(q)
      );
    }
    return terms;
  }

  function renderGrid() {
    const terms = visibleTerms();
    grid.innerHTML = '';
    if (terms.length === 0) {
      const noResults = document.createElement('div');
      noResults.className = 'no-results';
      noResults.textContent = searchQuery ? `「${searchQuery}」に一致する用語がありません` : '該当する用語がありません';
      grid.appendChild(noResults);
      return;
    }
    const frag = document.createDocumentFragment();
    terms.forEach(term => {
      const cat = catById[term.category];
      const isCollected = collected.has(term.id);
      const tile = document.createElement('button');
      tile.className = 'stamp-tile' + (isCollected ? ' is-collected' : '');
      if (isCollected) tile.style.boxShadow = `0 0 0 1.5px ${cat.color}33, var(--shadow-card)`;
      tile.innerHTML = `
        <span class="stamp-status"></span>
        <span class="stamp-emoji">${cat.emoji}</span>
        <span class="stamp-term">${term.term}</span>
      `;
      tile.addEventListener('click', () => openDetail(term.id));
      frag.appendChild(tile);
    });
    grid.appendChild(frag);
    updateProgress();
  }

  function updateProgress() {
    document.getElementById('progress-count').textContent = `${collected.size} / ${TERMS.length}`;
    document.getElementById('progress-fill').style.width = `${TERMS.length ? (collected.size / TERMS.length) * 100 : 0}%`;
    document.getElementById('footer-total').textContent = TERMS.length;
  }

  // ---------------- detail flip card ----------------
  const detailOverlay = document.getElementById('detail-overlay');
  const detailCardInner = document.getElementById('detail-card-inner');
  const detailCatBadge = document.getElementById('detail-cat-badge');
  const detailTerm = document.getElementById('detail-term');
  const detailReading = document.getElementById('detail-reading');
  const detailSummary = document.getElementById('detail-summary');
  const detailAnalogy = document.getElementById('detail-analogy');
  const detailExample = document.getElementById('detail-example');
  const detailCollectBtn = document.getElementById('detail-collect');
  const detailSpeakBtn = document.getElementById('detail-speak-btn');

  // ---------------- 音声読み上げ ----------------
  const canSpeak = 'speechSynthesis' in window;
  function speakText(text) {
    if (!canSpeak || !text) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'ja-JP';
    utter.rate = 0.95;
    utter.onstart = () => detailSpeakBtn.classList.add('is-speaking');
    utter.onend = () => detailSpeakBtn.classList.remove('is-speaking');
    utter.onerror = () => detailSpeakBtn.classList.remove('is-speaking');
    window.speechSynthesis.speak(utter);
  }
  if (canSpeak) {
    detailSpeakBtn.addEventListener('click', () => {
      const term = TERMS.find(t => t.id === currentDetailTermId);
      if (term) speakText(term.reading || term.term);
    });
  }

  function openDetail(termId) {
    const term = TERMS.find(t => t.id === termId);
    if (!term) return;
    currentDetailTermId = termId;
    const cat = catById[term.category];

    detailCatBadge.textContent = `${cat.emoji} ${cat.name}`;
    detailCatBadge.style.background = cat.color + '1a';
    detailCatBadge.style.color = cat.color;
    detailTerm.textContent = term.term;
    detailReading.textContent = term.reading ? `読み方: ${term.reading}` : '';
    detailSpeakBtn.style.display = canSpeak ? 'flex' : 'none';
    detailSummary.textContent = term.summary;
    detailAnalogy.textContent = term.analogy;
    detailExample.textContent = term.example;

    updateCollectButton();
    detailCardInner.classList.remove('is-flipped');
    detailOverlay.classList.add('is-open');
  }

  function updateCollectButton() {
    const isCollected = collected.has(currentDetailTermId);
    detailCollectBtn.textContent = isCollected ? '収集済み ✓' : '収集する ✓';
    detailCollectBtn.classList.toggle('is-done', isCollected);
  }

  function closeDetail() {
    detailOverlay.classList.remove('is-open');
    currentDetailTermId = null;
  }

  // tap front area (not the close/speak buttons) to flip to back
  document.querySelector('.flip-face-front').addEventListener('click', (e) => {
    if (e.target.closest('.card-close') || e.target.closest('.speak-btn')) return;
    detailCardInner.classList.add('is-flipped');
  });
  // tap back area (not close/collect buttons) to flip back to front
  document.querySelector('.flip-face-back').addEventListener('click', (e) => {
    if (e.target.closest('.card-close') || e.target.closest('.btn-collect')) return;
    detailCardInner.classList.remove('is-flipped');
  });

  document.getElementById('detail-close').addEventListener('click', closeDetail);
  document.getElementById('detail-close-back').addEventListener('click', closeDetail);
  document.getElementById('detail-scrim').addEventListener('click', closeDetail);

  detailCollectBtn.addEventListener('click', () => {
    if (!currentDetailTermId) return;
    if (collected.has(currentDetailTermId)) {
      collected.delete(currentDetailTermId);
    } else {
      collected.add(currentDetailTermId);
    }
    saveCollected();
    updateCollectButton();
    renderGrid();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && detailOverlay.classList.contains('is-open')) closeDetail();
  });

  // ---------------- quiz ----------------
  const quizState = {
    current: null,
    streak: 0,
    total: 0,
    best: loadBestStreak(),
  };

  const quizTermEl = document.getElementById('quiz-term');
  const quizReadingEl = document.getElementById('quiz-reading');
  const quizChoicesEl = document.getElementById('quiz-choices');
  const quizFeedbackEl = document.getElementById('quiz-feedback');
  const quizNextBtn = document.getElementById('quiz-next');

  function shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function pickQuizTerm() {
    return TERMS[Math.floor(Math.random() * TERMS.length)];
  }

  function buildChoices(correctTerm) {
    const sameCat = TERMS.filter(t => t.category === correctTerm.category && t.id !== correctTerm.id);
    const others = TERMS.filter(t => t.category !== correctTerm.category);
    const distractors = shuffle(sameCat).concat(shuffle(others)).slice(0, 3);
    return shuffle([correctTerm, ...distractors]);
  }

  function nextQuizQuestion() {
    const term = pickQuizTerm();
    quizState.current = term;
    quizTermEl.textContent = term.term;
    quizReadingEl.textContent = term.reading ? `読み方: ${term.reading}` : '';
    quizFeedbackEl.textContent = '';
    quizFeedbackEl.className = 'quiz-feedback';
    quizNextBtn.style.display = 'none';

    const choices = buildChoices(term);
    quizChoicesEl.innerHTML = '';
    choices.forEach(choiceTerm => {
      const btn = document.createElement('button');
      btn.className = 'quiz-choice-btn';
      btn.textContent = choiceTerm.summary;
      btn.addEventListener('click', () => answerQuiz(btn, choiceTerm.id === term.id));
      quizChoicesEl.appendChild(btn);
    });

    updateQuizStats();
  }

  function answerQuiz(clickedBtn, isCorrect) {
    const allBtns = quizChoicesEl.querySelectorAll('.quiz-choice-btn');
    allBtns.forEach(b => b.classList.add('is-disabled'));

    if (isCorrect) {
      clickedBtn.classList.add('is-correct');
      quizState.streak += 1;
      quizFeedbackEl.textContent = '🎉 正解！';
      quizFeedbackEl.classList.add('is-correct');
    } else {
      clickedBtn.classList.add('is-wrong');
      const correctBtn = [...allBtns].find(b => b.textContent === quizState.current.summary);
      if (correctBtn) correctBtn.classList.add('is-correct');
      quizState.streak = 0;
      quizFeedbackEl.textContent = `不正解… 正解は「${quizState.current.term}」でした`;
      quizFeedbackEl.classList.add('is-wrong');
    }
    quizState.total += 1;
    if (quizState.streak > quizState.best) {
      quizState.best = quizState.streak;
      saveBestStreak(quizState.best);
    }
    updateQuizStats();
    quizNextBtn.style.display = 'block';
  }

  function updateQuizStats() {
    document.getElementById('quiz-streak').textContent = quizState.streak;
    document.getElementById('quiz-best').textContent = quizState.best;
    document.getElementById('quiz-total').textContent = quizState.total;
  }

  quizNextBtn.addEventListener('click', nextQuizQuestion);

  // ---------------- init ----------------
  renderStreakBanner();
  renderChips();
  renderGrid();
  updateQuizStats();
})();
