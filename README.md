# AlexFDR ParaDB Video Gallery

A static GitHub Pages gallery for YouTube previews in ParaDB charts uploaded by U9EAF8A, with gaps filled by AlexFDR's ParaCommsDB charts. It also lists AlexFDR's downloadable ParaCommsDB kits and Paradiddle mods from Thunderstore.

## Features

- Finds YouTube links in chart descriptions and refreshes the gallery daily.
- Uses ParaDB as the primary chart source; ParaCommsDB only fills songs that ParaDB lacks, deduplicated by song and YouTube video ID.
- Caches ParaDB or ParaCommsDB cover art locally and uses it for each video card's thumbnail and background.
- Lists AlexFDR's four ParaCommsDB kits with previews and `.rlrr` download links.
- Fetches live ParaCommsDB listings/details and falls back to the seven-day cache only when the site is unavailable; the cache lives outside the published site files. Cover images are cached in `data/covers/` and restored from the Actions cache.
- Loads a YouTube embed only after its cached cover thumbnail is clicked.
- Shows rough price estimates for locally matched charts using the saved Expert mappingTime; AutoSaves are excluded.
- Fetches AlexFDR's Paradiddle mod listings from Thunderstore's community package API.
- Opens the pricing explanation from the button beside the search field.
- Uses a locally vendored Bootstrap 5.3 stylesheet for the responsive grid, forms, buttons, and utilities; the dark gallery theme remains in `styles.css`.

## Estimate calculation

The site treats mappingTime as seconds, based on five-minute autosave increments in the local chart files. It rounds Expert mapping time to the nearest ten minutes at $1 per ten minutes, with a $2 minimum. Each additional difficulty adds $2. The estimate adds a $2 service fee and a $20 base, or $10 per song for albums represented by at least six matched gallery songs. Prices are rounded to whole dollars and are rough estimates, not quotes.

## Publish

The Refresh gallery and publish GitHub Actions workflow builds and deploys the site when main changes, on a daily schedule, or when manually started. In repository settings, Pages must use GitHub Actions as the publishing source.

The workflow fetches ParaDB's public `/api/maps` endpoint and Thunderstore's Paradiddle community package endpoint. It filters ParaDB maps by uploader ID, extracts YouTube links from chart descriptions, and filters mods by owner name. ParaCommsDB has no public JSON API, so the workflow reads its public HTML pages with a throttled request and a seven-day detail cache. No API keys are used.
