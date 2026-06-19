# Fischer Chess — Chess Puzzle Generator & Trainer

A Python CLI + web app that extracts blunders and missed tactics from your chess games, classifies them by tactic type, and lets you train interactively with a board UI and live engine analysis.

## Features

### Puzzle Generation (CLI)
- Parses PGN files with multiple games
- Runs Stockfish evaluation on every position at configurable depth
- Detects blunders (≥200cp drop) and missed mates
- Classifies each puzzle by tactic type (fork, pin, skewer, discovered attack, etc.)
- Pre-computes acceptable alternative moves (within 50cp of best)
- Filters by player name (case-insensitive partial match)
- Outputs standard PGN with full metadata — openable in Lichess/Chess.com
- Auto-downloads Stockfish binary (macOS ARM, Linux x86, Windows)

### Web UI (Fischer Chess)
- Interactive chessboard with drag-and-drop solving
- Chat-style move input (SAN or UCI notation)
- Three-tier feedback: correct (best move), acceptable (within 50cp), incorrect
- Hint system (highlights source square)
- Free exploration after solving with undo/redo
- Live Stockfish WASM engine analysis (3 MultiPV lines, browser-side)
- In-browser puzzle generation with real-time progress
- Player stats modal with tactic breakdown bar chart
- User profile with persistent stats across sessions

### Tactic Classification
Detects: fork, discovered attack, discovered check, pin, skewer, back rank mate, smothered mate, checkmate, check, capture, promotion, trapped piece, positional.

### Player Stats
- Per-player aggregation across multiple PGN sources
- Tactic breakdown, average centipawn loss, per-game details
- Save to persistent JSON files or compute on-the-fly
- Visual bar chart in the web UI

### Blunder Rate Trends
- Time-series chart of blunder rate (blunders / total moves) per game plotted by date
- 5-game moving average trendline to visualize improvement over time
- Flexible input: puzzle PGN (instant) and/or game PGN (runs Stockfish if no puzzles)
- `GameMoves` header in puzzle output enables fully self-contained trend analysis
- Optional player filter
- Interactive Chart.js chart with hover tooltips showing game details

## Installation

```bash
pip install -r requirements.txt
```

Requirements: `python-chess`, `flask`

Stockfish is auto-downloaded on first run, or provide your own with `--stockfish /path/to/binary`.

## Usage

### Generate Puzzles (CLI)

```bash
# All blunders from a PGN file
python puzzles.py games.pgn -o puzzles.pgn

# Only your blunders, lower threshold, deeper analysis
python puzzles.py games.pgn -p "YourName" -t 150 -d 22 -o my_puzzles.pgn
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `pgn` | — | Input PGN file (positional, required) |
| `-o` / `--output` | `puzzles.pgn` | Output puzzle PGN file |
| `-t` / `--threshold` | 200 | Blunder threshold in centipawns |
| `-d` / `--depth` | 18 | Stockfish search depth |
| `-p` / `--player` | all | Only include this player's blunders |
| `--stockfish` | auto | Path to Stockfish binary |

### Run the Web App

```bash
python app.py
# Open http://localhost:5001
```

### API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/puzzles?file=<name>` | Load puzzles from a PGN file |
| POST | `/api/generate` | Generate puzzles (SSE stream) |
| GET | `/api/stats/live?file=<name>&player=<name>` | Compute stats on-the-fly |
| POST | `/api/stats/generate` | Generate and save player stats |
| GET | `/api/stats/players` | List all saved player profiles |
| GET | `/api/stats/player/<name>` | Get saved stats for a player |
| GET/POST/DELETE | `/api/profile` | Manage active user profile |
| GET | `/api/trends?games=<name>&puzzles=<name>&player=<name>` | Blunder rate time series (at least one file required) |

## Output Format

Each puzzle is a standalone PGN game with headers:

```
[Event "Rapid Tournament"]
[White "Alice"]
[Black "Bob"]
[FEN "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"]
[SetUp "1"]
[PuzzleNumber "1"]
[PuzzleReason "blunder (−312cp)"]
[PuzzleMove "4"]
[PuzzleTurn "white"]
[PuzzleAcceptable "d2d4,b1c3"]
[PuzzleTactics "fork,check"]
[GameMoves "64"]

4. Qxf7# { Played was Nf3 (blunder (−312cp)) }
```

## Project Structure

```
├── puzzles.py          # CLI puzzle generator
├── tactics.py          # Tactic classification engine
├── stats.py            # Player stats aggregation
├── app.py              # Flask web server
├── templates/
│   └── index.html      # Fischer Chess web UI
├── player_stats/       # Saved player JSON files
├── stockfish/          # Auto-downloaded engine binary
└── requirements.txt
```

## Tech Stack

- Python 3, python-chess, Flask
- Stockfish (native binary for CLI, WASM for browser)
- chessboard.js + chess.js (browser UI)
- stockfish.js 10.0.2 (browser engine via Web Worker)
