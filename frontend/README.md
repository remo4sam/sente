# Sente — Frontend

Next.js 15 + TypeScript + Tailwind + shadcn/ui. Talks to the FastAPI backend.

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # defaults to http://localhost:8000
npm run dev
```

Then open http://localhost:3000.

The backend must be running separately — see `../backend/README` for that.

## Structure

```
app/
├── layout.tsx         Root layout with sidebar nav
├── page.tsx           Dashboard (/)
├── upload/page.tsx    Upload PDF or paste SMS (/upload)
├── transactions/      Transaction table with inline category correction (/transactions)
└── chat/              Natural-language Q&A (/chat)

components/
├── ui/                shadcn/ui primitives
├── app-nav.tsx        Sidebar navigation
├── upload-form.tsx    PDF + SMS ingest form
├── transaction-table.tsx
├── category-badge.tsx
├── chat-panel.tsx     Chat with tool-call trace
└── dashboard.tsx      Stats + charts

lib/
├── api.ts             Typed backend client
├── types.ts           Mirrors backend Pydantic schemas
├── format.ts          UGX / date formatters
└── utils.ts           cn() helper
```

## Scripts

- `npm run dev` — Next dev server on port 3000
- `npm run build` — production build
- `npm run start` — serve production build
- `npm run lint` — ESLint
- `npm run typecheck` — tsc without emit

## Notes

- The category select is a native `<select>` rather than Radix to keep the
  dependency tree small. Swap in `@radix-ui/react-select` if you want keyboard-nav
  Combobox behavior.
- Charts use Recharts. Tremor is an option if you want more finance-specific
  components later.
- Dashboard aggregates are computed client-side from `GET /transactions?limit=1000`.
  For larger datasets, add aggregate endpoints to the backend.
