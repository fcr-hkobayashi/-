/**
 * Claude API を使った任意の要約機能。
 * キーが未設定でも動くように、呼び出し側は必ずフォールバックを持つこと。
 */
(function () {
  const MODEL = 'claude-sonnet-5';
  const CATEGORY_LINES = [
    ['work', '仕事'],
    ['idea', '新しいアイデア'],
    ['task', '明日やること'],
    ['later', '後で調べること'],
  ];

  async function summarizeWithClaude(apiKey, entries) {
    if (!apiKey) throw new Error('APIキーが設定されていません');
    if (!entries.length) throw new Error('この日のメモがありません');

    const lines = entries
      .map((e) => `- [${window.Classifier.CATEGORY_LABELS[e.category] || 'その他'}] ${e.text}`)
      .join('\n');

    const prompt = [
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

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 1024,
        messages: [{ role: 'user', content: prompt }],
      }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`Claude API エラー (${res.status}) ${body.slice(0, 200)}`);
    }

    const data = await res.json();
    const text = (data.content || []).map((b) => b.text || '').join('').trim();
    if (!text) throw new Error('Claudeから空の応答が返りました');
    return text;
  }

  window.ClaudeClient = { summarizeWithClaude, CATEGORY_LINES };
})();
