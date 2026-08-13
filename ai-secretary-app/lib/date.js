/**
 * 日本時間(JST)基準の日付キー(YYYY-MM-DD)を作る。
 * サーバーのタイムゾーンに依存しないよう Intl.DateTimeFormat で明示的に Asia/Tokyo を指定する。
 */
function jstDateKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

module.exports = { jstDateKey };
