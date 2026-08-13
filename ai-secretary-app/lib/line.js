/**
 * LINE Messaging API でBotの友だち全員(=自分だけ)にブロードキャスト送信する。
 * LINE Notifyは2025年3月末で終了したため、こちらを使う。
 */
async function sendLineBroadcast(text) {
  const token = process.env.LINE_CHANNEL_ACCESS_TOKEN;
  if (!token) throw new Error('LINE_CHANNEL_ACCESS_TOKEN is not set');

  const res = await fetch('https://api.line.me/v2/bot/message/broadcast', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      messages: [{ type: 'text', text: text.slice(0, 4900) }],
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`LINE broadcast failed: ${res.status} ${body.slice(0, 300)}`);
  }
}

module.exports = { sendLineBroadcast };
