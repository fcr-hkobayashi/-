/**
 * POST /api/entries  クライアントから送られたメモをKVに保存する(夜のレポート用)
 * GET  /api/entries?date=YYYY-MM-DD  指定日のメモ一覧を返す
 *
 * SYNC_SECRET環境変数を設定した場合、x-sync-secretヘッダが一致しないリクエストは拒否する。
 * (未設定でも動くが、誰でも書き込めてしまうため設定を強く推奨)
 */
const { kvGet, kvSet } = require('../lib/kv');
const { jstDateKey } = require('../lib/date');

function checkAuth(req) {
  const secret = process.env.SYNC_SECRET;
  if (!secret) return true;
  return req.headers['x-sync-secret'] === secret;
}

module.exports = async function handler(req, res) {
  // ハンドラ全体を1つのtry/catchで囲み、想定外の例外でもVercelの汎用500ではなく
  // 実際のエラーメッセージをJSONで返す(デバッグしやすくするため)。
  try {
    if (!checkAuth(req)) {
      res.status(401).json({ error: 'unauthorized' });
      return;
    }

    if (req.method === 'POST') {
      let body = req.body;
      if (typeof body === 'string') {
        try {
          body = JSON.parse(body);
        } catch (e) {
          body = {};
        }
      }
      const { text, category, createdAt } = body || {};
      if (!text || !createdAt) {
        res.status(400).json({ error: 'text and createdAt are required', receivedBody: body });
        return;
      }

      const date = jstDateKey(new Date(createdAt));
      const key = `entries:${date}`;

      const raw = await kvGet(key);
      const list = raw ? JSON.parse(raw) : [];
      const entry = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        text,
        category: category || 'other',
        createdAt,
      };
      list.push(entry);
      await kvSet(key, JSON.stringify(list));
      res.status(200).json({ ok: true, entry });
      return;
    }

    if (req.method === 'GET') {
      const date = (req.query && req.query.date) || jstDateKey(new Date());
      const key = `entries:${date}`;
      const raw = await kvGet(key);
      const list = raw ? JSON.parse(raw) : [];
      res.status(200).json({ date, entries: list });
      return;
    }

    res.status(405).json({ error: 'method not allowed' });
  } catch (e) {
    console.error('[api/entries] unhandled error:', e);
    res.status(500).json({ error: e.message, name: e.name });
  }
};
