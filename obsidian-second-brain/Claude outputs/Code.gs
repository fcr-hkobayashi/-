/**
 * マキカエシ 面接準備 — 検証用バックエンド（Google スプレッドシート + Apps Script）
 *
 * 受講者アプリ（student/index.html）と運営管理アプリ（admin/admin.html）が
 * 同じスプレッドシートを読み書きするための窓口。
 *
 * ・検証専用。テスター数名・架空またはテスト用のデータで使うこと
 * ・受講者は運営が発行した「受講者コード」でだけ書き込める
 * ・運営の操作は ADMIN_KEY（スクリプトプロパティ）が必要
 *
 * 使い方は「セットアップ手順.md」を参照。
 */

const SHEETS = {
  students:  ['code', 'name', 'cohort', 'consent_at', 'created_at', 'updated_at'],
  me:        ['code', 'answer', 'job', 'wins', 'hours', 'updated_at'],
  companies: ['code', 'name', 'url', 'step', 'result', 'date', 'memo', 'posting', 'saved_at'],
  feedback:  ['code', 'at', 'text']
};

/* ---------- 初回だけ実行：シートを作り、ADMIN_KEY を発行する ---------- */
function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Object.keys(SHEETS).forEach(function (name) {
    let sh = ss.getSheetByName(name);
    if (!sh) sh = ss.insertSheet(name);
    const head = SHEETS[name];
    sh.getRange(1, 1, 1, head.length).setValues([head]).setFontWeight('bold');
    sh.setFrozenRows(1);
    // 日付などが勝手に変換されないよう、全列を文字列扱いにする
    sh.getRange(1, 1, sh.getMaxRows(), head.length).setNumberFormat('@');
  });
  const props = PropertiesService.getScriptProperties();
  let key = props.getProperty('ADMIN_KEY');
  if (!key) {
    key = Utilities.getUuid().replace(/-/g, '');
    props.setProperty('ADMIN_KEY', key);
  }
  Logger.log('ADMIN_KEY: ' + key + '（運営管理アプリで入力します。人に見せないこと）');
}

/* ---------- 窓口 ---------- */
function doGet(e) {
  return respond_((e && e.parameter) || {});
}
function doPost(e) {
  let p = {};
  try { p = JSON.parse((e && e.postData && e.postData.contents) || '{}'); } catch (err) { p = {}; }
  return respond_(p);
}
function respond_(p) {
  let out;
  try {
    out = Object.assign({ ok: true }, route_(p));
  } catch (err) {
    out = { ok: false, error: String((err && err.message) || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

function route_(p) {
  switch (p.action) {
    case 'ping':              return { now: now_() };
    case 'student.load':      return studentLoad_(p);
    case 'student.save':      return withLock_(function () { return studentSave_(p); });
    case 'admin.list':        requireAdmin_(p); return adminList_();
    case 'admin.feedback':    requireAdmin_(p); return withLock_(function () { return adminFeedback_(p); });
    case 'admin.addStudent':  requireAdmin_(p); return withLock_(function () { return adminAddStudent_(p); });
    default: throw new Error('不明な操作です: ' + p.action);
  }
}

/* ---------- 受講者 ---------- */
function studentLoad_(p) {
  const st = findStudent_(p.code);
  return {
    student: { code: st.code, name: st.name, cohort: st.cohort, consent_at: st.consent_at },
    me: rows_('me').filter(byCode_(st.code))[0] || null,
    companies: rows_('companies').filter(byCode_(st.code)),
    feedback: rows_('feedback').filter(byCode_(st.code)).sort(function (a, b) { return a.at < b.at ? 1 : -1; })
  };
}

function studentSave_(p) {
  const st = findStudent_(p.code);
  if (!st.consent_at && !p.consent) throw new Error('同意がないため保存できません');
  const t = now_();

  if (p.me) {
    const me = p.me;
    upsert_('me', st.code, {
      code: st.code,
      answer: str_(me.answer, 300), job: str_(me.job, 300),
      wins: str_(me.wins, 2000), hours: str_(me.hours, 300), updated_at: t
    });
  }
  if (Array.isArray(p.companies)) {
    const list = p.companies.slice(0, 100).map(function (c) {
      return {
        code: st.code,
        name: str_(c.name, 100), url: str_(c.url, 300), step: str_(c.step, 20), result: str_(c.result, 20),
        date: str_(c.date, 10), memo: str_(c.memo, 1000), posting: str_(c.posting, 8000), saved_at: str_(c.at, 30) || t
      };
    });
    replaceFor_('companies', st.code, list);
  }
  const patch = { updated_at: t };
  if (!st.consent_at && p.consent) patch.consent_at = t;
  updateStudent_(st.code, patch);
  return { saved_at: t };
}

/* ---------- 運営 ---------- */
function adminList_() {
  const me = rows_('me'), cos = rows_('companies'), fb = rows_('feedback');
  return {
    students: rows_('students').map(function (s) {
      return {
        code: s.code, name: s.name, cohort: s.cohort, consent_at: s.consent_at,
        created_at: s.created_at, updated_at: s.updated_at,
        me: me.filter(byCode_(s.code))[0] || null,
        companies: cos.filter(byCode_(s.code)),
        feedback: fb.filter(byCode_(s.code)).sort(function (a, b) { return a.at < b.at ? 1 : -1; })
      };
    })
  };
}

function adminFeedback_(p) {
  const st = findStudent_(p.code);
  const text = str_(p.text, 2000);
  if (!text) throw new Error('フィードバックが空です');
  append_('feedback', { code: st.code, at: now_(), text: text });
  return { done: true };
}

function adminAddStudent_(p) {
  const name = str_(p.name, 50);
  if (!name) throw new Error('名前を入れてください');
  const code = 'MK-' + Utilities.getUuid().replace(/-/g, '').slice(0, 6).toUpperCase();
  const t = now_();
  append_('students', { code: code, name: name, cohort: str_(p.cohort, 20), consent_at: '', created_at: t, updated_at: t });
  return { code: code };
}

/* ---------- 共通 ---------- */
function requireAdmin_(p) {
  const key = PropertiesService.getScriptProperties().getProperty('ADMIN_KEY');
  if (!key || p.key !== key) throw new Error('運営キーが違います');
}
function findStudent_(code) {
  code = String(code || '').trim().toUpperCase();
  if (!code) throw new Error('受講者コードを入れてください');
  const st = rows_('students').filter(byCode_(code))[0];
  if (!st) throw new Error('受講者コードが見つかりません');
  return st;
}
function withLock_(fn) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try { return fn(); } finally { lock.releaseLock(); }
}
function sheet_(name) {
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
  if (!sh) throw new Error('シート「' + name + '」がありません。setup() を実行してください');
  return sh;
}
function rows_(name) {
  const sh = sheet_(name), head = SHEETS[name], n = sh.getLastRow() - 1;
  if (n <= 0) return [];
  const tz = Session.getScriptTimeZone();
  return sh.getRange(2, 1, n, head.length).getValues().map(function (r) {
    const o = {};
    head.forEach(function (h, i) {
      const v = r[i];
      o[h] = v instanceof Date ? Utilities.formatDate(v, tz, h === 'date' ? 'yyyy-MM-dd' : "yyyy-MM-dd'T'HH:mm:ss") : String(v);
    });
    return o;
  });
}
function toRow_(name, obj) { return SHEETS[name].map(function (h) { return obj[h] == null ? '' : String(obj[h]); }); }
function append_(name, obj) { sheet_(name).appendRow(toRow_(name, obj)); }
function upsert_(name, code, obj) {
  const sh = sheet_(name), all = rows_(name);
  const i = all.findIndex(byCode_(code));
  if (i >= 0) sh.getRange(i + 2, 1, 1, SHEETS[name].length).setValues([toRow_(name, obj)]);
  else append_(name, obj);
}
function replaceFor_(name, code, list) {
  const sh = sheet_(name), head = SHEETS[name];
  const keep = rows_(name).filter(function (r) { return r.code !== code; });
  const all = keep.concat(list).map(function (o) { return toRow_(name, o); });
  const n = sh.getLastRow() - 1;
  if (n > 0) sh.getRange(2, 1, n, head.length).clearContent();
  if (all.length) sh.getRange(2, 1, all.length, head.length).setValues(all);
}
function updateStudent_(code, patch) {
  const st = rows_('students').filter(byCode_(code))[0];
  upsert_('students', code, Object.assign({}, st, patch));
}
function byCode_(code) { return function (r) { return r.code === code; }; }
function str_(v, max) { return String(v == null ? '' : v).slice(0, max); }
function now_() { return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss"); }
