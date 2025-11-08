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
  const loadingEl = document.getElementById('loading');
  if (loadingEl) loadingEl.style.display = 'flex';
  const res = await fetch('data/song_pct.json');
  const data = await res.json();
  // load metadata mapping song -> album_release_date_iso
  const metaRes = await fetch('data/song_meta.json');
  const songMeta = await metaRes.json();
  // Build index
  songsIndex = Object.keys(data).sort();
  fuse = new Fuse(songsIndex, { includeScore: false, threshold: 0.3 });

  // Wire both search boxes
  setupSearch(data, els.search, els.suggestions, (song) => { selectedSong1 = song; renderChart(selectedSong1 || songsIndex[0], data, selectedSong2, songMeta); setRaceHighlightSong(selectedSong1); });
  setupSearch(data, els.search2, els.suggestions2, (song) => { selectedSong2 = song; renderChart(selectedSong1 || songsIndex[0], data, selectedSong2, songMeta); });

  // Preload first song example
  // No preload: leave search blank and chart empty until user selects a song

  // Hide loader once data and UI are wired
  if (loadingEl) loadingEl.style.display = 'none';
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

  // If no songs selected yet, render an empty chart with axes only
  if (!song1 && !song2) {
    chart = new Chart(ctx, {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#cbd5e1', maxTicksLimit: 12 } },
          y: { grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#cbd5e1', callback: v => `${v}%` }, suggestedMin: 0, suggestedMax: 100 }
        },
        plugins: { legend: { display: false } }
      }
    });
    els.meta.innerHTML = '';
    return;
  }

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

// Racing bar chart (top 20 by pct_played_prior over time)
// Assumes existing 'data/song_pct.json' with structure { song: [ {date: 'YYYY-MM-DD', pct: number}, ... ] }
// Build frames of date -> sorted songs and animate.

const race = {
  frames: [],
  idx: 0,
  playing: false,
  timer: null,
  speed: 300,
  limit: 20,
  highlightSong: null
};

function setRaceHighlightSong(song) {
  race.highlightSong = song ? decodeURIComponent(song) : null;
  if (race.frames && race.frames.length) {
    updateRaceFrame(race.idx, true);
  }
}

async function initRaceChart() {
  let raw;
  try {
    const r = await fetch('data/song_pct.json');
    raw = await r.json();
  } catch (e) {
    console.warn('race chart data unavailable', e); return;
  }
  // Transform: gather all dates
  const dateSet = new Set();
  Object.values(raw).forEach(arr => arr.forEach(rec => { if (rec.date && typeof rec.pct === 'number') dateSet.add(rec.date); }));
  const dates = Array.from(dateSet).sort();
  // Build frames (we could sample, but keep all for now)
  const frames = [];
  for (const d of dates) {
    const entries = [];
    for (const [song, arr] of Object.entries(raw)) {
      // find pct for date d (exact match)
      // use last known pct prior to d if exact not present for smoother continuity
      let val = null;
      for (let i = arr.length - 1; i >= 0; i--) {
        const rec = arr[i];
        if (rec.date <= d) { val = (typeof rec.pct === 'number') ? rec.pct : null; break; }
      }
      if (val !== null) entries.push({ song, pct: val });
    }
    entries.sort((a,b) => b.pct - a.pct);
    frames.push({ date: d, top: entries.slice(0, race.limit) });
  }
  race.frames = frames;
  // init slider bounds
  const slider = document.getElementById('race-slider');
  if (slider) {
    slider.max = Math.max(0, frames.length - 1);
    slider.value = 0;
    slider.disabled = frames.length <= 1;
  }
  buildRaceInitial();
}

function buildRaceInitial() {
  const wrap = document.getElementById('race-chart');
  if (!wrap || !race.frames.length) return;
  wrap.innerHTML = '';
  const frame = race.frames[0];
  frame.top.forEach((entry, i) => {
    const row = document.createElement('div');
    row.className = 'race-row';
    row.style.transform = `translateY(${i * 32}px)`;
    const rank = document.createElement('div'); rank.className='race-rank'; rank.textContent = (i+1).toString();
    const label = document.createElement('div'); label.className='race-label'; label.textContent = entry.song;
    const barWrap = document.createElement('div'); barWrap.className='race-bar-wrap';
    const bar = document.createElement('div'); bar.className='race-bar';
    const valSpan = document.createElement('div'); valSpan.className='race-value'; valSpan.textContent = `${entry.pct.toFixed(2)}%`;
    bar.appendChild(valSpan);
    barWrap.appendChild(bar);
    row.appendChild(rank); row.appendChild(label); row.appendChild(barWrap);
    wrap.appendChild(row);
  });
  updateRaceFrame(0, true);
  wireRaceControls();
}

function updateRaceFrame(idx, instant=false) {
  const frame = race.frames[idx];
  if (!frame) return;
  const wrap = document.getElementById('race-chart');
  const dateEl = document.getElementById('race-date');
  if (dateEl) dateEl.textContent = frame.date;
  const slider = document.getElementById('race-slider');
  if (slider && parseInt(slider.value,10) !== idx) slider.value = idx;
  // Map existing rows by song
  const existing = Array.from(wrap.querySelectorAll('.race-row'));
  const bySong = new Map(); existing.forEach(r => { const lab = r.querySelector('.race-label'); if (lab) bySong.set(lab.textContent, r); });
  // Update / create rows for top songs
  frame.top.forEach((entry, rank) => {
    let row = bySong.get(entry.song);
    if (!row) {
      row = document.createElement('div'); row.className='race-row';
      const rankDiv = document.createElement('div'); rankDiv.className='race-rank';
      const label = document.createElement('div'); label.className='race-label'; label.textContent = entry.song;
      const barWrap = document.createElement('div'); barWrap.className='race-bar-wrap';
      const bar = document.createElement('div'); bar.className='race-bar';
      const valSpan = document.createElement('div'); valSpan.className='race-value'; valSpan.textContent = `${entry.pct.toFixed(2)}%`;
      bar.appendChild(valSpan); barWrap.appendChild(bar);
      row.appendChild(rankDiv); row.appendChild(label); row.appendChild(barWrap);
      wrap.appendChild(row);
    }
    const rankDiv = row.querySelector('.race-rank');
    const valSpan = row.querySelector('.race-value');
    if (rankDiv) rankDiv.textContent = (rank+1).toString();
    if (valSpan) valSpan.textContent = `${entry.pct.toFixed(2)}%`;
    const pctNorm = entry.pct / (frame.top[0].pct || 1); // relative width within wrap
    const bar = row.querySelector('.race-bar');
    if (bar) {
      bar.style.width = `${Math.max(3, pctNorm * 100)}%`;
    }
    const y = rank * 32;
    row.style.transform = `translateY(${y}px)`;
    if (instant) row.style.transition = 'none'; else row.style.transition = 'transform .6s ease';
    // toggle highlight class
    row.classList.toggle('race-highlight', !!race.highlightSong && entry.song === race.highlightSong);
  });
  // Remove rows no longer in top
  existing.forEach(r => { const song = r.querySelector('.race-label')?.textContent; if (song && !frame.top.some(e => e.song === song)) r.remove(); });
}

function advanceRace() {
  if (!race.playing) return;
  race.idx = (race.idx + 1) % race.frames.length;
  updateRaceFrame(race.idx);
  race.timer = setTimeout(advanceRace, race.speed);
}

function wireRaceControls() {
  const playBtn = document.getElementById('race-play');
  const pauseBtn = document.getElementById('race-pause');
  const resetBtn = document.getElementById('race-reset');
  const speedSel = document.getElementById('race-speed');
  const slider = document.getElementById('race-slider');
  if (!playBtn || !pauseBtn || !resetBtn || !speedSel) return;
  playBtn.onclick = () => {
    if (race.playing) return; race.playing = true; playBtn.disabled = true; pauseBtn.disabled = false; resetBtn.disabled = false; advanceRace(); };
  pauseBtn.onclick = () => { race.playing = false; playBtn.disabled = false; pauseBtn.disabled = true; clearTimeout(race.timer); };
  resetBtn.onclick = () => { race.playing = false; clearTimeout(race.timer); race.idx = 0; updateRaceFrame(0, true); playBtn.disabled = false; pauseBtn.disabled = true; resetBtn.disabled = true; };
  speedSel.onchange = () => { race.speed = parseInt(speedSel.value, 10); };
  if (slider) {
    slider.oninput = (e) => {
      const v = parseInt(e.target.value, 10) || 0;
      race.idx = v;
      updateRaceFrame(race.idx, true);
    };
    slider.onchange = slider.oninput;
  }
}

initRaceChart();
