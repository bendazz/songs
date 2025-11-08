let chart, fuse, songsIndex = [];
const els = {
  search: document.getElementById('search'),
  suggestions: document.getElementById('suggestions'),
  meta: document.getElementById('meta')
};

async function loadData() {
  const res = await fetch('data/song_pct.json');
  const data = await res.json();
  // Build index
  songsIndex = Object.keys(data).sort();
  fuse = new Fuse(songsIndex, { includeScore: false, threshold: 0.3 });
  setupSearch(data);
  // Preload first song example
  if (songsIndex.length) renderChart(songsIndex[0], data);
}

function setupSearch(data) {
  let activeIndex = -1;
  els.search.addEventListener('input', () => {
    const q = els.search.value.trim();
    const results = q ? fuse.search(q).slice(0, 12).map(r => r.item) : songsIndex.slice(0, 12);
    renderSuggestions(results, data);
    activeIndex = -1;
  });

  els.search.addEventListener('keydown', (e) => {
    const items = Array.from(els.suggestions.querySelectorAll('li'));
    if (!items.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); activeIndex = Math.min(activeIndex + 1, items.length - 1); updateActive(items); }
    if (e.key === 'ArrowUp') { e.preventDefault(); activeIndex = Math.max(activeIndex - 1, 0); updateActive(items); }
    if (e.key === 'Enter' && activeIndex >= 0) { e.preventDefault(); items[activeIndex].click(); }
  });

  els.suggestions.addEventListener('click', (e) => {
    const item = e.target.closest('li');
    if (!item) return;
    const song = item.dataset.song;
    els.search.value = song;
    els.suggestions.innerHTML = '';
    renderChart(song, data);
  });
}

function updateActive(items) {
  items.forEach((it, i) => it.classList.toggle('active', i === activeIndex));
}

function renderSuggestions(list, data) {
  els.suggestions.innerHTML = list.map(s => `<li data-song="${encodeURIComponent(s)}">${s}</li>`).join('');
}

function renderChart(song, data) {
  const key = decodeURIComponent(song);
  const rows = (data[key] || []).filter(r => r.date && typeof r.pct === 'number');
  const labels = rows.map(r => r.date);
  const pct = rows.map(r => r.pct);

  const ctx = document.getElementById('chart').getContext('2d');
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: `% of prior eligible dates the song was played`,
        data: pct,
        fill: false,
        borderColor: '#60a5fa',
        backgroundColor: '#60a5fa',
        tension: 0.15,
        pointRadius: 0,
        borderWidth: 2
      }, {
        label: 'Played dates',
        data: pct.map((v,i)=> rows[i].played ? v : null),
        showLine: false,
        borderColor: '#fbbf24',
        backgroundColor: '#fbbf24',
        pointRadius: function(ctx){
          const i = ctx.dataIndex; return rows[i].played ? 4 : 0;
        },
        pointHoverRadius: 6,
        pointStyle: 'circle'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#cbd5e1', maxTicksLimit: 12 } },
        y: { grid: { color: 'rgba(148,163,184,.15)' }, ticks: { color: '#cbd5e1', callback: v => `${v}%` }, suggestedMin: 0, suggestedMax: 100 }
      },
      plugins: { legend: { labels: { color: '#e5e7eb' } }, tooltip: { callbacks: { label: ctx => `${ctx.parsed.y.toFixed(2)}%` } } }
    }
  });

  // Meta
  const firstDate = labels[0] || '—';
  const lastDate = labels[labels.length - 1] || '—';
  const avg = pct.length ? (pct.reduce((a,b)=>a+b,0)/pct.length).toFixed(2) : '0.00';
  els.meta.innerHTML = `<span class="badge">Song</span> ${key} &nbsp; <span class="badge">Dates</span> ${labels.length} &nbsp; <span class="badge">Avg %</span> ${avg}%`;
}

loadData();
