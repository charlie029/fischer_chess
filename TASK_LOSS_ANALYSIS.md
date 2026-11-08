# Task: Game Loss Analysis Feature

## Overview
Analyze a Lichess or Chess.com account's games over a configurable time period. For each lost game, classify HOW the game was lost (one-move blunder, gradual decline, opening disaster, endgame collapse, time trouble, tactical sequence). Summarize loss patterns across time on a dedicated summary page.

## Scope
- Add Lichess import support (new — currently only Chess.com)
- Add loss analysis engine that classifies each lost game
- Add new DB tables for loss analysis results
- Add summary page showing loss pattern distribution over time
- Integrate into existing player profile page

## Data Sources

### Lichess API
- Endpoint: `GET https://lichess.org/api/games/user/{username}`
- Params: `since`/`until` (ms timestamps), `evals=true`, `clocks=true`, `opening=true`
- Format: NDJSON (`Accept: application/x-ndjson`) — includes `analysis` array with per-move evals
- No auth required for public games
- Rate limit: ~20 req/sec (generous)
- Library: `berserk`
- Key advantage: server-side Stockfish evals included for many games (no local analysis needed)

### Chess.com API (existing)
- Already integrated via `/api/db/users/<username>/import`
- No move-by-move evals — requires local Stockfish analysis
- Rate limit: ~1 req/sec

## Loss Categories

| Category | Criteria | Description |
|----------|----------|-------------|
| `one_move_blunder` | Single move ≥3.0 pawn loss, position was ≥-1.0 before | Game decided by one catastrophic mistake |
| `opening_disaster` | Blunder(s) in first 15 moves, eval drops below -2.0 | Lost material/position early in the opening |
| `gradual_decline` | No single large blunder, eval drifts steadily negative | Death by a thousand cuts — outplayed positionally |
| `endgame_collapse` | Position holdable at midgame, errors in final phase | Had a good/even position but collapsed in the endgame |
| `time_trouble` | Blunders with <30s on clock in last 10 moves | Lost due to time pressure (requires clock data) |
| `tactical_sequence` | 2+ blunders within 5 moves of each other | Lost through a rapid sequence of tactical errors |
| `never_had_a_chance` | Eval below -1.0 from move 5 onwards | Was losing from the start (outrated/out-prepared) |

## Move Classification Thresholds (Lichess standard)
- Best: <10 cp loss
- Good: 10-49 cp loss
- Inaccuracy: 50-99 cp loss
- Mistake: 100-199 cp loss
- Blunder: ≥200 cp loss

## Database Changes

### New column on `users` table
```sql
ALTER TABLE users ADD COLUMN lichess_username TEXT;
```

### New table: `game_analyses`
```sql
CREATE TABLE IF NOT EXISTS game_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    result TEXT,              -- 'win', 'loss', 'draw'
    user_color TEXT,          -- 'white' or 'black'
    loss_category TEXT,       -- one of the 7 categories above (NULL for wins/draws)
    loss_description TEXT,    -- human-readable explanation
    worst_move_number INTEGER,
    worst_move_san TEXT,
    worst_move_cp_loss INTEGER,
    eval_before_worst REAL,
    eval_after_worst REAL,
    total_blunders INTEGER DEFAULT 0,
    total_mistakes INTEGER DEFAULT 0,
    total_inaccuracies INTEGER DEFAULT 0,
    avg_cp_loss REAL,
    accuracy REAL,            -- percentage (0-100)
    opening_name TEXT,
    time_control TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (game_id) REFERENCES games(id),
    UNIQUE(game_id)
);
CREATE INDEX IF NOT EXISTS idx_analysis_user ON game_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_category ON game_analyses(loss_category);
```

## Backend Implementation

### 1. `loss_analysis.py` — new module
Core analysis engine:
- `analyze_game_for_loss(pgn_text, user_color, lichess_evals=None)` → `GameAnalysis`
  - If lichess_evals provided, use them directly (no Stockfish needed)
  - Otherwise, run local Stockfish at depth 15
  - Classify every move (best/good/inaccuracy/mistake/blunder)
  - Determine loss category using the classification logic
  - Return structured result with all stats

### 2. `lichess_import.py` — new module
- `fetch_lichess_games(username, since, until)` → generator of game dicts
  - Uses `berserk` or direct HTTP with NDJSON parsing
  - Returns structured game data with evals if available
- Integrates with existing `db.save_game()` for storage

### 3. New API endpoints in `app.py`

```
POST /api/db/users/<username>/import-lichess
  Body: { "lichess_username": "...", "from_date": "YYYY-MM-DD", "to_date": "YYYY-MM-DD" }
  → imports games from Lichess into games table

POST /api/db/users/<username>/analyze-losses
  Body: { "from_date": "YYYY-MM-DD", "to_date": "YYYY-MM-DD", "force": false }
  → runs loss analysis on all user's lost games, saves to game_analyses table
  → SSE stream for progress (game X of Y)

GET /api/db/users/<username>/loss-summary
  Params: ?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD
  → returns aggregated loss analysis:
    - loss_category_distribution: { "one_move_blunder": 12, "gradual_decline": 8, ... }
    - loss_category_over_time: [{ "month": "2024-09", "one_move_blunder": 3, ... }]
    - worst_blunders: [top 10 worst single moves]
    - accuracy_trend: [{ "date": ..., "accuracy": ... }]
    - opening_loss_patterns: [{ "opening": "Sicilian", "losses": 5, "top_category": "..." }]

GET /api/db/users/<username>/loss-detail/<game_id>
  → full analysis for a single game
```

### 4. DB module additions (`db.py`)
- `save_game_analysis(...)` — insert into game_analyses
- `get_loss_summary(user_id, from_date, to_date)` — aggregated stats
- `get_loss_detail(game_id)` — single game analysis
- `get_unanalyzed_losses(user_id)` — games needing analysis
- Migration: add `lichess_username` column, create `game_analyses` table

## Frontend Implementation

### Summary page: `/analysis/<username>`
New template `analysis.html` with:

1. **Header**: username, date range picker, "Analyze" button, import buttons (Lichess + Chess.com)
2. **Loss Category Donut Chart**: pie/donut showing distribution of 7 categories
3. **Loss Pattern Over Time**: stacked bar chart (x=month, y=count, color=category)
4. **Accuracy Trend Line**: line chart showing average accuracy over time
5. **Worst Blunders Table**: top 10 worst single moves with position link
6. **Opening Loss Patterns**: which openings lead to which types of losses
7. **Recent Losses Table**: paginated list with category, description, date, opponent

### Player page integration
- Add "Loss Analysis" button on player.html that links to `/analysis/<username>`
- Show mini loss category donut in the stats section

## Dependencies
- `berserk` — Lichess API client (add to requirements.txt)
- `requests` — already available (used for Chess.com import)
- `python-chess` — already available
- Stockfish — already bundled

## Analysis Strategy
1. For Lichess games with `evals=true`: use server-side evals directly (fast, no Stockfish)
2. For Chess.com games and Lichess games without evals: run local Stockfish at depth 15
3. Two-pass optimization: depth 8 scan first, deep analysis only on suspicious moves
4. Progress streaming via SSE for long-running analyses

## Testing Plan
- Unit test loss_analysis.py with known game PGNs for each category
- Test Lichess import with real public accounts
- Test Chess.com analysis path (already have games in DB)
- Test date filtering
- Test summary aggregation queries
- Test frontend chart rendering
- Test edge cases: draws, resignations, timeouts, disconnects
