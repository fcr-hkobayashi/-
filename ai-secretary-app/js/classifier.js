/**
 * ルールベースの簡易分類器。
 * Claude APIキーが未設定でも、キーワード一致だけで「仕事/アイデア/タスク/後で調べる」に振り分ける。
 */
(function () {
  const CATEGORY_LABELS = {
    work: '仕事',
    idea: '新しいアイデア',
    task: '明日やること',
    later: '後で調べること',
    other: 'その他',
  };

  const CATEGORY_ORDER = ['work', 'idea', 'task', 'later', 'other'];

  // 判定優先度: 同点のときは先に書いたカテゴリが勝つ
  const KEYWORDS = {
    task: [
      'やらないと', 'しないと', 'しなきゃ', 'やること', '今日中に', '締切', '締め切り',
      '提出', '予約', '電話する', '連絡する', '買わないと', '行かないと', '忘れずに',
      'リマインド', 'todo', 'ToDo', '明日までに',
    ],
    idea: [
      'アイデア', '思いついた', 'ひらめいた', 'どうだろう', '企画', 'こんなのどう',
      '面白いかも', 'やってみたい', '作りたい', '閃いた',
    ],
    later: [
      '調べる', '調べたい', '気になる', '知りたい', '勉強', 'リサーチ', '検索したい',
      '後で確認', 'あとで見る',
    ],
    work: [
      '会議', '案件', 'クライアント', '資料', '報告', '上司', 'プロジェクト', '仕事',
      'ミーティング', '商談', '見積もり', '納期', '取引先',
    ],
  };

  function classify(text) {
    const scores = { task: 0, idea: 0, later: 0, work: 0 };
    for (const category of Object.keys(KEYWORDS)) {
      for (const word of KEYWORDS[category]) {
        if (text.includes(word)) scores[category] += 1;
      }
    }
    let best = null;
    let bestScore = 0;
    for (const category of ['task', 'idea', 'later', 'work']) {
      if (scores[category] > bestScore) {
        best = category;
        bestScore = scores[category];
      }
    }
    return best || 'other';
  }

  window.Classifier = { classify, CATEGORY_LABELS, CATEGORY_ORDER };
})();
