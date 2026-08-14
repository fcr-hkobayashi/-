/**
 * 毎晩20:00(JST)にVercel Cronから呼ばれ、その日のメモをClaudeで要約してLINEに送る。
 * vercel.jsonのcrons設定で "0 11 * * *" (UTC 11:00 = JST 20:00) を指定している。
 *
 * CRON_SECRET環境変数を設定すると、Vercelがcron実行時に自動で
 * Authorization: Bearer <CRON_SECRET> を付けて呼び出すため、外部からの不正な起動を防げる。
 */
const { kvGet } = require('../../lib/kv');
const { jstDateKey } = require('../../lib/date');
const { summarizeEntries, CATEGORY_LABELS } = require('../../lib/claude-server');
const { sendLineBroadcast } = require('../../lib/line');
const { saveDailyPageToNotion } = require('../../lib/notion');

function groupByCategory(entries) {
  const grouped = { work: [], idea: [], task: [], later: [], other: [] };
  entries.forEach((e) => {
    const bucket = grouped[e.category] ? e.category : 'other';
    grouped[bucket].push(e.text);
  });
  return grouped;
}

function summaryFromGrouped(grouped) {
  const lines = [
    `・仕事：${grouped.work.length ? grouped.work.join(' / ') : '特になし'}`,
    `・新しいアイデア：${grouped.idea.length ? grouped.idea.join(' / ') : '特になし'}`,
    `・明日やること：${grouped.task.length ? grouped.task.join(' / ') : '特になし'}`,
    `・後で調べること：${grouped.later.length ? grouped.later.join(' / ') : '特になし'}`,
  ];
  if (grouped.other.length) lines.push(`・その他：${grouped.other.join(' / ')}`);
  return lines.join('\n');
}

module.exports = async function handler(req, res) {
  const cronSecret = process.env.CRON_SECRET;
  if (cronSecret && req.headers['authorization'] !== `Bearer ${cronSecret}`) {
    res.status(401).json({ error: 'unauthorized' });
    return;
  }

  const date = jstDateKey(new Date());
  const key = `entries:${date}`;

  try {
    const raw = await kvGet(key);
    const entries = raw ? JSON.parse(raw) : [];
    const grouped = groupByCategory(entries);

    let message;
    let summary = null;
    if (!entries.length) {
      message = `【AI秘書メモ】${date}\n今日のメモはありませんでした。`;
    } else {
      try {
        summary = await summarizeEntries(entries);
      } catch (e) {
        // Claudeが失敗しても、簡易版のまとめで必ず何か送る
        summary = summaryFromGrouped(grouped);
      }
      message = `【AI秘書メモ】${date}の振り返り\n\n${summary}`;
    }

    await sendLineBroadcast(message);

    // Notion保存は独立した処理として扱う。失敗してもLINE送信は既に成功しているので、
    // ここでエラーを投げてユーザーへの通知自体を止めない。
    let notionStatus = 'skipped (no entries)';
    if (entries.length && process.env.NOTION_TOKEN && process.env.NOTION_DATABASE_ID) {
      try {
        await saveDailyPageToNotion({
          date,
          grouped,
          entryCount: entries.length,
          entries,
          summaryText: summary,
          categoryLabels: CATEGORY_LABELS,
        });
        notionStatus = 'ok';
      } catch (e) {
        console.error('[cron] notion save failed:', e);
        notionStatus = `failed: ${e.message}`;
      }
    } else if (entries.length) {
      notionStatus = 'skipped (not configured)';
    }

    res.status(200).json({ ok: true, date, count: entries.length, notion: notionStatus });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
};
