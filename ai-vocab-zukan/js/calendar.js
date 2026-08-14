// Googleカレンダー連携 — 9カテゴリ+復習日の学習セッションを自動登録する
(() => {
  'use strict';

  const CLIENT_ID = '979731749526-qvnhd4em0gnpscfpj5hagimk4erntlcn.apps.googleusercontent.com';
  const SCOPE = 'https://www.googleapis.com/auth/calendar.events';
  const STORAGE_KEY = 'aivocab_calendar_setup_v1';
  const EVENT_SOURCE_TAG = 'ai-vocab-zukan';
  const DAY_LABELS = ['日', '月', '火', '水', '木', '金', '土'];

  // --- バナー・セットアップモーダル ---
  const banner = document.getElementById('calendar-banner');
  const connectBtn = document.getElementById('calendar-connect-btn');
  const dismissBtn = document.getElementById('calendar-dismiss-btn');
  const overlay = document.getElementById('calendar-overlay');
  const scrim = document.getElementById('calendar-scrim');
  const modalClose = document.getElementById('calendar-modal-close');
  const timeInput = document.getElementById('calendar-time-input');
  const presetBtns = document.querySelectorAll('.day-preset-btn');
  const dayChecksWrap = document.getElementById('calendar-day-checks');
  const submitBtn = document.getElementById('calendar-submit-btn');
  const statusEl = document.getElementById('calendar-modal-status');
  const formView = document.getElementById('calendar-form-view');
  const resultView = document.getElementById('calendar-result-view');
  const resultSummary = document.getElementById('calendar-result-summary');
  const resultList = document.getElementById('calendar-result-list');
  const resultCloseBtn = document.getElementById('calendar-result-close');

  // --- カレンダータブ ---
  const statusCard = document.getElementById('calendar-status-card');
  const upcomingHeading = document.getElementById('calendar-upcoming-heading');
  const upcomingList = document.getElementById('calendar-upcoming-list');

  let selectedDays = new Set([0, 1, 2, 3, 4, 5, 6]);

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function renderDayChecks() {
    dayChecksWrap.innerHTML = DAY_LABELS.map((label, i) => `
      <label class="day-check">
        <input type="checkbox" value="${i}" ${selectedDays.has(i) ? 'checked' : ''}>
        <span>${label}</span>
      </label>
    `).join('');
    dayChecksWrap.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => {
        const v = Number(cb.value);
        if (cb.checked) selectedDays.add(v); else selectedDays.delete(v);
      });
    });
  }

  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      presetBtns.forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      const preset = btn.dataset.preset;
      if (preset === 'everyday') {
        selectedDays = new Set([0, 1, 2, 3, 4, 5, 6]);
        dayChecksWrap.style.display = 'none';
      } else if (preset === 'weekday') {
        selectedDays = new Set([1, 2, 3, 4, 5]);
        dayChecksWrap.style.display = 'none';
      } else {
        dayChecksWrap.style.display = 'flex';
        renderDayChecks();
      }
    });
  });

  function getSetupState() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }
  function setSetupState(v) {
    try { localStorage.setItem(STORAGE_KEY, v); } catch (e) {}
  }

  function openSetupModal() {
    overlay.classList.add('is-open');
  }

  if (getSetupState() === 'connected' || getSetupState() === 'dismissed') {
    banner.style.display = 'none';
  }

  connectBtn.addEventListener('click', openSetupModal);
  dismissBtn.addEventListener('click', () => {
    setSetupState('dismissed');
    banner.style.display = 'none';
  });
  modalClose.addEventListener('click', () => overlay.classList.remove('is-open'));
  scrim.addEventListener('click', () => overlay.classList.remove('is-open'));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('is-open')) overlay.classList.remove('is-open');
  });

  // --- 共通: OAuthトークン取得 ---
  // 呼び出しのたびに新しいtokenClientを作る（サイレント試行の直後に対話的リクエストを
  // 投げるなど、同じクライアントを使い回すとGoogle側の内部状態が噛み合わず応答が返って
  // こなくなることがあるための対策）。タイムアウトも必ず設定し、画面が固まったままに
  // ならないようにする。
  function isGsiReady() {
    return !!(window.google && google.accounts && google.accounts.oauth2);
  }

  function requestToken({ interactive, timeoutMs = 15000 }) {
    return new Promise((resolve, reject) => {
      if (!isGsiReady()) {
        reject(new Error('Googleログインスクリプトの読み込みが完了していません'));
        return;
      }
      let settled = false;
      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        reject(new Error('応答がありませんでした(タイムアウト)。ポップアップがブロックされていないか確認してください'));
      }, timeoutMs);

      const tc = google.accounts.oauth2.initTokenClient({
        client_id: CLIENT_ID,
        scope: SCOPE,
        callback: (resp) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          if (resp.error) reject(resp);
          else resolve(resp.access_token);
        },
      });
      tc.requestAccessToken(interactive ? {} : { prompt: '' });
    });
  }

  function pad(n) { return String(n).padStart(2, '0'); }
  function toLocalIso(date) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`;
  }
  const WEEKDAY_LABEL = ['日', '月', '火', '水', '木', '金', '土'];
  function formatResultDate(date) {
    return `${date.getMonth() + 1}/${date.getDate()}(${WEEKDAY_LABEL[date.getDay()]})`;
  }

  function computeSessionDates(count, timeStr) {
    const [h, m] = timeStr.split(':').map(Number);
    const dates = [];
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(h, m, 0, 0);
    let guard = 0;
    while (dates.length < count && guard < 60) {
      if (selectedDays.has(d.getDay())) dates.push(new Date(d));
      d.setDate(d.getDate() + 1);
      guard++;
    }
    return dates;
  }

  function buildSessions() {
    const sessions = CATEGORIES.map(cat => {
      const count = TERMS.filter(t => t.category === cat.id).length;
      return {
        summary: `AI用語ずかん ${cat.emoji} ${cat.name}（${count}語）`,
        description: `AI用語ずかんで「${cat.name}」を学習する日です。アプリを開いてカテゴリチップで絞り込み、図鑑タブでカードをめくって覚えましょう。\n${location.href}`,
      };
    });
    sessions.push({
      summary: 'AI用語ずかん ✏️ 総復習クイズDay',
      description: `これまでの9カテゴリを振り返るクイズDay。クイズタブで全カテゴリからランダム出題に挑戦しましょう。\n${location.href}`,
    });
    return sessions;
  }

  async function createCalendarEvents(accessToken) {
    const sessions = buildSessions();
    const dates = computeSessionDates(sessions.length, timeInput.value || '20:00');
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    const results = [];
    for (let i = 0; i < sessions.length; i++) {
      const start = dates[i];
      const end = new Date(start.getTime() + 30 * 60000);
      const body = {
        summary: sessions[i].summary,
        description: sessions[i].description,
        start: { dateTime: toLocalIso(start), timeZone },
        end: { dateTime: toLocalIso(end), timeZone },
        reminders: { useDefault: false, overrides: [{ method: 'popup', minutes: 10 }] },
        extendedProperties: { private: { source: EVENT_SOURCE_TAG } },
      };
      let ok = false;
      let htmlLink = null;
      try {
        const res = await fetch('https://www.googleapis.com/calendar/v3/calendars/primary/events', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        });
        ok = res.ok;
        if (ok) {
          const json = await res.json();
          htmlLink = json.htmlLink || null;
        }
      } catch (e) {
        ok = false;
      }
      results.push({ date: start, title: sessions[i].summary, ok, htmlLink });
    }
    return results;
  }

  function renderResults(results) {
    const okCount = results.filter(r => r.ok).length;
    resultSummary.textContent = `${results[0] ? formatResultDate(results[0].date) : ''}〜${results[results.length - 1] ? formatResultDate(results[results.length - 1].date) : ''}の期間で、${okCount}/${results.length}件をカレンダーに登録しました。`;

    resultList.innerHTML = results.map(r => `
      <li class="calendar-result-item${r.ok ? '' : ' is-failed'}">
        <span class="result-status">${r.ok ? '✅' : '⚠️'}</span>
        <span class="result-date">${formatResultDate(r.date)}</span>
        <span class="result-title">${escapeHtml(r.title)}</span>
      </li>
    `).join('');

    formView.style.display = 'none';
    resultView.style.display = 'block';
  }

  submitBtn.addEventListener('click', async () => {
    if (selectedDays.size === 0) {
      statusEl.textContent = '曜日を1つ以上選んでください。';
      return;
    }
    if (!isGsiReady()) {
      statusEl.textContent = 'Googleログインの準備中です。数秒後にもう一度お試しください。';
      return;
    }
    statusEl.textContent = '';
    submitBtn.disabled = true;
    submitBtn.textContent = '連携中…';

    try {
      const accessToken = await requestToken({ interactive: true });
      const results = await createCalendarEvents(accessToken);
      renderResults(results);
      setSetupState('connected');
      banner.style.display = 'none';
      renderStatusCard();
    } catch (e) {
      statusEl.textContent = '連携がキャンセルされたか、予定の作成に失敗しました。もう一度お試しください。';
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Googleでログインして予定を作成';
    }
  });

  resultCloseBtn.addEventListener('click', () => {
    overlay.classList.remove('is-open');
    // 次回開いた時のためにフォーム表示へ戻しておく
    setTimeout(() => {
      resultView.style.display = 'none';
      formView.style.display = 'block';
    }, 300);
  });

  // --- カレンダータブ: 連携状態・今後の予定 ---
  function renderStatusCard() {
    const connected = getSetupState() === 'connected';
    if (connected) {
      statusCard.innerHTML = `
        <div class="calendar-status connected">
          <span class="status-dot"></span>
          <div>
            <strong>✅ Googleカレンダーと連携済み</strong>
            <p>下のボタンを押すと、実際にカレンダーへ登録されている予定をここに表示します。</p>
          </div>
        </div>
        <div class="calendar-status-actions">
          <button class="btn-calendar" id="calendar-refresh-btn">最新の予定を確認</button>
          <button class="calendar-dismiss-btn" id="calendar-reconnect-btn">スケジュールを作り直す</button>
        </div>
        <p class="calendar-status-note" id="calendar-refresh-note"></p>
      `;
      document.getElementById('calendar-refresh-btn').addEventListener('click', () => refreshUpcoming(true));
      document.getElementById('calendar-reconnect-btn').addEventListener('click', openSetupModal);
      refreshUpcoming(false);
    } else {
      statusCard.innerHTML = `
        <div class="calendar-status disconnected">
          <span class="status-dot"></span>
          <div>
            <strong>🔌 まだ連携していません</strong>
            <p>連携すると、9カテゴリ＋復習日の学習予定が自動でGoogleカレンダーに登録されます。</p>
          </div>
        </div>
        <div class="calendar-status-actions">
          <button class="btn-calendar" id="calendar-open-setup-btn">連携する</button>
        </div>
      `;
      document.getElementById('calendar-open-setup-btn').addEventListener('click', openSetupModal);
      upcomingHeading.style.display = 'none';
      upcomingList.innerHTML = '';
    }
  }

  async function refreshUpcoming(interactive) {
    const noteEl = document.getElementById('calendar-refresh-note');
    const refreshBtn = document.getElementById('calendar-refresh-btn');
    if (noteEl) noteEl.textContent = '確認中…';
    if (refreshBtn) refreshBtn.disabled = true;

    try {
      if (!isGsiReady()) throw new Error('Googleログインの準備ができていません(スクリプト未読み込み)');
      let accessToken;
      try {
        accessToken = await requestToken({ interactive, timeoutMs: interactive ? 15000 : 6000 });
      } catch (tokenErr) {
        const reason = (tokenErr && (tokenErr.error || tokenErr.message)) || '不明なエラー';
        throw new Error(`ログインに失敗: ${reason}`);
      }
      const items = await fetchUpcomingEvents(accessToken);
      renderUpcoming(items);
      if (noteEl) noteEl.textContent = `最終確認: たった今`;
    } catch (e) {
      console.error('[AI用語ずかん] カレンダー取得エラー:', e);
      if (!interactive) {
        // サイレント取得の失敗は無言で諦める（毎回ログイン要求すると煩わしいため）
        if (noteEl) noteEl.textContent = '「最新の予定を確認」を押すと表示されます。';
      } else {
        if (noteEl) noteEl.textContent = `取得に失敗しました: ${e.message || e}`;
      }
    } finally {
      if (refreshBtn) refreshBtn.disabled = false;
    }
  }

  async function fetchUpcomingEvents(accessToken) {
    const params = new URLSearchParams({
      privateExtendedProperty: `source=${EVENT_SOURCE_TAG}`,
      timeMin: new Date().toISOString(),
      orderBy: 'startTime',
      singleEvents: 'true',
      maxResults: '10',
    });
    const res = await fetch(`https://www.googleapis.com/calendar/v3/calendars/primary/events?${params}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.error && errJson.error.message) detail += ` ${errJson.error.message}`;
      } catch (e) { /* ignore */ }
      throw new Error(detail);
    }
    const json = await res.json();
    return json.items || [];
  }

  function renderUpcoming(items) {
    if (!items.length) {
      upcomingHeading.style.display = 'none';
      upcomingList.innerHTML = '<p class="calendar-empty-note">今後の予定は見つかりませんでした。</p>';
      return;
    }
    upcomingHeading.style.display = 'block';
    upcomingList.innerHTML = `<ul class="calendar-result-list">${items.map(ev => {
      const start = new Date(ev.start.dateTime || ev.start.date);
      return `
        <li>
          <a class="calendar-result-item" href="${ev.htmlLink}" target="_blank" rel="noopener">
            <span class="result-status">📅</span>
            <span class="result-date">${formatResultDate(start)}</span>
            <span class="result-title">${escapeHtml(ev.summary || '')}</span>
          </a>
        </li>
      `;
    }).join('')}</ul>`;
  }

  const calendarTabBtn = document.querySelector('.tab-btn[data-tab="calendar"]');
  if (calendarTabBtn) {
    calendarTabBtn.addEventListener('click', renderStatusCard);
  }
})();
