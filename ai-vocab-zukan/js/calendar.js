// Googleカレンダー連携 — 9カテゴリ+復習日の学習セッションを自動登録する
(() => {
  'use strict';

  const CLIENT_ID = '979731749526-qvnhd4em0gnpscfpj5hagimk4erntlcn.apps.googleusercontent.com';
  const SCOPE = 'https://www.googleapis.com/auth/calendar.events';
  const STORAGE_KEY = 'aivocab_calendar_setup_v1';
  const DAY_LABELS = ['日', '月', '火', '水', '木', '金', '土'];

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

  let selectedDays = new Set([0, 1, 2, 3, 4, 5, 6]);

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

  if (getSetupState() === 'connected' || getSetupState() === 'dismissed') {
    banner.style.display = 'none';
  }

  connectBtn.addEventListener('click', () => overlay.classList.add('is-open'));
  dismissBtn.addEventListener('click', () => {
    setSetupState('dismissed');
    banner.style.display = 'none';
  });
  modalClose.addEventListener('click', () => overlay.classList.remove('is-open'));
  scrim.addEventListener('click', () => overlay.classList.remove('is-open'));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('is-open')) overlay.classList.remove('is-open');
  });

  function pad(n) { return String(n).padStart(2, '0'); }
  function toLocalIso(date) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`;
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

  const WEEKDAY_LABEL = ['日', '月', '火', '水', '木', '金', '土'];
  function formatResultDate(date) {
    return `${date.getMonth() + 1}/${date.getDate()}(${WEEKDAY_LABEL[date.getDay()]})`;
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
        <span class="result-title">${r.title}</span>
      </li>
    `).join('');

    formView.style.display = 'none';
    resultView.style.display = 'block';
  }

  submitBtn.addEventListener('click', () => {
    if (selectedDays.size === 0) {
      statusEl.textContent = '曜日を1つ以上選んでください。';
      return;
    }
    if (!window.google || !google.accounts || !google.accounts.oauth2) {
      statusEl.textContent = 'Googleログインの準備中です。数秒後にもう一度お試しください。';
      return;
    }
    statusEl.textContent = '';
    submitBtn.disabled = true;
    submitBtn.textContent = '連携中…';

    const tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: CLIENT_ID,
      scope: SCOPE,
      callback: async (response) => {
        if (response.error) {
          statusEl.textContent = '連携がキャンセルされました。もう一度お試しください。';
          submitBtn.disabled = false;
          submitBtn.textContent = 'Googleでログインして予定を作成';
          return;
        }
        try {
          const results = await createCalendarEvents(response.access_token);
          renderResults(results);
          setSetupState('connected');
          banner.style.display = 'none';
        } catch (e) {
          statusEl.textContent = '予定の作成に失敗しました。時間をおいて再度お試しください。';
        } finally {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Googleでログインして予定を作成';
        }
      },
    });
    tokenClient.requestAccessToken();
  });

  resultCloseBtn.addEventListener('click', () => {
    overlay.classList.remove('is-open');
    // 次回開いた時のためにフォーム表示へ戻しておく
    setTimeout(() => {
      resultView.style.display = 'none';
      formView.style.display = 'block';
    }, 300);
  });
})();
