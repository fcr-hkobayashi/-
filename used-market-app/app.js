const sampleItems = [
  {
    id: "ip14p-256",
    name: "iPhone 14 Pro 256GB SIMフリー",
    category: "スマホ",
    model: "MQ0Q3J/A",
    confidence: 86,
    sources: [
      { name: "フリマ成約", price: 92500, count: 38 },
      { name: "オークション", price: 88400, count: 24 },
      { name: "店頭販売", price: 99800, count: 12 },
    ],
  },
  {
    id: "switch-oled",
    name: "Nintendo Switch 有機ELモデル ホワイト",
    category: "ゲーム機",
    model: "HEG-S-KAAAA",
    confidence: 91,
    sources: [
      { name: "フリマ成約", price: 26900, count: 80 },
      { name: "オークション", price: 25400, count: 42 },
      { name: "店頭販売", price: 30900, count: 18 },
    ],
  },
  {
    id: "rx100m7",
    name: "SONY Cyber-shot RX100 VII",
    category: "カメラ",
    model: "DSC-RX100M7",
    confidence: 78,
    sources: [
      { name: "フリマ成約", price: 132000, count: 18 },
      { name: "オークション", price: 126500, count: 14 },
      { name: "店頭販売", price: 149800, count: 7 },
    ],
  },
  {
    id: "speedmaster",
    name: "OMEGA Speedmaster Professional",
    category: "時計",
    model: "310.30.42.50.01.002",
    confidence: 72,
    sources: [
      { name: "フリマ成約", price: 748000, count: 9 },
      { name: "オークション", price: 721000, count: 12 },
      { name: "店頭販売", price: 858000, count: 5 },
    ],
  },
  {
    id: "lv-neverfull",
    name: "Louis Vuitton ネヴァーフル MM モノグラム",
    category: "ブランドバッグ",
    model: "M41178",
    confidence: 69,
    sources: [
      { name: "フリマ成約", price: 146000, count: 21 },
      { name: "オークション", price: 138000, count: 16 },
      { name: "店頭販売", price: 178000, count: 8 },
    ],
  },
  {
    id: "ipad-air5",
    name: "iPad Air 第5世代 Wi-Fi 64GB",
    category: "スマホ",
    model: "MM9C3J/A",
    confidence: 88,
    sources: [
      { name: "フリマ成約", price: 57800, count: 44 },
      { name: "オークション", price: 54800, count: 28 },
      { name: "店頭販売", price: 69800, count: 13 },
    ],
  },
];

const STORAGE_KEYS = {
  items: "reuse-price-desk-items",
  history: "reuse-price-desk-history",
};

const MARKET_CONFIGS = [
  { key: "aucfan", label: "オークファン" },
  { key: "yahoo", label: "ヤフオク" },
  { key: "mercari", label: "メルカリ" },
  { key: "rakuma", label: "楽天ラクマ" },
  { key: "shopping", label: "Yahoo!ショッピング" },
];

const state = {
  items: loadJson(STORAGE_KEYS.items, sampleItems),
  history: loadJson(STORAGE_KEYS.history, []),
  selectedId: null,
};

const els = {
  searchInput: document.querySelector("#searchInput"),
  categorySelect: document.querySelector("#categorySelect"),
  conditionSelect: document.querySelector("#conditionSelect"),
  boxCheck: document.querySelector("#boxCheck"),
  accessoryCheck: document.querySelector("#accessoryCheck"),
  warrantyCheck: document.querySelector("#warrantyCheck"),
  feeRange: document.querySelector("#feeRange"),
  marginRange: document.querySelector("#marginRange"),
  riskRange: document.querySelector("#riskRange"),
  feeValue: document.querySelector("#feeValue"),
  marginValue: document.querySelector("#marginValue"),
  riskValue: document.querySelector("#riskValue"),
  itemList: document.querySelector("#itemList"),
  itemCount: document.querySelector("#itemCount"),
  saveQuoteBtn: document.querySelector("#saveQuoteBtn"),
  exportBtn: document.querySelector("#exportBtn"),
  importInput: document.querySelector("#importInput"),
  historyList: document.querySelector("#historyList"),
  clearHistoryBtn: document.querySelector("#clearHistoryBtn"),
  photoInput: document.querySelector("#photoInput"),
  photoPreview: document.querySelector("#photoPreview"),
  photoPlaceholder: document.querySelector("#photoPlaceholder"),
  photoSearchBtn: document.querySelector("#photoSearchBtn"),
  openAllMarketsBtn: document.querySelector("#openAllMarketsBtn"),
  clearMarketBtn: document.querySelector("#clearMarketBtn"),
  manualMarketInput: document.querySelector("#manualMarketInput"),
  manualBuyInput: document.querySelector("#manualBuyInput"),
  marketPasteInputs: Object.fromEntries(
    MARKET_CONFIGS.map((market) => [market.key, document.querySelector(`#${market.key}PasteInput`)]),
  ),
  marketSummaries: Object.fromEntries(
    MARKET_CONFIGS.map((market) => [market.key, document.querySelector(`#${market.key}ExtractSummary`)]),
  ),
};

function loadJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function yen(value) {
  if (!Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0,
  }).format(Math.round(value));
}

function median(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function percentile(values, ratio) {
  const sorted = values.slice().sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const index = (sorted.length - 1) * ratio;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

function withoutOutliers(values) {
  const prices = values.filter((value) => Number.isFinite(value) && value >= 300 && value <= 10000000);
  if (prices.length < 4) return prices;
  const q1 = percentile(prices, 0.25);
  const q3 = percentile(prices, 0.75);
  const iqr = q3 - q1;
  const min = Math.max(300, q1 - iqr * 1.5);
  const max = q3 + iqr * 1.5;
  return prices.filter((price) => price >= min && price <= max);
}

function getSelectedItem() {
  return state.items.find((item) => item.id === state.selectedId) ?? filteredItems()[0] ?? null;
}

function filteredItems() {
  const query = els.searchInput.value.trim().toLowerCase();
  const category = els.categorySelect.value;
  return state.items.filter((item) => {
    const text = `${item.name} ${item.model} ${item.category}`.toLowerCase();
    const matchesQuery = !query || text.includes(query);
    const matchesCategory = category === "all" || item.category === category;
    return matchesQuery && matchesCategory;
  });
}

function accessoryMultiplier() {
  let multiplier = Number(els.conditionSelect.value);
  if (!els.boxCheck.checked) multiplier -= 0.03;
  if (!els.accessoryCheck.checked) multiplier -= 0.05;
  if (els.warrantyCheck.checked) multiplier += 0.03;
  return Math.max(0.25, multiplier);
}

function getMarketSources(item) {
  const sources = item.sources.slice();
  MARKET_CONFIGS.forEach((market) => {
    const extracted = marketPrices(market.key);
    if (extracted.length) {
      sources.unshift({ name: `${market.label}抽出`, price: median(extracted), count: extracted.length });
    }
  });
  const manualMarket = Number(els.manualMarketInput.value);
  if (manualMarket > 0) {
    sources.unshift({ name: "手入力相場", price: manualMarket, count: 1 });
  }
  return sources.filter((source) => Number(source.price) > 0);
}

function calculate(item) {
  const sourcePrices = getWeightedMarketPrices(item);
  const mid = median(sourcePrices);
  const low = Math.min(...sourcePrices);
  const high = Math.max(...sourcePrices);
  const adjusted = mid * accessoryMultiplier();
  const fee = Number(els.feeRange.value) / 100;
  const margin = Number(els.marginRange.value) / 100;
  const risk = Number(els.riskRange.value) / 100;
  const sell = adjusted * (1 + risk * 0.35);
  const manualBuy = Number(els.manualBuyInput.value);
  const limit = manualBuy > 0 ? manualBuy : sell * (1 - fee - margin - risk);
  return {
    median: mid,
    low,
    high,
    sell,
    limit: Math.max(0, limit),
  };
}

function getWeightedMarketPrices(item) {
  const baseSources = item.sources.map((source) => source.price);
  const extractedPrices = MARKET_CONFIGS.flatMap((market) => marketPrices(market.key));
  const manualMarket = Number(els.manualMarketInput.value);
  const prices = [
    ...baseSources,
    ...extractedPrices,
    ...(manualMarket > 0 ? [manualMarket] : []),
  ];
  return withoutOutliers(prices);
}

function renderItems() {
  const items = filteredItems();
  els.itemCount.textContent = `${items.length}件`;
  if (!items.length) {
    els.itemList.innerHTML = `<p class="empty">該当する相場データがありません</p>`;
    return;
  }

  if (!items.some((item) => item.id === state.selectedId)) {
    state.selectedId = items[0].id;
  }

  els.itemList.innerHTML = items
    .map((item) => {
      const calc = calculate(item);
      const active = item.id === state.selectedId ? " active" : "";
      return `
        <button class="item-card${active}" type="button" data-id="${item.id}">
          <div class="item-title">
            <span>${escapeHtml(item.name)}</span>
            <span class="tag">${escapeHtml(item.category)}</span>
          </div>
          <div class="item-meta">
            <span>${escapeHtml(item.model)}</span>
            <span>中央値 ${yen(calc.median)}</span>
            <span>上限 ${yen(calc.limit)}</span>
          </div>
        </button>
      `;
    })
    .join("");
}

function renderHistory() {
  if (!state.history.length) {
    els.historyList.innerHTML = `<p class="empty">保存した査定はまだありません</p>`;
    return;
  }

  els.historyList.innerHTML = state.history
    .map(
      (entry) => `
        <article class="history-card">
          <div class="history-title">
            <span>${escapeHtml(entry.name)}</span>
            <span class="tag">${escapeHtml(entry.condition)}</span>
          </div>
          <div class="history-meta">
            <span>${entry.date}</span>
            <span>販売 ${yen(entry.sell)}</span>
            <span>参考買取 ${yen(entry.limit)}</span>
            <span>手数料 ${entry.fee}%</span>
            <span>粗利 ${entry.margin}%</span>
            ${entry.manualMarket ? `<span>手入力相場 ${yen(entry.manualMarket)}</span>` : ""}
            ${entry.manualBuy ? `<span>手入力買取 ${yen(entry.manualBuy)}</span>` : ""}
            ${(entry.marketStats || [])
              .map((stat) => `<span>${escapeHtml(stat.label)} ${stat.count}件 ${yen(stat.median)}</span>`)
              .join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderControls() {
  els.feeValue.textContent = els.feeRange.value;
  els.marginValue.textContent = els.marginRange.value;
  els.riskValue.textContent = els.riskRange.value;
  MARKET_CONFIGS.forEach((market) => {
    renderExtractSummary(els.marketSummaries[market.key], els.marketPasteInputs[market.key].value);
  });
}

function renderAll() {
  renderControls();
  renderItems();
  renderHistory();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

function selectedConditionLabel() {
  return els.conditionSelect.options[els.conditionSelect.selectedIndex].textContent;
}

function randomId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `quote-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function saveQuote() {
  const item = getSelectedItem();
  if (!item) return;
  const calc = calculate(item);
  const marketStats = MARKET_CONFIGS.map((market) => {
    const prices = marketPrices(market.key);
    return prices.length
      ? { key: market.key, label: market.label, count: prices.length, median: median(prices) }
      : null;
  }).filter(Boolean);
  state.history.unshift({
    id: randomId(),
    date: new Date().toLocaleString("ja-JP", { dateStyle: "short", timeStyle: "short" }),
    name: item.name,
    condition: selectedConditionLabel(),
    sell: calc.sell,
    limit: calc.limit,
    fee: Number(els.feeRange.value),
    margin: Number(els.marginRange.value),
    manualMarket: Number(els.manualMarketInput.value) || "",
    manualBuy: Number(els.manualBuyInput.value) || "",
    marketStats,
  });
  state.history = state.history.slice(0, 40);
  saveJson(STORAGE_KEYS.history, state.history);
  renderHistory();
}

function exportCsv() {
  const rows = [
    ["name", "category", "model", "confidence", "source1_name", "source1_price", "source1_count", "source2_name", "source2_price", "source2_count", "source3_name", "source3_price", "source3_count"],
    ...state.items.map((item) => [
      item.name,
      item.category,
      item.model,
      item.confidence,
      ...item.sources.flatMap((source) => [source.name, source.price, source.count]),
    ]),
  ];
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "reuse-price-data.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvCell(value) {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

function importCsv(file) {
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    const rows = parseCsv(String(reader.result)).slice(1);
    const imported = rows
      .filter((row) => row[0])
      .map((row, index) => ({
        id: `import-${Date.now()}-${index}`,
        name: row[0],
        category: row[1] || "その他",
        model: row[2] || "-",
        confidence: Number(row[3]) || 60,
        sources: [
          { name: row[4] || "ソース1", price: Number(row[5]) || 0, count: Number(row[6]) || 0 },
          { name: row[7] || "ソース2", price: Number(row[8]) || 0, count: Number(row[9]) || 0 },
          { name: row[10] || "ソース3", price: Number(row[11]) || 0, count: Number(row[12]) || 0 },
        ],
      }));
    if (imported.length) {
      state.items = imported;
      state.selectedId = imported[0].id;
      saveJson(STORAGE_KEYS.items, state.items);
      renderAll();
    }
  });
  reader.readAsText(file);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

function clearExternalMarketPrices() {
  els.manualMarketInput.value = "";
  els.manualBuyInput.value = "";
  MARKET_CONFIGS.forEach((market) => {
    els.marketPasteInputs[market.key].value = "";
  });
}

function marketPrices(key) {
  return withoutOutliers(extractPrices(els.marketPasteInputs[key].value));
}

function extractPrices(text) {
  const normalized = String(text || "")
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0xfee0))
    .replace(/，/g, ",")
    .replace(/￥/g, "¥");
  const prices = [];
  const pricePatterns = [
    /(?:¥|￥)\s*([0-9][0-9,]{2,})/g,
    /([0-9][0-9,]{2,})\s*円/g,
    /\b([1-9][0-9]{0,2}(?:,[0-9]{3})+)\b/g,
  ];

  pricePatterns.forEach((pattern) => {
    let match = pattern.exec(normalized);
    while (match) {
      const value = Number(match[1].replace(/,/g, ""));
      if (Number.isFinite(value)) prices.push(value);
      match = pattern.exec(normalized);
    }
  });

  return [...new Set(prices)].filter((price) => price >= 300 && price <= 10000000);
}

function renderExtractSummary(element, text) {
  const all = extractPrices(text);
  const filtered = withoutOutliers(all);
  if (!all.length) {
    element.textContent = "0件";
    return;
  }
  const removed = all.length - filtered.length;
  const suffix = removed > 0 ? ` / 除外 ${removed}件` : "";
  element.textContent = `${filtered.length}件 / 中央値 ${yen(median(filtered))}${suffix}`;
}

function updatePhotoPreview(file) {
  if (!file) return;
  const url = URL.createObjectURL(file);
  els.photoPreview.src = url;
  els.photoPreview.onload = () => URL.revokeObjectURL(url);
  els.photoPreview.closest(".photo-drop").classList.add("has-image");
  els.photoPlaceholder.textContent = "撮り直し";
}

function searchFromPhoto() {
  const [file] = els.photoInput.files;
  if (!file) return;
  const guessed = file.name
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\b(img|image|photo|dsc|pxl)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  if (guessed && guessed.length > 2) {
    els.searchInput.value = guessed;
  }
  clearExternalMarketPrices();
  state.selectedId = null;
  renderAll();
}

function currentSearchQuery() {
  const item = getSelectedItem();
  return els.searchInput.value.trim() || item?.name || "";
}

function openMarketSearch(kind) {
  const query = encodeURIComponent(currentSearchQuery());
  if (!query) return;
  const urls = {
    aucfan: `https://aucfan.com/search1/q-${query}/s-mix/`,
    yahoo: `https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=${query}`,
    mercari: `https://jp.mercari.com/search?keyword=${query}&status=on_sale,sold_out`,
    rakuma: `https://fril.jp/search/${query}`,
    shopping: `https://shopping.yahoo.co.jp/search?p=${query}&used=1`,
  };
  window.open(urls[kind], "_blank", "noopener");
}

function openAllMarketSearches() {
  MARKET_CONFIGS.forEach((market) => openMarketSearch(market.key));
}

els.itemList.addEventListener("click", (event) => {
  const card = event.target.closest("[data-id]");
  if (!card) return;
  if (state.selectedId !== card.dataset.id) clearExternalMarketPrices();
  state.selectedId = card.dataset.id;
  renderAll();
});

els.searchInput.addEventListener("input", () => {
  clearExternalMarketPrices();
  state.selectedId = null;
});

[
  els.searchInput,
  els.categorySelect,
  els.conditionSelect,
  els.boxCheck,
  els.accessoryCheck,
  els.warrantyCheck,
  els.feeRange,
  els.marginRange,
  els.riskRange,
  els.manualMarketInput,
  els.manualBuyInput,
  ...Object.values(els.marketPasteInputs),
].forEach((control) => control.addEventListener("input", renderAll));

els.saveQuoteBtn.addEventListener("click", saveQuote);
els.exportBtn.addEventListener("click", exportCsv);
els.clearHistoryBtn.addEventListener("click", () => {
  state.history = [];
  saveJson(STORAGE_KEYS.history, state.history);
  renderHistory();
});
els.importInput.addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) importCsv(file);
  event.target.value = "";
});
els.photoInput.addEventListener("change", (event) => {
  const [file] = event.target.files;
  updatePhotoPreview(file);
  searchFromPhoto();
});
els.photoSearchBtn.addEventListener("click", searchFromPhoto);
els.openAllMarketsBtn.addEventListener("click", openAllMarketSearches);
els.clearMarketBtn.addEventListener("click", () => {
  clearExternalMarketPrices();
  renderAll();
});
document.querySelectorAll("[data-open-market]").forEach((button) => {
  button.addEventListener("click", () => openMarketSearch(button.dataset.openMarket));
});

renderAll();
