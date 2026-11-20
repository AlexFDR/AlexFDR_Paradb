const gallery = document.querySelector('#gallery');
const statusEl = document.querySelector('#status');
const search = document.querySelector('#search');
const count = document.querySelector('#count');
const howButton = document.querySelector('#how-button');
const infoDialog = document.querySelector('#info-dialog');
const closeDialog = document.querySelector('#close-dialog');
let charts = [];

function safeText(value) {
  return String(value ?? '');
}

function formatMoney(value) {
  return `$${Math.round(Number(value || 0))}`;
}

function estimateTooltip(estimate, unavailableReason) {
  if (!estimate) return unavailableReason || 'No matching local chart file was found, so there is no mapping-time estimate.';
  const base = `${formatMoney(estimate.base)} base (${estimate.baseReason || 'estimated rate'})`;
  const service = `${formatMoney(estimate.serviceFee)} service fee`;
  const expert = `Expert: ${Number(estimate.expertMinutesRounded)} min → ${formatMoney(estimate.expertCost)}`;
  const otherCount = Number(estimate.otherDifficultyCount || 0);
  const extras = otherCount ? `${otherCount} additional ${otherCount === 1 ? 'difficulty' : 'difficulties'} × ${formatMoney(2)} = ${formatMoney(estimate.otherDifficultyCost)}` : '';
  const albumNote = estimate.albumDiscountApplied
    ? ` Album base is ${formatMoney(estimate.base)} because ${estimate.albumSongCount} matching songs from this album were found.`
    : '';
  return `Math: ${[base, service, expert, extras].filter(Boolean).join(' + ')} = ${formatMoney(estimate.total)}.${albumNote} Rough estimate only.`;
}

function safeCoverUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname === 'paradb.net' ? url.href : null;
  } catch { return null; }
}

function positionPriceTooltip(estimate) {
  const tooltip = estimate.querySelector('.price-tooltip');
  if (!tooltip) return;
  const rect = estimate.getBoundingClientRect();
  const width = Math.min(330, window.innerWidth - 40);
  tooltip.classList.toggle('align-right', rect.left + width > window.innerWidth - 12);
}


function createIframe(chart) {
  const iframe = document.createElement('iframe');
  iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(chart.video.id)}?autoplay=1&playsinline=1`;
  iframe.title = `${safeText(chart.artist)} — ${safeText(chart.title)} video preview`;
  iframe.loading = 'lazy';
  iframe.referrerPolicy = 'strict-origin-when-cross-origin';
  iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
  iframe.allowFullscreen = true;
  return iframe;
}

function createVideoFacade(chart, video) {
  const facade = document.createElement('button');
  facade.type = 'button';
  facade.className = 'video-facade';
  facade.setAttribute('aria-label', `Play video preview for ${safeText(chart.artist)} — ${safeText(chart.title)}`);

  const thumbnail = document.createElement('img');
  thumbnail.src = `https://i.ytimg.com/vi/${encodeURIComponent(chart.video.id)}/hqdefault.jpg`;
  thumbnail.alt = '';
  thumbnail.loading = 'lazy';
  thumbnail.decoding = 'async';
  thumbnail.addEventListener('error', () => {
    if (!thumbnail.src.includes('/mqdefault.jpg')) {
      thumbnail.src = `https://i.ytimg.com/vi/${encodeURIComponent(chart.video.id)}/mqdefault.jpg`;
    }
  }, { once: true });

  const play = document.createElement('span');
  play.className = 'video-play';
  play.setAttribute('aria-hidden', 'true');
  play.textContent = '▶';

  facade.append(thumbnail, play);
  facade.addEventListener('click', () => video.replaceChildren(createIframe(chart)), { once: true });
  video.append(facade);
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
    if (coverUrl) {
      const cover = document.createElement('img');
      cover.className = 'card-cover';
      cover.src = coverUrl;
      cover.alt = '';
      cover.setAttribute('aria-hidden', 'true');
      cover.loading = 'lazy';
      cover.decoding = 'async';
      card.append(cover);
    }

    const video = document.createElement('div');
    video.className = 'video';
    createVideoFacade(chart, video);

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
    estimate.textContent = chart.estimate ? `~${formatMoney(chart.estimate.total)} estimate` : 'Estimate unavailable';
    const tooltip = estimateTooltip(chart.estimate, chart.estimateUnavailableReason);
      estimate.setAttribute('aria-label', tooltip);
    estimate.addEventListener('mouseenter', () => positionPriceTooltip(estimate));
    estimate.addEventListener('focus', () => positionPriceTooltip(estimate));
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
