import { EVENTS, CATEGORY_META, ERAS } from './data.js';
import { buildBaseMap, renderPins } from './map.js';
import { initQuiz } from './quiz.js';

const state = {
  yearFrom: 1600,
  yearTo: new Date().getFullYear(),
  cats: new Set(Object.keys(CATEGORY_META)),
  selectedId: null,
};

const svg = document.getElementById('japanMap');
buildBaseMap(svg);

const yearFromInput = document.getElementById('yearFrom');
const yearToInput = document.getElementById('yearTo');
const yearLabel = document.getElementById('yearRangeLabel');
const eraButtons = document.getElementById('eraButtons');
const catFilters = document.getElementById('catFilters');
const eventListEl = document.getElementById('eventList');
const listCountEl = document.getElementById('listCount');
const detailPanel = document.getElementById('detailPanel');

yearToInput.value = String(state.yearTo);
yearFromInput.max = String(state.yearTo);
yearToInput.max = String(state.yearTo);

// 時代クイックボタン
for (const era of ERAS) {
  const btn = document.createElement('button');
  btn.className = 'era-btn';
  btn.textContent = era.label;
  btn.addEventListener('click', () => {
    state.yearFrom = era.from;
    state.yearTo = Math.min(era.to, state.yearTo === undefined ? era.to : new Date().getFullYear());
    if (era.id === 'reiwa') state.yearTo = new Date().getFullYear();
    yearFromInput.value = String(state.yearFrom);
    yearToInput.value = String(state.yearTo);
    update();
  });
  eraButtons.appendChild(btn);
}

const allBtn = document.createElement('button');
allBtn.className = 'era-btn era-btn-all';
allBtn.textContent = 'すべて';
allBtn.addEventListener('click', () => {
  state.yearFrom = 1600;
  state.yearTo = new Date().getFullYear();
  yearFromInput.value = String(state.yearFrom);
  yearToInput.value = String(state.yearTo);
  update();
});
eraButtons.prepend(allBtn);

// カテゴリフィルタ
for (const [key, meta] of Object.entries(CATEGORY_META)) {
  const label = document.createElement('label');
  label.className = 'cat-check';
  label.style.setProperty('--cat-color', meta.color);
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = true;
  input.addEventListener('change', () => {
    if (input.checked) state.cats.add(key); else state.cats.delete(key);
    update();
  });
  label.appendChild(input);
  const swatch = document.createElement('span');
  swatch.className = 'swatch';
  label.appendChild(swatch);
  label.append(meta.label);
  catFilters.appendChild(label);
}

yearFromInput.addEventListener('input', () => {
  state.yearFrom = Math.min(Number(yearFromInput.value), Number(yearToInput.value));
  yearFromInput.value = String(state.yearFrom);
  update();
});
yearToInput.addEventListener('input', () => {
  state.yearTo = Math.max(Number(yearToInput.value), Number(yearFromInput.value));
  yearToInput.value = String(state.yearTo);
  update();
});

function filteredEvents() {
  return EVENTS
    .filter(e => e.year >= state.yearFrom && e.year <= state.yearTo && state.cats.has(e.cat))
    .sort((a, b) => a.year - b.year);
}

function selectEvent(ev) {
  state.selectedId = ev ? ev.id : null;
  renderPins(svg, filteredEvents(), { selectedId: state.selectedId, onSelect: selectEvent });
  renderDetail(ev);
  renderList();
}

function renderDetail(ev) {
  if (!ev) {
    detailPanel.innerHTML = '<p class="detail-placeholder">地図上のピン、または下の一覧から出来事を選んでください。</p>';
    return;
  }
  const meta = CATEGORY_META[ev.cat];
  detailPanel.innerHTML = `
    <span class="detail-cat" style="--cat-color:${meta.color}">${meta.label}</span>
    <h3>${ev.title}</h3>
    <p class="detail-meta">${ev.year}年 ・ ${ev.pref}</p>
    <p class="detail-desc">${ev.desc}</p>
  `;
}

function renderList() {
  const events = filteredEvents();
  listCountEl.textContent = String(events.length);
  eventListEl.innerHTML = '';
  for (const ev of events) {
    const li = document.createElement('li');
    li.className = 'event-item' + (ev.id === state.selectedId ? ' active' : '');
    const meta = CATEGORY_META[ev.cat];
    li.innerHTML = `
      <span class="dot" style="background:${meta.color}"></span>
      <span class="event-year">${ev.year}</span>
      <span class="event-title">${ev.title}</span>
      <span class="event-pref">${ev.pref}</span>
    `;
    li.addEventListener('click', () => selectEvent(ev));
    eventListEl.appendChild(li);
  }
}

function update() {
  yearLabel.textContent = `${state.yearFrom}年 〜 ${state.yearTo}年`;
  const events = filteredEvents();
  if (state.selectedId && !events.some(e => e.id === state.selectedId)) {
    state.selectedId = null;
    renderDetail(null);
  }
  renderPins(svg, events, { selectedId: state.selectedId, onSelect: selectEvent });
  renderList();
}

update();
renderDetail(null);

// タブ切り替え
const tabButtons = document.querySelectorAll('.tab-btn');
const views = { map: document.getElementById('view-map'), quiz: document.getElementById('view-quiz') };
for (const btn of tabButtons) {
  btn.addEventListener('click', () => {
    for (const b of tabButtons) b.classList.toggle('active', b === btn);
    for (const [key, view] of Object.entries(views)) view.classList.toggle('active', key === btn.dataset.tab);
  });
}

initQuiz(document.getElementById('view-quiz'));
