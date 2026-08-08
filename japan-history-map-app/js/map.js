// 日本地図(簡略化・低ポリゴン)の描画とピンの配置
import { CATEGORY_META } from './data.js';

export const VIEW_W = 620;
export const VIEW_H = 720;

const BOUNDS = { lonMin: 129, lonMax: 146.5, latMin: 30.8, latMax: 45.8 };
const PAD_X = 70;
const PAD_Y = 30;

function project([lon, lat]) {
  const usableH = VIEW_H - PAD_Y * 2 - 130; // 下部は沖縄インセット分の余白
  const scale = usableH / (BOUNDS.latMax - BOUNDS.latMin);
  const xScale = scale * Math.cos((37.5 * Math.PI) / 180);
  const x = PAD_X + (lon - BOUNDS.lonMin) * xScale;
  const y = PAD_Y + (BOUNDS.latMax - lat) * scale;
  return [x, y];
}

// 沖縄本島用インセット投影(別スケールで右下の枠内に配置)
const OKINAWA_BOX = { x: 30, y: VIEW_H - 150, w: 190, h: 120 };
const OKINAWA_BOUNDS = { lonMin: 127.55, lonMax: 128.35, latMin: 26.0, latMax: 26.9 };
function projectOkinawa([lon, lat]) {
  const x = OKINAWA_BOX.x + ((lon - OKINAWA_BOUNDS.lonMin) / (OKINAWA_BOUNDS.lonMax - OKINAWA_BOUNDS.lonMin)) * OKINAWA_BOX.w;
  const y = OKINAWA_BOX.y + OKINAWA_BOX.h - ((lat - OKINAWA_BOUNDS.latMin) / (OKINAWA_BOUNDS.latMax - OKINAWA_BOUNDS.latMin)) * OKINAWA_BOX.h;
  return [x, y];
}

// 簡略化した島の輪郭(低ポリゴン, lon/lat)
const HOKKAIDO = [
  [140.3,41.4],[139.8,42.6],[140.0,43.9],[141.0,45.3],[142.0,45.5],
  [145.0,44.3],[144.5,43.3],[143.0,42.0],[141.5,41.5],[140.3,41.4],
];

const HONSHU = [
  [140.3,41.3],[141.9,40.5],[141.95,39.6],[141.5,38.5],[140.9,37.3],
  [140.85,35.7],[139.8,35.2],[138.95,34.6],[137.2,34.6],[136.85,34.3],
  [135.77,33.45],[135.2,34.3],[134.2,34.5],[132.45,34.35],[130.94,33.95],
  [131.3,34.4],[132.6,35.5],[133.35,35.55],[135.75,35.65],[136.2,35.6],
  [137.0,36.7],[137.35,37.45],[137.0,37.0],[138.0,37.3],[139.8,39.2],
  [140.05,40.5],[140.3,41.3],
];

const SHIKOKU = [
  [133.5,34.3],[134.6,34.35],[134.35,33.5],[132.8,32.7],[132.5,33.3],[132.9,33.95],[133.5,34.3],
];

const KYUSHU = [
  [130.9,33.95],[131.9,33.2],[131.6,32.0],[130.7,31.2],[129.6,32.0],
  [129.7,33.1],[129.9,33.6],[130.9,33.95],
];

const OKINAWA_ISLAND = [
  [127.9,26.85],[128.3,26.6],[128.1,26.1],[127.7,26.15],[127.65,26.5],[127.9,26.85],
];

function toPath(points, projector) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${projector(p)[0].toFixed(1)},${projector(p)[1].toFixed(1)}`).join(' ') + ' Z';
}

const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

export function buildBaseMap(svg) {
  svg.setAttribute('viewBox', `0 0 ${VIEW_W} ${VIEW_H}`);
  svg.innerHTML = '';

  const landGroup = el('g', { class: 'land' });
  for (const poly of [HOKKAIDO, HONSHU, SHIKOKU, KYUSHU]) {
    landGroup.appendChild(el('path', { d: toPath(poly, project), class: 'land-shape' }));
  }
  svg.appendChild(landGroup);

  // 沖縄インセット枠
  const inset = el('g', { class: 'okinawa-inset' });
  inset.appendChild(el('rect', {
    x: OKINAWA_BOX.x - 10, y: OKINAWA_BOX.y - 24, width: OKINAWA_BOX.w + 20, height: OKINAWA_BOX.h + 34,
    class: 'inset-frame',
  }));
  inset.appendChild(el('text', { x: OKINAWA_BOX.x, y: OKINAWA_BOX.y - 10, class: 'inset-label' })).textContent = '沖縄県(拡大)';
  inset.appendChild(el('path', { d: toPath(OKINAWA_ISLAND, projectOkinawa), class: 'land-shape' }));
  svg.appendChild(inset);

  const pinLayer = el('g', { class: 'pin-layer' });
  pinLayer.setAttribute('data-layer', 'pins');
  svg.appendChild(pinLayer);

  return svg;
}

function projectEvent(ev) {
  return ev.pref === '沖縄県' ? projectOkinawa([ev.lon, ev.lat]) : project([ev.lon, ev.lat]);
}

export function renderPins(svg, events, { selectedId, onSelect } = {}) {
  const layer = svg.querySelector('[data-layer="pins"]');
  layer.innerHTML = '';

  for (const ev of events) {
    const [x, y] = projectEvent(ev);
    const color = CATEGORY_META[ev.cat]?.color ?? '#495057';
    const g = el('g', {
      class: 'pin' + (ev.id === selectedId ? ' pin-selected' : ''),
      tabindex: '0',
      role: 'button',
      'aria-label': `${ev.year}年 ${ev.title}`,
      'data-id': ev.id,
    });
    g.appendChild(el('circle', { cx: x, cy: y, r: ev.id === selectedId ? 8 : 5.5, fill: color }));
    if (ev.id === selectedId) {
      g.appendChild(el('circle', { cx: x, cy: y, r: 12, class: 'pin-pulse', stroke: color }));
    }
    g.addEventListener('click', () => onSelect?.(ev));
    g.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect?.(ev); }
    });
    layer.appendChild(g);
  }
}
