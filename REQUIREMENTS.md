# Fischer Chess — Requirements Document

## Overview

Fischer Chess is a chess puzzle generation and training system that extracts blunders from real games, classifies them by tactic type, and provides an interactive web interface for solving and analysis.

---

## 1. Puzzle Generation

### 1.1 Input
- **FR-1.1.1**: Accept PGN files containing one or more games
- **FR-1.1.2**: Support standard PGN format with headers and movetext (including annotations and variations — ignored during analysis)

### 1.2 Analysis Engine
- **FR-1.2.1**: Use Stockfish for position evaluation
- **FR-1.2.2**: Auto-download platform-appropriate Stockfish binary (macOS ARM, Linux x86-64, Windows) if not provided
- **FR-1.2.3**: Configurable search depth (default: 18 ply)
- **FR-1.2.4**: Evaluate every position in the mainline of each game

### 1.3 Blunder Detection
- **FR-1.3.1**: Flag positions where the eval drop from the moving side's perspective ≥ threshold (default: 200cp)
- **FR-1.3.2**: Detect missed mates — flag only when a forced mate is completely lost (not slower mates, not checkmate delivered, not positions still >500cp winning)
- **FR-1.3.3**: Configurable centipawn threshold via CLI flag

### 1.4 Acceptable Moves
- **FR-1.4.1**: At each puzzle position, compute MultiPV=5 analysis
- **FR-1.4.2**: Moves within ≤50cp of the best move are marked as acceptable alternatives
- **FR-1.4.3**: Store acceptable moves as comma-separated UCI in PGN header

### 1.5 Tactic Classification
- **FR-1.5.1**: Classify each puzzle's best move by tactic type
- **FR-1.5.2**: Supported tactics: fork, discovered attack, discovered check, pin, skewer, back rank mate, smothered mate, checkmate, check, capture, promotion, trapped piece, positional (fallback)
- **FR-1.5.3**: Multiple tags may apply to a single puzzle
- **FR-1.5.4**: Store as comma-separated labels in PGN header

### 1.6 Player Filter
- **FR-1.6.1**: Optional filter to include only blunders by a specific player
- **FR-1.6.2**: Case-insensitive partial match against White/Black headers
- **FR-1.6.3**: Skip games where the player is not involved

### 1.7 Output
- **FR-1.7.1**: Output as standard PGN file (one game per puzzle)
- **FR-1.7.2**: Include original game info headers (Event, Site, Date, Round, White, Black, Result)
- **FR-1.7.3**: Include FEN + SetUp=1 for the puzzle starting position
- **FR-1.7.4**: Include metadata headers: PuzzleNumber, PuzzleReason, PuzzleMove, PuzzleTurn, PuzzleAcceptable, PuzzleTactics, GameMoves
- **FR-1.7.5**: Mainline contains the best move with comment noting what was played
- **FR-1.7.6**: Output PGN must be openable in Lichess and Chess.com

---

## 2. Web Application

### 2.1 Puzzle Solving
- **FR-2.1.1**: Interactive chessboard with drag-and-drop piece movement
- **FR-2.1.2**: Board auto-orients to the puzzle's turn (white/black at bottom)
- **FR-2.1.3**: Three-tier move feedback:
  - Green: exact best move (correct)
  - Amber: acceptable move within 50cp (shows best move)
  - Red: incorrect move (snapback, try again)
- **FR-2.1.4**: Chat-style text input panel accepting SAN or UCI notation as alternative to drag-and-drop
- **FR-2.1.5**: Hint button highlights the source square of the solution move

### 2.2 Navigation
- **FR-2.2.1**: Prev/Next buttons to navigate between puzzles
- **FR-2.2.2**: Puzzle counter showing current position (N / M)
- **FR-2.2.3**: PGN file selector dropdown

### 2.3 Free Exploration (Post-Solve)
- **FR-2.3.1**: After solving, allow free moves via drag-and-drop and chat input
- **FR-2.3.2**: Back/Forward/Reset buttons for undo/redo through explored line
- **FR-2.3.3**: Keyboard arrow support (left=back, right=forward)

### 2.4 Engine Analysis
- **FR-2.4.1**: Browser-side Stockfish WASM (stockfish.js 10.0.2)
- **FR-2.4.2**: Toggle button to enable/disable engine
- **FR-2.4.3**: Display 3 MultiPV lines with centipawn evaluation
- **FR-2.4.4**: Auto-re-analyze on every board position change
- **FR-2.4.5**: Show current search depth

### 2.5 Puzzle Generation (In-Browser)
- **FR-2.5.1**: Generate puzzles from the web UI with optional player filter
- **FR-2.5.2**: Real-time progress via Server-Sent Events (SSE)
- **FR-2.5.3**: Auto-load generated puzzle file on completion

### 2.6 Info Panel
- **FR-2.6.1**: Display game info (Event, Date, White, Black)
- **FR-2.6.2**: Display puzzle metadata (move number, turn, reason, FEN)
- **FR-2.6.3**: FEN is copyable (user-select: all)

---

## 3. Player Stats

### 3.1 Tactic Aggregation
- **FR-3.1.1**: Classify all puzzles in a file by tactic type
- **FR-3.1.2**: Aggregate per-player: total blunders, average cp loss, tactic breakdown, per-game details
- **FR-3.1.3**: Support on-the-fly computation (no persistence) and save-to-file modes

### 3.2 Persistence
- **FR-3.2.1**: Save player stats to `player_stats/<name>.json`
- **FR-3.2.2**: Merge stats across multiple PGN source files (keyed by filename, re-runs overwrite)
- **FR-3.2.3**: Compute aggregate totals across all sources

### 3.3 Stats UI
- **FR-3.3.1**: Modal overlay with player selector
- **FR-3.3.2**: Summary boxes: total blunders, average cp loss, number of tactic types
- **FR-3.3.3**: Horizontal bar chart of tactic breakdown (sorted by frequency)
- **FR-3.3.4**: Per-game detail list with tactic tags per puzzle
- **FR-3.3.5**: Save-to-file button to persist stats

---

## 4. User Profile

### 4.1 Profile Management
- **FR-4.1.1**: Set active player name via profile bar in UI
- **FR-4.1.2**: Persist active profile across sessions
- **FR-4.1.3**: Clear profile option
- **FR-4.1.4**: Display profile summary (total blunders, source count, top tactic tags)

### 4.2 Profile Integration
- **FR-4.2.1**: Auto-attach saved stats when retrieving profile
- **FR-4.2.2**: API endpoints: GET/POST/DELETE `/api/profile`

---

## 5. Blunder Rate Trends

### 5.1 Data Sources
- **FR-5.1.1**: Accept puzzle PGN file as fast-path input (no engine needed)
- **FR-5.1.2**: Accept original game PGN as slow-path input (runs Stockfish analysis)
- **FR-5.1.3**: At least one file must be provided; both are optional
- **FR-5.1.4**: If puzzle file has `GameMoves` header, no games file needed for rate calculation
- **FR-5.1.5**: If puzzle file lacks `GameMoves`, fall back to games file for total move counts

### 5.2 Computation
- **FR-5.2.1**: Compute blunder rate per game as (blunders / total moves)
- **FR-5.2.2**: Group puzzles by game using White|Black|Date composite key
- **FR-5.2.3**: Optional player filter (case-insensitive partial match)
- **FR-5.2.4**: Return time series sorted by game date

### 5.3 Visualization
- **FR-5.3.1**: Chart.js line chart with game dates on x-axis, blunder rate % on y-axis
- **FR-5.3.2**: 5-game moving average trendline (green dashed line)
- **FR-5.3.3**: Hover tooltips showing game name, blunder count, and total moves
- **FR-5.3.4**: Modal overlay triggered by "Trends" button in controls bar
- **FR-5.3.5**: Two file selectors (games PGN, puzzle PGN) + player filter input

---

## 6. Non-Functional Requirements

### 6.1 Performance
- **NFR-6.1.1**: Puzzle generation uses MultiPV for speed (single call per position vs per-move)
- **NFR-6.1.2**: Engine analysis runs entirely in-browser (no server round-trips)
- **NFR-6.1.3**: SSE streaming for real-time generation feedback
- **NFR-6.1.4**: Trends fast-path uses pre-computed puzzle data (no Stockfish needed)

### 6.2 Compatibility
- **NFR-6.2.1**: Output PGN compatible with Lichess and Chess.com import
- **NFR-6.2.2**: Web UI works in modern browsers (Chrome, Firefox, Safari)
- **NFR-6.2.3**: Stockfish auto-download supports macOS ARM, Linux x86-64, Windows

### 6.3 Security
- **NFR-6.3.1**: Path traversal prevention on all file-serving endpoints (reject `/` and `\` in filenames)

### 6.4 Portability
- **NFR-6.4.1**: Minimal dependencies (python-chess, flask)
- **NFR-6.4.2**: No database required — file-based persistence (JSON, PGN)
- **NFR-6.4.3**: Self-contained — Stockfish auto-downloaded, no external services needed

---

## 7. Future / Planned

- **FR-7.1**: Save individual puzzles into player profile (not just aggregate stats)
- **FR-7.2**: Refine "positional" tactic into finer-grained categories (hanging piece defense, threat creation, pawn push, king safety, quiet improvement)
- **FR-7.3**: Verify and fix move back/forward/reset feature (implementation started, needs testing)
