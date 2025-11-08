let chart, fuse, songsIndex = [];
const els = {
  search: document.getElementById('search'),
  suggestions: document.getElementById('suggestions'),
  search2: document.getElementById('search2'),
  suggestions2: document.getElementById('suggestions2'),
  meta: document.getElementById('meta')
};
let selectedSong1 = null;
let selectedSong2 = null;
let canvasClickHandler = null;

async function loadData() {
  const res = await fetch('data/song_pct.json');
  const data = await res.json();
  // load metadata mapping song -> album_release_date_iso
  const metaRes = await fetch('data/song_meta.json');
  const songMeta = await metaRes.json();
  // Build index
  songsIndex = Object.keys(data).sort();
  fuse = new Fuse(songsIndex, { includeScore: false, threshold: 0.3 });

  // Wire both search boxes
  setupSearch(data, els.search, els.suggestions, (song) => { selectedSong1 = song; renderChart(selectedSong1 || songsIndex[0], data, selectedSong2, songMeta); });
  setupSearch(data, els.search2, els.suggestions2, (song) => { selectedSong2 = song; renderChart(selectedSong1 || songsIndex[0], data, selectedSong2, songMeta); });

  // Preload first song example
  if (songsIndex.length) {
    selectedSong1 = songsIndex[0];
    els.search.value = selectedSong1;
    renderChart(selectedSong1, data, null);
  }
}

function setupSearch(data, inputEl, suggestionsEl, onSelected) {
  let activeIndex = -1;
  inputEl.addEventListener('input', () => {
    const q = inputEl.value.trim();
    const results = q ? fuse.search(q).slice(0, 12).map(r => r.item) : songsIndex.slice(0, 12);
    suggestionsEl.innerHTML = results.map(s => `<li data-song="${encodeURIComponent(s)}">${s}</li>`).join('');
    activeIndex = -1;
  });

  inputEl.addEventListener('keydown', (e) => {
    const items = Array.from(suggestionsEl.querySelectorAll('li'));
    if (!items.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); activeIndex = Math.min(activeIndex + 1, items.length - 1); items.forEach((it,i)=>it.classList.toggle('active', i===activeIndex)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); activeIndex = Math.max(activeIndex - 1, 0); items.forEach((it,i)=>it.classList.toggle('active', i===activeIndex)); }
    if (e.key === 'Enter' && activeIndex >= 0) { e.preventDefault(); items[activeIndex].click(); }
  });

  suggestionsEl.addEventListener('click', (e) => {
    const item = e.target.closest('li');
    if (!item) return;
    const song = decodeURIComponent(item.dataset.song);
    inputEl.value = song;
    suggestionsEl.innerHTML = '';
    onSelected(song);
  });
}

function renderChart(song, data) {
  // song may be raw or encoded; ensure decode
  const song1 = song ? decodeURIComponent(song) : null;
  const song2 = (typeof arguments[2] === 'string' && arguments[2]) ? decodeURIComponent(arguments[2]) : null;
  const meta = (typeof arguments[3] === 'object') ? arguments[3] : {};

  const rows1 = song1 ? (data[song1] || []).filter(r => r.date && typeof r.pct === 'number') : [];
  const rows2 = song2 ? (data[song2] || []).filter(r => r.date && typeof r.pct === 'number') : [];

  // master date list = union of both date arrays
  const dateSet = new Set();
  rows1.forEach(r => dateSet.add(r.date));
  rows2.forEach(r => dateSet.add(r.date));
  const labels = Array.from(dateSet).sort();

  const map1 = new Map(rows1.map(r => [r.date, r.pct]));
  const map2 = new Map(rows2.map(r => [r.date, r.pct]));

  const data1 = labels.map(d => (map1.has(d) ? map1.get(d) : null));
  const data2 = labels.map(d => (map2.has(d) ? map2.get(d) : null));

  const ctx = document.getElementById('chart').getContext('2d');
  if (chart) chart.destroy();
  const datasets = [];

  // If peers checkbox is checked, find all songs that share release date with song1 and plot them faintly
  const peersCheckbox = document.getElementById('peers');
      if (peersCheckbox && peersCheckbox.checked && song1 && meta) {
    const song1Release = meta[song1];
    if (song1Release) {
      // find peers
        const peers = Object.keys(meta).filter(s => meta[s] === song1Release && s !== song1);
        peers.forEach(p => {
          const rowsP = (data[p] || []).filter(r => r.date && typeof r.pct === 'number');
          const mapP = new Map(rowsP.map(r => [r.date, r.pct]));
          const d = labels.map(d0 => (mapP.has(d0) ? mapP.get(d0) : null));
          // stronger peer visibility: slightly darker, thicker line
          datasets.push({ label: p, data: d, fill: false, borderColor: 'rgba(203,213,225,0.45)', backgroundColor: 'rgba(203,213,225,0.45)', tension: 0.15, pointRadius: 0, pointHoverRadius: 0, borderWidth: 2 });
        });
    }
  }

  if (song1) datasets.push({ label: song1, data: data1, fill: false, borderColor: '#60a5fa', backgroundColor: '#60a5fa', tension: 0.15, pointRadius: 0, pointHoverRadius: 0, borderWidth: 2 });
  if (song2) datasets.push({ label: song2, data: data2, fill: false, borderColor: '#34d399', backgroundColor: '#34d399', tension: 0.15, pointRadius: 0, pointHoverRadius: 0, borderWidth: 2 });

  chart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#cbd5e1', maxTicksLimit: 12 } },
        y: { grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#cbd5e1', callback: v => `${v}%` }, suggestedMin: 0, suggestedMax: 100 }
      },
      plugins: {
        legend: { labels: { color: '#e5e7eb' } },
        tooltip: {
          callbacks: {
            // Show dataset (song) name and value in tooltip
            title: (items) => items && items.length ? items[0].label : '',
            label: (context) => {
              const val = (context.parsed && typeof context.parsed.y === 'number') ? context.parsed.y.toFixed(2) : '—';
              return `${context.dataset.label}: ${val}%`;
            }
          }
        }
      }
    }
  });

  // remove previous click handler if present to avoid duplicates
  if (canvasClickHandler && ctx && ctx.canvas) {
    try { ctx.canvas.removeEventListener('click', canvasClickHandler); } catch (e) {}
    canvasClickHandler = null;
  }

  // Click to toggle highlight on a dataset (makes it thicker and brighter)
  canvasClickHandler = function (e) {
    const elements = chart.getElementsAtEventForMode(e, 'nearest', { intersect: false }, false);
    if (!elements || !elements.length) return;
    const el = elements[0];
    const di = el.datasetIndex;
    const ds = chart.data.datasets[di];
    if (!ds) return;
    // store originals if not stored
    if (ds._origBorderWidth === undefined) ds._origBorderWidth = ds.borderWidth || 1;
    if (ds._origBorderColor === undefined) ds._origBorderColor = ds.borderColor || ds.backgroundColor || '#999';
    // toggle highlight
    if (ds._highlighted) {
      ds.borderWidth = ds._origBorderWidth;
      ds.borderColor = ds._origBorderColor;
      ds._highlighted = false;
    } else {
      ds.borderWidth = Math.max(3, (ds._origBorderWidth || 1) + 1.5);
      ds.borderColor = '#f59e0b';
      ds._highlighted = true;
    }
    chart.update('none');
  };
  ctx.canvas.addEventListener('click', canvasClickHandler);

  // Meta summary for both songs
  const avg1 = (data1.filter(v=>v!==null).length) ? (data1.filter(v=>v!==null).reduce((a,b)=>a+b,0)/data1.filter(v=>v!==null).length).toFixed(2) : '—';
  const avg2 = (data2.filter(v=>v!==null).length) ? (data2.filter(v=>v!==null).reduce((a,b)=>a+b,0)/data2.filter(v=>v!==null).length).toFixed(2) : '—';
  let metaHtml = '';
  if (song1) metaHtml += `<span class="badge">Song A</span> ${song1} &nbsp; <span class="badge">Dates</span> ${labels.length} &nbsp; <span class="badge">Avg %</span> ${avg1}%`;
  if (song2) metaHtml += ` &nbsp; <span class="badge">Song B</span> ${song2} &nbsp; <span class="badge">Avg %</span> ${avg2}%`;
  els.meta.innerHTML = metaHtml;
}

loadData();

// Load model summary and render simple network visualization (single-feature logistic regression)
async function loadModelSummary() {
  try {
    const res = await fetch('data/model_simple.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const m = await res.json();
    renderModel(m);
  } catch (e) {
    console.warn('Model summary not available:', e);
  }
}

function renderModel(m) {
  const svg = document.getElementById('nn-viz');
  if (!svg) return;
  svg.innerHTML = '';

  // Basic geometry
  const W = 700, H = 280;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const inputX = 100, hiddenX = 350, outputX = 580;
  const midY = H/2;

  // Single input node (feature), bias node, output node
  const weight = m.weight;
  const bias = m.bias;

  // Scales for edge thickness
  const wMag = typeof weight === 'number' ? Math.min(8, Math.max(1.5, Math.abs(weight))) : 2;
  const bMag = typeof bias === 'number' ? Math.min(10, Math.max(2, Math.abs(bias))) : 2;

  // Utility to create SVG elements
  function el(name, attrs) { const n = document.createElementNS('http://www.w3.org/2000/svg', name); Object.entries(attrs||{}).forEach(([k,v])=>n.setAttribute(k,v)); return n; }

  // Input node
  svg.appendChild(el('circle', { cx: inputX, cy: midY, r: 30, class: 'nn-node' }));
  svg.appendChild(el('text', { x: inputX, y: midY+5, class: 'nn-label', 'text-anchor':'middle' })).appendChild(document.createTextNode('Feature'));

  // Bias node (draw above)
  const biasY = midY - 90;
  svg.appendChild(el('circle', { cx: hiddenX, cy: biasY, r: 26, class: 'nn-node bias' }));
  svg.appendChild(el('text', { x: hiddenX, y: biasY+4, class: 'nn-label', 'text-anchor':'middle' })).appendChild(document.createTextNode('Bias'));

  // Output node
  svg.appendChild(el('circle', { cx: outputX, cy: midY, r: 34, class: 'nn-node output' }));
  svg.appendChild(el('text', { x: outputX, y: midY+5, class: 'nn-label', 'text-anchor':'middle' })).appendChild(document.createTextNode('Output'));

  // Edge feature -> output with weight thickness & color sign
  const edgeClass = typeof weight === 'number' ? (weight >= 0 ? 'nn-edge pos' : 'nn-edge neg') : 'nn-edge';
  svg.appendChild(el('line', { x1: inputX+30, y1: midY, x2: outputX-34, y2: midY, class: edgeClass, 'stroke-width': wMag }));

  // Bias edge (bias -> output)
  svg.appendChild(el('line', { x1: hiddenX+26, y1: biasY, x2: outputX-40, y2: midY-25, class: 'nn-edge bias', 'stroke-width': bMag }));

  // Weight label
  const wLabelY = midY - 25;
  svg.appendChild(el('text', { x: (inputX+outputX)/2, y: wLabelY, class: 'nn-label', 'text-anchor':'middle' })).appendChild(document.createTextNode(`w = ${weight !== null ? weight.toFixed(3) : '—'}`));
  const bLabelY = biasY - 15;
  svg.appendChild(el('text', { x: hiddenX+80, y: bLabelY, class: 'nn-label', 'text-anchor':'start' })).appendChild(document.createTextNode(`b = ${bias !== null ? bias.toFixed(3) : '—'}`));

  // Activation formula under output
  const formula = `σ(w·x + b)`;
  svg.appendChild(el('text', { x: outputX, y: midY+65, class: 'nn-label', 'text-anchor':'middle' })).appendChild(document.createTextNode(formula));

  // Fill stats panel
  const fmt = n => (typeof n === 'number' ? n.toFixed(4) : '—');
  const accEl = document.getElementById('nn-acc');
  const featureEl = document.getElementById('nn-feature');
  const wEl = document.getElementById('nn-weight');
  const bEl = document.getElementById('nn-bias');
  const bestEl = document.getElementById('nn-best');
  if (accEl) accEl.textContent = fmt(m.final_accuracy);
  if (bestEl) bestEl.textContent = `${fmt(m.best_accuracy)} (epoch ${m.best_epoch})`;
  if (featureEl) featureEl.textContent = m.feature || '—';
  if (wEl) wEl.textContent = weight !== null ? weight.toFixed(4) : '—';
  if (bEl) bEl.textContent = bias !== null ? bias.toFixed(4) : '—';
}

loadModelSummary();
