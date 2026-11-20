# AlexFDR ParaDB Video Gallery

A static GitHub Pages gallery for YouTube previews in ParaDB charts uploaded by `U9EAF8A`.

## Features

- Finds YouTube links in chart descriptions and refreshes the gallery daily.
- Uses ParaDB album art as each card's background.
- Loads a YouTube embed only after its thumbnail is clicked.
- Shows rough price estimates for locally matched charts. Estimates use the Expert file's saved `mappingTime`; AutoSaves are excluded.
- Opens the pricing explanation from the button beside the search field.

## Estimate calculation

The site treats `mappingTime` as seconds, based on five-minute autosave increments in the local chart files. It rounds Expert mapping time to the nearest ten minutes at $1 per ten minutes, with a $2 minimum. Each additional difficulty adds $2. The calculation adds a $2 service fee and a $20 base rate, or $10 per song for albums represented by at least six matched gallery songs. Prices are rounded to whole dollars and are rough estimates, not quotes.

## Publish

The `Refresh gallery and publish` GitHub Actions workflow builds and deploys the site when `main` changes, on a daily schedule, or when manually started. In repository settings, open **Pages** and select **GitHub Actions** as the source if GitHub asks you to configure publishing.

The workflow fetches ParaDB's public `/api/maps` endpoint, follows pagination, filters by uploader ID, and extracts YouTube links from each chart description. It uses no API keys.
