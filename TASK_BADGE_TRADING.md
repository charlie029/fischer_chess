# Task: Badge Trading System

## Context

Fischer Chess is a Flask web app at `/Users/linchai/chess-puzzle-generator/`. It has 7 badge categories (54 total badges) earned by solving puzzles. Badges are currently display-only on the player stats page. This task adds a badge trading system between users.

**Deployed to:** AWS Lightsail at http://44.249.248.55:5001  
**DB:** SQLite (`fischer.db`)  
**Auth:** Session-based password gate (FISCHER_PASSWORD env var)

## Goal

Let users trade duplicate/unwanted badges with each other, adding a social/collectible layer to the puzzle-solving experience.

## Design Decisions Needed

Before implementing, confirm these with the user:

1. **Trading model:** Should users trade badge-for-badge (1:1 swap), or can badges be "gifted" one-way too?
2. **Duplicate badges:** Users currently can't earn the same badge twice. Should trading require a "duplicate" system (earn a badge twice to have one tradeable copy), or can users trade away their only copy?
3. **Trade initiation:** Should trades happen via:
   - (a) A "trade board" where users post badges they want to give/receive, and others browse and accept
   - (b) Direct user-to-user trade proposals (select a user, propose a swap)
   - (c) Both
4. **Badge rarity:** Should higher-tier / mystery badges be untradeable to preserve their prestige?
5. **Trade history:** Should there be a visible log of past trades?

## Requirements

### Database Changes (`db.py`)

- [ ] Create `trades` table:
  ```sql
  CREATE TABLE IF NOT EXISTS trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      proposer_id INTEGER NOT NULL,
      responder_id INTEGER NOT NULL,
      proposer_badge_id INTEGER NOT NULL,
      responder_badge_id INTEGER,          -- NULL if gift (one-way)
      status TEXT DEFAULT 'pending',       -- pending, accepted, rejected, cancelled
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      resolved_at TIMESTAMP,
      FOREIGN KEY (proposer_id) REFERENCES users(id),
      FOREIGN KEY (responder_id) REFERENCES users(id),
      FOREIGN KEY (proposer_badge_id) REFERENCES badges(id),
      FOREIGN KEY (responder_badge_id) REFERENCES badges(id)
  );
  ```
- [ ] Add migration in `init_db()` to create the table
- [ ] Add `tradeable` column to `badges` table (BOOLEAN DEFAULT 1) — allows marking certain badges as untradeable

### Backend (`app.py`)

- [ ] `GET /api/trades` — list pending trades for current user (incoming + outgoing)
- [ ] `POST /api/trades` — propose a trade `{responder_username, my_badge_id, want_badge_id}`
- [ ] `POST /api/trades/<id>/accept` — accept a pending trade (swaps badge ownership in a transaction)
- [ ] `POST /api/trades/<id>/reject` — reject a pending trade
- [ ] `POST /api/trades/<id>/cancel` — cancel own pending trade
- [ ] `GET /api/users/<username>/badges` — view another user's badge collection (public)
- [ ] Badge swap logic: UPDATE badges SET user_id = ... in a single transaction, rollback on any failure
- [ ] Validation: can't trade with yourself, can't trade a badge you don't own, can't accept a trade where responder doesn't own the requested badge

### Frontend (`templates/index.html` or new `templates/trading.html`)

- [ ] Trading page or modal accessible from the stats page
- [ ] "Browse Users" — see other users' earned badges
- [ ] "Propose Trade" — select one of your badges + one of theirs → submit
- [ ] "My Trades" panel — pending incoming (accept/reject) and outgoing (cancel)
- [ ] Visual: badge cards with name, image, category label
- [ ] Toast notification when a trade is accepted

### Badge System Updates (`badges.py`)

- [ ] Add `UNTRADEABLE_CATEGORIES` config (e.g., mystery-tier badges, or specific categories)
- [ ] Helper function `is_tradeable(badge_type, tier)` checking against config

### Testing

- [ ] Trade proposal creates a pending record
- [ ] Accepting a trade swaps user_id on both badges atomically
- [ ] Rejecting/cancelling sets status correctly
- [ ] Cannot trade untradeable badges
- [ ] Cannot accept a trade if badge ownership changed since proposal
- [ ] Cannot trade with yourself

## Acceptance Criteria

1. User A can see User B's badges on the stats page
2. User A can propose a badge swap with User B
3. User B sees the incoming trade and can accept or reject
4. On accept, badges swap owners and appear in each user's collection
5. Trade history is visible
6. Mystery-tier badges (above `mystery_from` threshold) are untradeable by default
7. All trades are atomic — no badge duplication or loss on failure

## Files to Modify

- `db.py` — new table + migration + trade queries
- `app.py` — new API routes
- `badges.py` — tradeability config + helper
- `templates/player.html` — trading UI (or new template)
- `templates/index.html` — trade notification badge count (optional)

## Out of Scope

- Real-time notifications (polling is fine for MVP)
- Badge marketplace with pricing/currency
- Cross-instance trading
