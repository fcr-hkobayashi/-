/**
 * メモ保存時にサーバー(/api/entries)へバックグラウンド同期する。
 * 失敗してもこの端末のlocalStorageには残っているので致命的ではないが、
 * 夜のLINEレポートにはその1件が反映されない可能性がある。
 */
(function () {
  const SECRET_KEY = 'aisecretary:sync-secret';

  function getSyncSecret() {
    return localStorage.getItem(SECRET_KEY) || '';
  }

  function setSyncSecret(value) {
    if (value) localStorage.setItem(SECRET_KEY, value);
    else localStorage.removeItem(SECRET_KEY);
  }

  function syncEntry(entry) {
    const secret = getSyncSecret();
    const headers = { 'content-type': 'application/json' };
    if (secret) headers['x-sync-secret'] = secret;

    fetch('/api/entries', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        text: entry.text,
        category: entry.category,
        createdAt: entry.createdAt,
      }),
    }).catch(() => {
      /* オフライン等での失敗は無視する */
    });
  }

  window.Sync = { getSyncSecret, setSyncSecret, syncEntry };
})();
