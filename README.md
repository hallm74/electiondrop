# Election Release Archive

A neutral, source-first browser for the election-integrity document collections released by the White House in July 2026. The application keeps imported originals immutable, assigns stable public identifiers, extracts page-level text, and keeps printed source material separate from editorial metadata.

## Live deployment

- Public site: https://electiondrop.netlify.app
- API: https://electiondrop-api.fly.dev/api/
- Media: Linode Object Storage (`electiondrop-archive`)

The React frontend is deployed on Netlify. Django runs on one 256 MB Fly.io machine configured to suspend when idle and resume on request, and the read-only archive fixture is restored whenever a fresh machine image starts.

For local Fly management without an interactive login, use the app-scoped deploy token stored in macOS Keychain:

```bash
scripts/fly-keychain.sh status
scripts/fly-keychain.sh deploy backend --config backend/fly.toml --remote-only
```

## Local setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/python manage.py migrate && ../.venv/bin/python manage.py runserver
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The public app runs at `http://localhost:5173`, the API at `http://localhost:8000/api/`, and review administration at `http://localhost:8000/admin/`.

## Importing source material

Place ZIPs or PDFs anywhere outside `media/originals` (the included `imports/` directory is convenient), then run:

```bash
cd backend
../.venv/bin/python manage.py import_election_documents ../imports
```

Use collection-coded folders (`vulnerabilities`, `china`, `michigan`, or `noncitizens`) or pass `--collection <slug>`. Re-running the same import is safe: SHA-256 hashes prevent duplicate source records. Imported originals are copied to `media/originals` and are never rewritten by the processing pipeline.

## Production notes

For the current read-only deployment, Fly uses a seeded SQLite database inside the machine image. Administrative changes are not durable across a redeploy. For persistent editing, set `DATABASE_URL` to a PostgreSQL URL. Production disables debug, uses a strong secret, restricts allowed hosts, and serves originals through a read-only media origin. Search uses PostgreSQL full-text ranking when PostgreSQL is configured and a SQLite-compatible fallback otherwise.

### Linode Object Storage

Production media can be served from the `electiondrop-archive` bucket in Chicago. Set these environment variables on the Django host:

```bash
LINODE_S3_BUCKET=electiondrop-archive
LINODE_S3_ENDPOINT=https://us-ord-10.linodeobjects.com
LINODE_S3_CUSTOM_DOMAIN=electiondrop-archive.us-ord-10.linodeobjects.com
LINODE_S3_ACCESS_KEY_ID=...
LINODE_S3_SECRET_ACCESS_KEY=...
```

The access key should be limited to read/write access on this bucket. The bucket policy makes only `media/*` anonymously readable; it does not grant public write access.
