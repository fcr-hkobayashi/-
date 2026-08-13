/**
 * Vercel Storage (Upstash Redis) の REST API を薄くラップしたヘルパー。
 * KV_REST_API_URL / KV_REST_API_TOKEN は Storage をプロジェクトに接続すると自動で設定される。
 */
const KV_URL = process.env.KV_REST_API_URL;
const KV_TOKEN = process.env.KV_REST_API_TOKEN;

function assertConfigured() {
  if (!KV_URL || !KV_TOKEN) {
    throw new Error('KVが未設定です。Vercelの「ストレージ」からデータベースを作成しプロジェクトに接続してください。');
  }
}

async function kvGet(key) {
  assertConfigured();
  const res = await fetch(`${KV_URL}/get/${encodeURIComponent(key)}`, {
    headers: { Authorization: `Bearer ${KV_TOKEN}` },
  });
  if (!res.ok) throw new Error(`KV get failed: ${res.status}`);
  const data = await res.json();
  return data.result ?? null;
}

async function kvSet(key, value) {
  assertConfigured();
  const res = await fetch(`${KV_URL}/set/${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${KV_TOKEN}` },
    body: value,
  });
  if (!res.ok) throw new Error(`KV set failed: ${res.status}`);
}

module.exports = { kvGet, kvSet };
