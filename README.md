# AlexFDR ParaDB Video Gallery

A static GitHub Pages gallery for YouTube previews in ParaDB charts uploaded by `U9EAF8A`.

## Publish

The `Refresh gallery and publish` GitHub Actions workflow builds and deploys the site when `main` changes, on a daily schedule, or when manually started. In repository settings, open **Pages** and select **GitHub Actions** as the source if GitHub asks you to configure publishing.

The workflow fetches ParaDB's public `/api/maps` endpoint, follows pagination, filters by uploader ID, and extracts YouTube links from each chart description. It uses no API keys.
