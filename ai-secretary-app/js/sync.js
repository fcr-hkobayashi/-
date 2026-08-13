/**
 * メモ保存時にサーバー(/api/entries)へバックグラウンド同期する。
 * 失敗してもこの端末のlocalStorageには残っているので致命的ではないが、
 * 夜のLINEレポートにはその1件が反映されない可能性がある。
 */
(function () {
  const SECRET_KEY = 'aisecretary:sync-secret';
  let onSyncError = null;

  function getSyncSecret() {
    return localStorage.getItem(SECRET_KEY) || '';
  }

  function setSyncSecret(value) {
    if (value) localStorage.setItem(SECRET_KEY, value);
    else localStorage.removeItem(SECRET_KEY);
  }

  function setSyncErrorHandler(fn) {
    onSyncError = fn;
  }

  function reportError(message) {
    console.error('[Sync]', message);
    if (onSyncError) onSyncError(message);
  }

  function syncEntry(entry) {
    const secret = getSyncSecret();
    if (!secret) return; // 同期を設定していない場合は何もしない(今まで通りローカルのみ)

    fetch('/api/entries', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-sync-secret': secret },
      body: JSON.stringify({
        text: entry.text,
        category: entry.category,
        createdAt: entry.createdAt,
      }),
    })
      .then((res) => {
        if (!res.ok) {
          return res.text().then((body) => {
            reportError(`⚠️ サーバー同期に失敗しました (${res.status})`);
            console.error('[Sync] response body:', body);
          });
        }
      })
      .catch((e) => {
        reportError('⚠️ サーバー同期に失敗しました(通信エラー)');
        console.error('[Sync] fetch error:', e);
      });
  }

  window.Sync = { getSyncSecret, setSyncSecret, setSyncErrorHandler, syncEntry };
})();
