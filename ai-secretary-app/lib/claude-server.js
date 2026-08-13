/**
 * サーバー側(Cronジョブ)からClaude APIを呼んで要約を作る。
 * ブラウザ側の js/claude.js とは別実装(こちらはANTHROPIC_API_KEY環境変数を使う)。
 */
const MODEL = 'claude-sonnet-5';

const CATEGORY_LABELS = {
  work: '仕事',
  idea: '新しいアイデア',
  task: '明日やること',
  later: '後で調べること',
  other: 'その他',
};

function buildPrompt(entries) {
  const lines = entries
    .map((e) => `- [${CATEGORY_LABELS[e.category] || 'その他'}] ${e.text}`)
    .join('\n');

  return [
    '以下は運転中に音声で残したメモです。内容を「仕事」「新しいアイデア」「明日やること」「後で調べること」の4分類に整理し、',
    '各分類ごとに簡潔な日本語の箇条書きでまとめてください。似た内容はまとめ、重複は削ってください。',
    '該当するメモがない分類は「特になし」としてください。',
    '出力は次のフォーマットだけを厳守してください（前置きや説明は不要）:',
    '・仕事：...',
    '・新しいアイデア：...',
    '・明日やること：...',
    '・後で調べること：...',
    '',
    'メモ一覧:',
    lines,
  ].join('\n');
}

async function summarizeEntries(entries) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY is not set');

  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1024,
      messages: [{ role: 'user', content: buildPrompt(entries) }],
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Claude API error: ${res.status} ${body.slice(0, 300)}`);
  }

  const data = await res.json();
  const text = (data.content || []).map((b) => b.text || '').join('').trim();
  if (!text) throw new Error('Claude returned empty response');
  return text;
}

module.exports = { summarizeEntries, CATEGORY_LABELS };
