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
          datasets.push({ label: p, data: d, fill: false, borderColor: 'rgba(203,213,225,0.35)', backgroundColor: 'rgba(203,213,225,0.35)', tension: 0.15, pointRadius: 0, pointHoverRadius: 0, borderWidth: 1.5 });
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

  // Meta summary for both songs
  const avg1 = (data1.filter(v=>v!==null).length) ? (data1.filter(v=>v!==null).reduce((a,b)=>a+b,0)/data1.filter(v=>v!==null).length).toFixed(2) : '—';
  const avg2 = (data2.filter(v=>v!==null).length) ? (data2.filter(v=>v!==null).reduce((a,b)=>a+b,0)/data2.filter(v=>v!==null).length).toFixed(2) : '—';
  let metaHtml = '';
  if (song1) metaHtml += `<span class="badge">Song A</span> ${song1} &nbsp; <span class="badge">Dates</span> ${labels.length} &nbsp; <span class="badge">Avg %</span> ${avg1}%`;
  if (song2) metaHtml += ` &nbsp; <span class="badge">Song B</span> ${song2} &nbsp; <span class="badge">Avg %</span> ${avg2}%`;
  els.meta.innerHTML = metaHtml;
}

loadData();
