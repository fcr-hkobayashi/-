(function () {
  const { classify, CATEGORY_LABELS, CATEGORY_ORDER } = window.Classifier;
  const Storage = window.Storage;

  // ---------- タブ切り替え ----------
  const tabButtons = document.querySelectorAll('.tab-bar__item');
  const tabPanels = document.querySelectorAll('.tab-panel');

  function activateTab(tabId) {
    tabButtons.forEach((btn) => btn.classList.toggle('is-active', btn.dataset.tab === tabId));
    tabPanels.forEach((panel) => panel.classList.toggle('is-active', panel.id === tabId));
    if (tabId === 'tab-review') renderReview();
  }

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
  });

  // ---------- トースト ----------
  const toastEl = document.getElementById('toast');
  let toastTimer = null;
  function showToast(message) {
    toastEl.textContent = message;
    toastEl.hidden = false;
    toastEl.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.remove('is-visible');
      toastEl.hidden = true;
    }, 2400);
  }

  // ---------- 保存時のフィードバック（音声・バイブ） ----------
  function feedbackOnSave(categoryLabel) {
    const prefs = Storage.loadPrefs();
    if (prefs.vibrate && navigator.vibrate) {
      navigator.vibrate(60);
    }
    if (prefs.voiceFeedback && 'speechSynthesis' in window) {
      const utter = new SpeechSynthesisUtterance(`${categoryLabel}で保存しました`);
      utter.lang = 'ja-JP';
      utter.rate = 1.15;
      speechSynthesis.speak(utter);
    }
  }

  // ---------- メモの保存共通処理 ----------
  function saveMemo(text) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const category = classify(trimmed);
    const entry = Storage.addEntry(trimmed, category);
    const label = CATEGORY_LABELS[category];

    const lastEntryEl = document.getElementById('last-entry');
    document.getElementById('last-entry-category').textContent = label;
    document.getElementById('last-entry-category').className = `chip chip--${category}`;
    document.getElementById('last-entry-text').textContent = entry.text;
    lastEntryEl.hidden = false;

    feedbackOnSave(label);
    window.Sync.syncEntry(entry);
    return entry;
  }

  // ---------- 音声認識 ----------
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  const micButton = document.getElementById('mic-toggle');
  const micStatus = document.getElementById('mic-status');
  const liveText = document.getElementById('live-text');
  let recognition = null;
  let listening = false;

  if (!SpeechRecognitionImpl) {
    document.getElementById('speech-unsupported').hidden = false;
    micButton.disabled = true;
  } else {
    recognition = new SpeechRecognitionImpl();
    recognition.lang = 'ja-JP';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) {
          saveMemo(transcript);
          liveText.textContent = '聞いています…';
        } else {
          interim += transcript;
        }
      }
      if (interim) liveText.textContent = interim;
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      showToast(`音声認識エラー: ${event.error}`);
    };

    recognition.onend = () => {
      // Chromeは無音が続くと自動停止するので、リスニング継続中なら再開する
      if (listening) {
        try {
          recognition.start();
        } catch (e) {
          /* すでに開始中の場合は無視 */
        }
      }
    };
  }

  function startListening() {
    if (!recognition) return;
    listening = true;
    try {
      recognition.start();
    } catch (e) {
      /* 既に開始している場合は無視 */
    }
    micButton.classList.add('is-listening');
    micButton.setAttribute('aria-pressed', 'true');
    micButton.querySelector('.mic-button__label').textContent = '停止する';
    micStatus.textContent = '聞いています… 話しかけてください';
    liveText.textContent = '聞いています…';
  }

  function stopListening() {
    if (!recognition) return;
    listening = false;
    recognition.stop();
    micButton.classList.remove('is-listening');
    micButton.setAttribute('aria-pressed', 'false');
    micButton.querySelector('.mic-button__label').textContent = '話し始める';
    micStatus.textContent = '停止中';
    liveText.textContent = 'ここに認識中の文字が表示されます';
  }

  micButton.addEventListener('click', () => {
    if (listening) stopListening();
    else startListening();
  });

  // ---------- 手入力フォールバック ----------
  document.getElementById('manual-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const textarea = document.getElementById('manual-text');
    const entry = saveMemo(textarea.value);
    if (entry) {
      textarea.value = '';
      showToast('保存しました');
    }
  });

  // ---------- 確認タブ ----------
  const datePicker = document.getElementById('date-picker');

  function todayStr() {
    return Storage.dateKey(new Date());
  }

  datePicker.value = todayStr();

  document.getElementById('date-prev').addEventListener('click', () => {
    shiftDate(-1);
  });
  document.getElementById('date-next').addEventListener('click', () => {
    shiftDate(1);
  });
  datePicker.addEventListener('change', renderReview);

  function shiftDate(delta) {
    const current = new Date(`${datePicker.value}T00:00:00`);
    current.setDate(current.getDate() + delta);
    datePicker.value = Storage.dateKey(current);
    renderReview();
  }

  function buildLocalSummary(entries) {
    const grouped = { work: [], idea: [], task: [], later: [], other: [] };
    entries.forEach((e) => grouped[e.category] ? grouped[e.category].push(e.text) : grouped.other.push(e.text));

    const lines = [];
    lines.push(`・仕事：${grouped.work.length ? grouped.work.join(' / ') : '特になし'}`);
    lines.push(`・新しいアイデア：${grouped.idea.length ? grouped.idea.join(' / ') : '特になし'}`);
    lines.push(`・明日やること：${grouped.task.length ? grouped.task.join(' / ') : '特になし'}`);
    lines.push(`・後で調べること：${grouped.later.length ? grouped.later.join(' / ') : '特になし'}`);
    if (grouped.other.length) lines.push(`・その他：${grouped.other.join(' / ')}`);
    return lines.join('\n');
  }

  function renderReview() {
    const dateStr = datePicker.value || todayStr();
    const entries = Storage.entriesForDate(dateStr).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    const groupsEl = document.getElementById('review-groups');
    const emptyEl = document.getElementById('review-empty');
    groupsEl.innerHTML = '';

    if (!entries.length) {
      emptyEl.hidden = false;
    } else {
      emptyEl.hidden = true;
      CATEGORY_ORDER.forEach((category) => {
        const items = entries.filter((e) => e.category === category);
        if (!items.length) return;
        groupsEl.appendChild(renderGroup(category, items));
      });
    }

    document.getElementById('summary-preview').hidden = true;
    document.getElementById('summary-claude').hidden = !Storage.getClaudeKey();
  }

  function renderGroup(category, items) {
    const section = document.createElement('div');
    section.className = 'review-group';

    const heading = document.createElement('h3');
    heading.className = `review-group__title chip chip--${category}`;
    heading.textContent = `${CATEGORY_LABELS[category]}（${items.length}）`;
    section.appendChild(heading);

    const list = document.createElement('ul');
    list.className = 'review-list';

    items.forEach((entry) => {
      const li = document.createElement('li');
      li.className = 'review-item';
      if (entry.done) li.classList.add('is-done');

      if (category === 'task') {
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = !!entry.done;
        checkbox.addEventListener('change', () => {
          Storage.updateEntry(entry.id, { done: checkbox.checked });
          renderReview();
        });
        li.appendChild(checkbox);
      }

      const textSpan = document.createElement('span');
      textSpan.className = 'review-item__text';
      textSpan.textContent = entry.text;
      li.appendChild(textSpan);

      const timeSpan = document.createElement('span');
      timeSpan.className = 'review-item__time';
      timeSpan.textContent = new Date(entry.createdAt).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
      li.appendChild(timeSpan);

      const categorySelect = document.createElement('select');
      categorySelect.className = 'review-item__category-select';
      CATEGORY_ORDER.forEach((cat) => {
        const opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = CATEGORY_LABELS[cat];
        if (cat === entry.category) opt.selected = true;
        categorySelect.appendChild(opt);
      });
      categorySelect.addEventListener('change', () => {
        Storage.updateEntry(entry.id, { category: categorySelect.value });
        renderReview();
      });
      li.appendChild(categorySelect);

      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn-icon';
      deleteBtn.setAttribute('aria-label', '削除');
      deleteBtn.textContent = '×';
      deleteBtn.addEventListener('click', () => {
        Storage.deleteEntry(entry.id);
        renderReview();
      });
      li.appendChild(deleteBtn);

      list.appendChild(li);
    });

    section.appendChild(list);
    return section;
  }

  document.getElementById('summary-copy').addEventListener('click', async () => {
    const dateStr = datePicker.value || todayStr();
    const entries = Storage.entriesForDate(dateStr);
    const summary = buildLocalSummary(entries);
    const previewEl = document.getElementById('summary-preview');
    previewEl.textContent = summary;
    previewEl.hidden = false;
    try {
      await navigator.clipboard.writeText(summary);
      showToast('コピーしました');
    } catch (e) {
      showToast('コピーに失敗しました。下のテキストを手動でコピーしてください');
    }
  });

  document.getElementById('summary-claude').addEventListener('click', async () => {
    const dateStr = datePicker.value || todayStr();
    const entries = Storage.entriesForDate(dateStr);
    const previewEl = document.getElementById('summary-preview');
    const btn = document.getElementById('summary-claude');
    const key = Storage.getClaudeKey();

    btn.disabled = true;
    btn.textContent = '要約中…';
    try {
      const summary = await window.ClaudeClient.summarizeWithClaude(key, entries);
      previewEl.textContent = summary;
      previewEl.hidden = false;
      try {
        await navigator.clipboard.writeText(summary);
        showToast('Claudeの要約をコピーしました');
      } catch (e) {
        showToast('要約を生成しました（コピーは手動で）');
      }
    } catch (e) {
      showToast(e.message || '要約に失敗しました');
    } finally {
      btn.disabled = false;
      btn.textContent = '✨ Claudeで要約する';
    }
  });

  // ---------- 設定タブ ----------
  const prefs = Storage.loadPrefs();
  document.getElementById('voice-feedback-toggle').checked = prefs.voiceFeedback;
  document.getElementById('vibrate-toggle').checked = prefs.vibrate;

  document.getElementById('voice-feedback-toggle').addEventListener('change', (e) => {
    const p = Storage.loadPrefs();
    p.voiceFeedback = e.target.checked;
    Storage.savePrefs(p);
  });
  document.getElementById('vibrate-toggle').addEventListener('change', (e) => {
    const p = Storage.loadPrefs();
    p.vibrate = e.target.checked;
    Storage.savePrefs(p);
  });

  const claudeKeyInput = document.getElementById('claude-key-input');
  const claudeKeyStatus = document.getElementById('claude-key-status');

  function refreshClaudeKeyStatus() {
    claudeKeyStatus.textContent = Storage.getClaudeKey() ? '✅ キーが設定されています' : 'キーは未設定です';
  }
  refreshClaudeKeyStatus();

  document.getElementById('claude-key-save').addEventListener('click', () => {
    Storage.setClaudeKey(claudeKeyInput.value.trim());
    claudeKeyInput.value = '';
    refreshClaudeKeyStatus();
    showToast('保存しました');
  });

  document.getElementById('claude-key-clear').addEventListener('click', () => {
    Storage.setClaudeKey('');
    refreshClaudeKeyStatus();
    showToast('キーを削除しました');
  });

  const syncSecretInput = document.getElementById('sync-secret-input');
  const syncSecretStatus = document.getElementById('sync-secret-status');

  function refreshSyncSecretStatus() {
    syncSecretStatus.textContent = window.Sync.getSyncSecret()
      ? '✅ 設定済み（保存のたびにサーバーへ同期されます）'
      : '未設定です（サーバー同期・LINEレポートは動きません）';
  }
  refreshSyncSecretStatus();

  document.getElementById('sync-secret-save').addEventListener('click', () => {
    window.Sync.setSyncSecret(syncSecretInput.value.trim());
    syncSecretInput.value = '';
    refreshSyncSecretStatus();
    showToast('保存しました');
  });

  document.getElementById('sync-secret-clear').addEventListener('click', () => {
    window.Sync.setSyncSecret('');
    refreshSyncSecretStatus();
    showToast('解除しました');
  });

  document.getElementById('clear-all-data').addEventListener('click', () => {
    if (confirm('すべてのメモを削除します。よろしいですか？')) {
      Storage.clearAll();
      showToast('削除しました');
      renderReview();
    }
  });

  // 初期表示
  renderReview();
})();
