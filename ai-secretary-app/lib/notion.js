/**
 * その日のメモ・要約をNotionデータベースに1ページとして保存する。
 * NOTION_TOKEN / NOTION_DATABASE_ID が未設定の場合は呼び出し元でスキップすること。
 */
const NOTION_VERSION = '2022-06-28';

function richText(content) {
  return { rich_text: [{ type: 'text', text: { content: String(content || '').slice(0, 1900) } }] };
}

function summaryToBlocks(summaryText) {
  return String(summaryText || '')
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => ({
      object: 'block',
      type: 'paragraph',
      paragraph: { rich_text: [{ type: 'text', text: { content: line.slice(0, 1900) } }] },
    }));
}

function rawEntryBlocks(entries, categoryLabels) {
  return entries.map((e) => ({
    object: 'block',
    type: 'bulleted_list_item',
    bulleted_list_item: {
      rich_text: [
        { type: 'text', text: { content: `[${categoryLabels[e.category] || 'その他'}] ${e.text}`.slice(0, 1900) } },
      ],
    },
  }));
}

async function saveDailyPageToNotion({ date, grouped, entryCount, entries, summaryText, categoryLabels }) {
  const token = process.env.NOTION_TOKEN;
  const databaseId = process.env.NOTION_DATABASE_ID;
  if (!token || !databaseId) throw new Error('NOTION_TOKEN / NOTION_DATABASE_ID is not set');

  const children = [
    ...summaryToBlocks(summaryText),
    { object: 'block', type: 'divider', divider: {} },
    {
      object: 'block',
      type: 'heading_3',
      heading_3: { rich_text: [{ type: 'text', text: { content: '生メモ' } }] },
    },
    ...rawEntryBlocks(entries, categoryLabels),
  ];

  const res = await fetch('https://api.notion.com/v1/pages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      Authorization: `Bearer ${token}`,
      'Notion-Version': NOTION_VERSION,
    },
    body: JSON.stringify({
      parent: { database_id: databaseId },
      properties: {
        Name: { title: [{ text: { content: date } }] },
        日付: { date: { start: date } },
        仕事: richText(grouped.work.join(' / ')),
        新しいアイデア: richText(grouped.idea.join(' / ')),
        明日やること: richText(grouped.task.join(' / ')),
        後で調べること: richText(grouped.later.join(' / ')),
        メモ件数: { number: entryCount },
      },
      children,
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Notion API error: ${res.status} ${body.slice(0, 300)}`);
  }
}

module.exports = { saveDailyPageToNotion };
