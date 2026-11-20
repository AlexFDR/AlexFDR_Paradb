const gallery = document.querySelector('#gallery');
const statusEl = document.querySelector('#status');
const search = document.querySelector('#search');
const count = document.querySelector('#count');
const howButton = document.querySelector('#how-button');
const infoDialog = document.querySelector('#info-dialog');
const closeDialog = document.querySelector('#close-dialog');
let charts = [];

function youtubeId(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname === 'youtu.be') return parsed.pathname.split('/').filter(Boolean)[0] || null;
    if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'].includes(parsed.hostname)) {
      if (parsed.pathname === '/watch') return parsed.searchParams.get('v');
      const match = parsed.pathname.match(/^\/(?:embed|shorts|live)\/([^/?]+)/);
      return match?.[1] || null;
    }
  } catch { /* Ignore malformed URLs in descriptions. */ }
  return null;
}

function videoLinks(description) {
  const doc = new DOMParser().parseFromString(description || '', 'text/html');
  const candidates = [...doc.querySelectorAll('a[href]')].map((a) => a.href);
  candidates.push(...(description || '').match(/https?:\/\/[^\s<>"']+/g) || []);
  return [...new Set(candidates.map((url) => ({ url, id: youtubeId(url) })).filter((item) => item.id))];
}

function safeText(value) {
  return String(value ?? '');
}

function formatMoney(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function estimateTooltip(estimate) {
  if (!estimate) return 'No matching local chart file was found, so there is no mapping-time estimate.';
  const parts = [`${formatMoney(estimate.base)} base`, `${formatMoney(estimate.serviceFee)} service fee`];
  for (const item of estimate.difficulties || []) {
    const raw = Number(item.mappingTimeSeconds || 0) / 600;
    const math = item.minimumApplied
      ? `${item.name}: max(${raw.toFixed(2)} × $1, $2 minimum) = ${formatMoney(item.cost)}`
      : `${item.name}: ${Number(item.mappingTimeSeconds).toLocaleString()}s ÷ 600s × $1 = ${formatMoney(item.cost)}`;
    parts.push(math);
  }
  const albumNote = estimate.albumDiscountApplied
    ? ` Album pricing uses ${formatMoney(estimate.base)} base because ${estimate.albumSongCount} matching songs from this album were found.`
    : '';
  return `Estimated math: ${parts.join(' + ')} = ${formatMoney(estimate.total)}.${albumNote} Rough estimate only.`;
}

function safeCoverUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname === 'paradb.net' ? url.href : null;
  } catch { return null; }
}

function render() {
  const needle = search.value.trim().toLocaleLowerCase();
  const shown = charts.filter((chart) => `${chart.title} ${chart.artist}`.toLocaleLowerCase().includes(needle));
  count.textContent = `${shown.length} ${shown.length === 1 ? 'chart' : 'charts'}`;
  gallery.replaceChildren();
  statusEl.textContent = shown.length ? '' : 'No charts match that search.';

  for (const chart of shown) {
    const card = document.createElement('article');
    card.className = 'card';
    const coverUrl = safeCoverUrl(chart.coverUrl);
    if (coverUrl) card.style.setProperty('--cover-image', `url("${coverUrl}")`);

    const video = document.createElement('div');
    video.className = 'video';
    const iframe = document.createElement('iframe');
    iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(chart.video.id)}`;
    iframe.title = `${safeText(chart.artist)} — ${safeText(chart.title)} video preview`;
    iframe.loading = 'lazy';
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    iframe.allowFullscreen = true;
    video.append(iframe);

    const body = document.createElement('div');
    body.className = 'card-body';
    const artist = document.createElement('p');
    artist.className = 'artist';
    artist.textContent = safeText(chart.artist);
    const titleRow = document.createElement('div');
    titleRow.className = 'title-row';
    const title = document.createElement('h2');
    title.textContent = safeText(chart.title);
    titleRow.append(title);

    const meta = document.createElement('div');
    meta.className = 'card-meta';
    const date = document.createElement('span');
    date.className = 'date';
    date.textContent = chart.submissionDate ? new Date(chart.submissionDate).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
    meta.append(date);

    const estimate = document.createElement('span');
    estimate.className = chart.estimate ? 'price-estimate' : 'price-estimate missing';
    estimate.tabIndex = 0;
    if (chart.estimate) {
      estimate.textContent = `~${formatMoney(chart.estimate.total)}`;
    } else {
      estimate.textContent = 'Estimate unavailable';
    }
    const tooltip = estimateTooltip(chart.estimate);
    estimate.title = tooltip;
    estimate.setAttribute('aria-label', tooltip);
    const tooltipText = document.createElement('span');
    tooltipText.className = 'price-tooltip';
    tooltipText.setAttribute('role', 'tooltip');
    tooltipText.textContent = tooltip;
    estimate.append(tooltipText);
    meta.append(estimate);

    const links = document.createElement('div');
    links.className = 'card-links';
    const chartLink = document.createElement('a');
    chartLink.href = `https://paradb.net/map/${encodeURIComponent(chart.id)}`;
    chartLink.target = '_blank';
    chartLink.rel = 'noreferrer';
    chartLink.textContent = 'View chart ↗';
    const videoLink = document.createElement('a');
    videoLink.href = chart.video.url;
    videoLink.target = '_blank';
    videoLink.rel = 'noreferrer';
    videoLink.textContent = 'Open video ↗';
    links.append(chartLink, videoLink);
    body.append(artist, titleRow, meta, links);
    card.append(video, body);
    gallery.append(card);
  }
}

async function load() {
  try {
    const response = await fetch('data/charts.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Gallery data returned HTTP ${response.status}`);
    const payload = await response.json();
    charts = Array.isArray(payload.charts) ? payload.charts : [];
    charts.sort((a, b) => new Date(b.submissionDate || 0) - new Date(a.submissionDate || 0));
    render();
    statusEl.className = 'status';
    if (!charts.length) statusEl.textContent = 'No YouTube previews were found in the latest chart data.';
  } catch (error) {
    count.textContent = 'Gallery data unavailable';
    statusEl.className = 'status error';
    statusEl.textContent = 'Could not load chart data. Please try again later.';
    console.error(error);
  }
}

howButton.addEventListener('click', () => infoDialog.showModal());
closeDialog.addEventListener('click', () => infoDialog.close());
infoDialog.addEventListener('click', (event) => {
  if (event.target === infoDialog) infoDialog.close();
});
search.addEventListener('input', render);
load();
