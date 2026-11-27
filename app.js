const gallery = document.querySelector('#gallery');
const statusEl = document.querySelector('#status');
const modsGallery = document.querySelector('#mods-gallery');
const modsStatus = document.querySelector('#mods-status');
const kitsGallery = document.querySelector('#kits-gallery');
const kitsStatus = document.querySelector('#kits-status');
const videosPage = document.querySelector('#videos-page');
const modsPage = document.querySelector('#mods-page');
const kitsPage = document.querySelector('#kits-page');
const videosTab = document.querySelector('#videos-tab');
const modsTab = document.querySelector('#mods-tab');
const kitsTab = document.querySelector('#kits-tab');
const pageTitle = document.querySelector('#page-title');
const searchLabel = document.querySelector('#search-label');
const search = document.querySelector('#search');
const count = document.querySelector('#count');
const howButton = document.querySelector('#how-button');
const infoDialog = document.querySelector('#info-dialog');
const closeDialog = document.querySelector('#close-dialog');
let charts = [];
let mods = [];
let kits = [];
let activePage = 'videos';

const IMAGE_HOSTS = new Set(['i.ytimg.com', 'paradb.net', 'paracommsdb.fencil.xyz', 'thunderstore.io']);

function safeText(value) {
  return String(value ?? '');
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return safeText(value);
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatMoney(value) {
  return `$${Math.round(Number(value || 0))}`;
}

function estimateTooltipItems(estimate, unavailableReason) {
  if (!estimate) {
    return [{ label: 'Estimate unavailable', value: unavailableReason || 'No matching local chart file was found.' }];
  }
  const otherCount = Number(estimate.otherDifficultyCount || 0);
  return [
    {
      label: 'Base + service fee',
      value: `${formatMoney(estimate.base)} + ${formatMoney(estimate.serviceFee)} = ${formatMoney(Number(estimate.base) + Number(estimate.serviceFee))}`,
    },
    {
      label: 'Expert',
      value: `${Number(estimate.expertMinutesRounded)} min × $1/10 min = ${formatMoney(estimate.expertCost)}`,
    },
    {
      label: 'Difficulties',
      value: otherCount ? `${otherCount} × $2 = ${formatMoney(estimate.otherDifficultyCost)}` : `None = ${formatMoney(0)}`,
    },
    { label: 'Total', value: formatMoney(estimate.total), total: true },
  ];
}

function safeImageUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && IMAGE_HOSTS.has(url.hostname) ? url.href : null;
  } catch { return null; }
}

function safeLocalAsset(value) {
  const text = String(value ?? '');
  return /^data\/covers\/[A-Za-z0-9._-]+$/.test(text) ? text : null;
}

function safeCoverUrl(value) {
  return safeLocalAsset(value) || safeImageUrl(value);
}

function positionPriceTooltip(estimate) {
  const tooltip = estimate.querySelector('.price-tooltip');
  if (!tooltip) return;
  const rect = estimate.getBoundingClientRect();
  const width = Math.max(120, Math.min(360, window.innerWidth - 24));
  const clampedLeft = Math.min(Math.max(rect.left, 12), window.innerWidth - width - 12);
  tooltip.style.left = `${clampedLeft - rect.left}px`;
  tooltip.style.right = 'auto';
}

function positionAllPriceTooltips() {
  document.querySelectorAll('.price-estimate').forEach(positionPriceTooltip);
}

function appendGalleryCard(container, card) {
  const column = document.createElement('div');
  column.className = 'col d-flex';
  column.append(card);
  container.append(column);
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

  const coverUrl = safeCoverUrl(chart.coverUrl);
  const youtubeThumb = (size) => `https://i.ytimg.com/vi/${encodeURIComponent(chart.video.id)}/${size}.jpg`;
  const thumbnail = document.createElement('img');
  thumbnail.src = coverUrl || youtubeThumb('hqdefault');
  thumbnail.alt = '';
  thumbnail.loading = 'lazy';
  thumbnail.decoding = 'async';
  thumbnail.addEventListener('error', () => {
    if (!thumbnail.src.includes('/mqdefault.jpg')) {
      thumbnail.src = youtubeThumb('mqdefault');
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

function renderVideos() {
  const needle = search.value.trim().toLocaleLowerCase();
  const shown = charts.filter((chart) => `${chart.title} ${chart.artist}`.toLocaleLowerCase().includes(needle));
  if (activePage === 'videos') count.textContent = `${shown.length} ${shown.length === 1 ? 'chart' : 'charts'}`;
  gallery.replaceChildren();
  statusEl.textContent = shown.length ? '' : 'No charts match that search.';

  for (const chart of shown) {
    const card = document.createElement('article');
    card.className = 'card h-100 w-100';
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
    date.textContent = formatDate(chart.submissionDate);
    meta.append(date);

    const estimate = document.createElement('span');
    estimate.className = chart.estimate ? 'price-estimate' : 'price-estimate missing';
    estimate.tabIndex = 0;
    estimate.textContent = chart.estimate ? `~${formatMoney(chart.estimate.total)} estimate` : 'Estimate unavailable';
    const tooltipLines = estimateTooltipItems(chart.estimate, chart.estimateUnavailableReason);
    estimate.setAttribute('aria-label', tooltipLines.map((line) => `${line.label}: ${line.value}`).join('. '));
    estimate.addEventListener('mouseenter', () => positionPriceTooltip(estimate));
    estimate.addEventListener('focus', () => positionPriceTooltip(estimate));
    const tooltipText = document.createElement('span');
    tooltipText.className = 'price-tooltip';
    tooltipText.setAttribute('role', 'tooltip');
    for (const item of tooltipLines) {
      const line = document.createElement('span');
      line.className = item.total ? 'tooltip-line tooltip-total' : 'tooltip-line';
      const label = document.createElement('span');
      label.textContent = item.label;
      const value = document.createElement('strong');
      value.textContent = item.value;
      line.append(label, value);
      tooltipText.append(line);
    }
    estimate.append(tooltipText);
    meta.append(estimate);

    const links = document.createElement('div');
    links.className = 'card-links';
    const chartLink = document.createElement('a');
    chartLink.href = safeExternalUrl(chart.chartUrl) || `https://paradb.net/map/${encodeURIComponent(chart.id)}`;
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
    appendGalleryCard(gallery, card);
    positionPriceTooltip(estimate);
  }
}

async function loadVideos() {
  try {
    const response = await fetch('data/charts.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Gallery data returned HTTP ${response.status}`);
    const payload = await response.json();
    charts = Array.isArray(payload.charts) ? payload.charts : [];
    charts.sort((a, b) => new Date(b.submissionDate || 0) - new Date(a.submissionDate || 0));
    renderVideos();
    statusEl.className = 'status';
    if (!charts.length) statusEl.textContent = 'No YouTube previews were found in the latest chart data.';
  } catch (error) {
    count.textContent = 'Gallery data unavailable';
    statusEl.className = 'status error';
    statusEl.textContent = 'Could not load chart data. Please try again later.';
    console.error(error);
  }
}

function renderMods() {
  const needle = search.value.trim().toLocaleLowerCase();
  const shown = mods.filter((mod) => `${mod.name} ${mod.owner} ${mod.description} ${(mod.categories || []).join(' ')}`.toLocaleLowerCase().includes(needle));
  if (activePage === 'mods') count.textContent = `${shown.length} ${shown.length === 1 ? 'mod' : 'mods'}`;
  modsGallery.replaceChildren();
  modsStatus.textContent = shown.length ? '' : 'No mods match that search.';

  for (const mod of shown) {
    const card = document.createElement('article');
    card.className = 'card h-100 w-100 mod-card';
    const header = document.createElement('div');
    header.className = 'mod-header';
    const iconUrl = safeExternalUrl(mod.iconUrl);
    if (iconUrl) {
      const icon = document.createElement('img');
      icon.className = 'mod-icon';
      icon.src = iconUrl;
      icon.alt = `${safeText(mod.name)} icon`;
      icon.loading = 'lazy';
      icon.decoding = 'async';
      header.append(icon);
    } else {
      const fallback = document.createElement('div');
      fallback.className = 'mod-icon mod-icon-fallback';
      fallback.setAttribute('aria-hidden', 'true');
      fallback.textContent = safeText(mod.name).slice(0, 1).toUpperCase() || 'M';
      header.append(fallback);
    }
    const heading = document.createElement('div');
    heading.className = 'mod-heading';
    const owner = document.createElement('p');
    owner.className = 'artist';
    owner.textContent = safeText(mod.owner);
    const name = document.createElement('h2');
    name.textContent = safeText(mod.name);
    heading.append(owner, name);
    header.append(heading);

    const details = document.createElement('div');
    details.className = 'mod-details';
    const description = document.createElement('p');
    description.className = 'mod-description';
    description.textContent = safeText(mod.description) || 'No description provided.';
    const metadata = document.createElement('div');
    metadata.className = 'mod-meta';
    if (mod.version) {
      const version = document.createElement('span');
      version.className = 'mod-tag';
      version.textContent = `v${safeText(mod.version)}`;
      metadata.append(version);
    }
    if (Number.isFinite(Number(mod.downloads))) {
      const downloads = document.createElement('span');
      downloads.className = 'mod-tag';
      downloads.textContent = `${Number(mod.downloads).toLocaleString()} downloads`;
      metadata.append(downloads);
    }
    for (const category of (mod.categories || []).slice(0, 3)) {
      const tag = document.createElement('span');
      tag.className = 'mod-tag';
      tag.textContent = safeText(category);
      metadata.append(tag);
    }
    const links = document.createElement('div');
    links.className = 'card-links mod-links';
    const packageLink = document.createElement('a');
    packageLink.href = safeExternalUrl(mod.packageUrl) || `https://thunderstore.io/c/paradiddle/p/${encodeURIComponent(mod.owner)}/${encodeURIComponent(mod.name)}/`;
    packageLink.target = '_blank';
    packageLink.rel = 'noreferrer';
    packageLink.textContent = 'View on Thunderstore ↗';
    links.append(packageLink);
    const downloadUrl = safeExternalUrl(mod.downloadUrl);
    if (downloadUrl) {
      const download = document.createElement('a');
      download.href = downloadUrl;
      download.target = '_blank';
      download.rel = 'noreferrer';
      download.textContent = 'Latest download ↗';
      links.append(download);
    }
    details.append(description, metadata, links);
    card.append(header, details);
    appendGalleryCard(modsGallery, card);
  }
}

function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : null;
  } catch { return null; }
}

async function loadMods() {
  try {
    const response = await fetch('data/mods.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Thunderstore data returned HTTP ${response.status}`);
    const payload = await response.json();
    mods = Array.isArray(payload.mods) ? payload.mods : [];
    if (activePage === 'mods') renderMods();
    modsStatus.className = 'status';
    if (!mods.length) modsStatus.textContent = 'No Thunderstore mods by AlexFDR were found.';
  } catch (error) {
    modsStatus.className = 'status error';
    modsStatus.textContent = 'Could not load the Thunderstore mod list. Please try again later.';
    console.error(error);
  }
}

function renderKits() {
  const needle = search.value.trim().toLocaleLowerCase();
  const shown = kits.filter((kit) => `${kit.name} ${kit.owner} ${kit.description}`.toLocaleLowerCase().includes(needle));
  if (activePage === 'kits') count.textContent = `${shown.length} ${shown.length === 1 ? 'kit' : 'kits'}`;
  kitsGallery.replaceChildren();
  kitsStatus.textContent = shown.length ? '' : 'No kits match that search.';

  for (const kit of shown) {
    const card = document.createElement('article');
    card.className = 'card h-100 w-100 kit-card';

    const images = (kit.images || []).map(safeImageUrl).filter(Boolean).slice(0, 1);
    if (images.length) {
      const imageRow = document.createElement('div');
      imageRow.className = 'kit-images';
      images.forEach((src, index) => {
        const image = document.createElement('img');
        image.className = 'kit-image';
        image.src = src;
        image.alt = index === 0 ? `${safeText(kit.name)} kit preview` : '';
        image.loading = 'lazy';
        image.decoding = 'async';
        image.addEventListener('error', () => image.remove(), { once: true });
        imageRow.append(image);
      });
      card.append(imageRow);
    }

    const body = document.createElement('div');
    body.className = 'card-body kit-body';
    const owner = document.createElement('p');
    owner.className = 'artist';
    owner.textContent = safeText(kit.owner);

    const titleRow = document.createElement('div');
    titleRow.className = 'title-row';
    const name = document.createElement('h2');
    name.textContent = safeText(kit.name);
    titleRow.append(name);

    const description = document.createElement('p');
    description.className = 'kit-description';
    description.textContent = safeText(kit.description) || 'No description provided.';

    const metadata = document.createElement('div');
    metadata.className = 'mod-meta kit-meta';
    const pieces = Number(kit.pieces);
    if (kit.pieces != null && Number.isFinite(pieces)) {
      const tag = document.createElement('span');
      tag.textContent = `${pieces} pieces`;
      metadata.append(tag);
    }
    const downloads = Number(kit.downloads);
    if (Number.isFinite(downloads)) {
      const tag = document.createElement('span');
      tag.textContent = `${downloads.toLocaleString()} downloads`;
      metadata.append(tag);
    }
    const uploaded = formatDate(kit.uploadedAt);
    if (uploaded) {
      const tag = document.createElement('span');
      tag.textContent = `Added ${uploaded}`;
      metadata.append(tag);
    }

    const links = document.createElement('div');
    links.className = 'card-links';
    const kitUrl = safeExternalUrl(kit.kitUrl);
    if (kitUrl) {
      const link = document.createElement('a');
      link.href = kitUrl;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = 'View on ParaCommsDB ↗';
      links.append(link);
    }
    const downloadUrl = safeExternalUrl(kit.downloadUrl);
    if (downloadUrl) {
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = 'Download .rlrr ↗';
      links.append(link);
    }

    body.append(owner, titleRow, description, metadata, links);
    card.append(body);
    appendGalleryCard(kitsGallery, card);
  }
}

async function loadKits() {
  try {
    const response = await fetch('data/kits.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Kit data returned HTTP ${response.status}`);
    const payload = await response.json();
    kits = Array.isArray(payload.kits) ? payload.kits : [];
    if (activePage === 'kits') renderKits();
    kitsStatus.className = 'status';
    if (!kits.length) kitsStatus.textContent = 'No ParaCommsDB kits were found.';
  } catch (error) {
    if (activePage === 'kits') count.textContent = 'Kit data unavailable';
    kitsStatus.className = 'status error';
    kitsStatus.textContent = 'Could not load the kit list. Please try again later.';
    console.error(error);
  }
}

function selectPage(page) {
  activePage = page;
  const showingVideos = page === 'videos';
  const showingMods = page === 'mods';
  const showingKits = page === 'kits';
  document.title = showingMods
    ? 'AlexFDR — Mods'
    : showingKits
      ? 'AlexFDR — Kits'
      : 'AlexFDR — ParaDB Video Gallery';
  videosPage.hidden = !showingVideos;
  modsPage.hidden = !showingMods;
  kitsPage.hidden = !showingKits;
  videosTab.classList.toggle('is-active', showingVideos);
  modsTab.classList.toggle('is-active', showingMods);
  kitsTab.classList.toggle('is-active', showingKits);

  for (const tab of [videosTab, modsTab, kitsTab]) tab.removeAttribute('aria-current');
  (showingMods ? modsTab : showingKits ? kitsTab : videosTab).setAttribute('aria-current', 'page');

  if (showingMods) {
    pageTitle.textContent = 'AlexFDR’s mods';
    searchLabel.textContent = 'Find a mod';
    search.placeholder = 'Search mods…';
    howButton.hidden = true;
    renderMods();
  } else if (showingKits) {
    pageTitle.textContent = 'AlexFDR’s kits';
    searchLabel.textContent = 'Find a kit';
    search.placeholder = 'Search kits…';
    howButton.hidden = true;
    renderKits();
  } else {
    pageTitle.textContent = 'AlexFDR’s charts';
    searchLabel.textContent = 'Find a song or artist';
    search.placeholder = 'Search the gallery…';
    howButton.hidden = false;
    renderVideos();
  }
}

videosTab.addEventListener('click', () => selectPage('videos'));
modsTab.addEventListener('click', () => selectPage('mods'));
kitsTab.addEventListener('click', () => selectPage('kits'));
if (window.location.hash === '#mods') selectPage('mods');
if (window.location.hash === '#kits') selectPage('kits');
search.addEventListener('input', () => {
  if (activePage === 'mods') renderMods();
  else if (activePage === 'kits') renderKits();
  else renderVideos();
});
howButton.addEventListener('click', () => infoDialog.showModal());
if (window.location.hash === '#how') {
  infoDialog.showModal();
}
closeDialog.addEventListener('click', () => infoDialog.close());
infoDialog.addEventListener('click', (event) => {
  if (event.target === infoDialog) infoDialog.close();
});
window.addEventListener('resize', positionAllPriceTooltips, { passive: true });
loadVideos();
loadMods();
loadKits();
