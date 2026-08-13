/**
 * メモ保存時にサーバー(/api/entries)へバックグラウンド同期する。
 * 失敗してもこの端末のlocalStorageには残っているので致命的ではないが、
 * 夜のLINEレポートにはその1件が反映されない可能性がある。
 *
 * 同期用の合言葉はここに固定値として埋め込む(Vercel側のSYNC_SECRET環境変数と
 * 同じ値にすること)。以前はブラウザのlocalStorageに手入力させていたが、
 * デプロイURLが変わるたびに別オリジン扱いになって入力し直しが必要になり
 * 運用上の混乱の元だったため、コードに焼き込む方式に変更した。
 * 個人用ホビーアプリなので、この程度の簡易的な保護で十分という判断。
 */
(function () {
  const HARDCODED_SECRET = '466c50e83cc9ad26f55944a6534859';
  const SECRET_KEY = 'aisecretary:sync-secret';
  let onSyncError = null;

  function getSyncSecret() {
    return localStorage.getItem(SECRET_KEY) || HARDCODED_SECRET;
  }

  function hasCustomOverride() {
    return !!localStorage.getItem(SECRET_KEY);
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
            let detail = body;
            try {
              detail = JSON.parse(body).error || body;
            } catch (e) {
              /* JSONでなければそのまま使う */
            }
            reportError(`⚠️ サーバー同期に失敗 (${res.status}): ${String(detail).slice(0, 80)}`);
            console.error('[Sync] response body:', body);
          });
        }
      })
      .catch((e) => {
        reportError('⚠️ サーバー同期に失敗しました(通信エラー)');
        console.error('[Sync] fetch error:', e);
      });
  }

  window.Sync = { getSyncSecret, setSyncSecret, hasCustomOverride, setSyncErrorHandler, syncEntry };
})();
