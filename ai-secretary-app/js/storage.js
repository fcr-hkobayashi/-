/**
 * localStorage を使った永続化。すべてこの端末のブラウザ内だけに保存する。
 */
(function () {
  const ENTRIES_KEY = 'aisecretary:entries';
  const CLAUDE_KEY = 'aisecretary:claude-key';
  const PREFS_KEY = 'aisecretary:prefs';

  function loadEntries() {
    try {
      return JSON.parse(localStorage.getItem(ENTRIES_KEY) || '[]');
    } catch (e) {
      return [];
    }
  }

  function saveEntries(entries) {
    localStorage.setItem(ENTRIES_KEY, JSON.stringify(entries));
  }

  function addEntry(text, category) {
    const entries = loadEntries();
    const entry = {
      id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)),
      text,
      category,
      done: false,
      createdAt: new Date().toISOString(),
    };
    entries.push(entry);
    saveEntries(entries);
    return entry;
  }

  function updateEntry(id, patch) {
    const entries = loadEntries();
    const idx = entries.findIndex((e) => e.id === id);
    if (idx === -1) return null;
    entries[idx] = Object.assign({}, entries[idx], patch);
    saveEntries(entries);
    return entries[idx];
  }

  function deleteEntry(id) {
    const entries = loadEntries().filter((e) => e.id !== id);
    saveEntries(entries);
  }

  function clearAll() {
    localStorage.removeItem(ENTRIES_KEY);
  }

  // ローカルタイムゾーンでの日付キー（YYYY-MM-DD）。toISOString だとUTCにずれるので使わない。
  function dateKey(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function entriesForDate(dateStr) {
    return loadEntries().filter((e) => dateKey(new Date(e.createdAt)) === dateStr);
  }

  function getClaudeKey() {
    return localStorage.getItem(CLAUDE_KEY) || '';
  }

  function setClaudeKey(key) {
    if (key) localStorage.setItem(CLAUDE_KEY, key);
    else localStorage.removeItem(CLAUDE_KEY);
  }

  function loadPrefs() {
    try {
      return Object.assign({ voiceFeedback: true, vibrate: true }, JSON.parse(localStorage.getItem(PREFS_KEY) || '{}'));
    } catch (e) {
      return { voiceFeedback: true, vibrate: true };
    }
  }

  function savePrefs(prefs) {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  }

  window.Storage = {
    loadEntries,
    saveEntries,
    addEntry,
    updateEntry,
    deleteEntry,
    clearAll,
    dateKey,
    entriesForDate,
    getClaudeKey,
    setClaudeKey,
    loadPrefs,
    savePrefs,
  };
})();
