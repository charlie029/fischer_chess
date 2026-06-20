# Fischer Chess — Requirements Document

## Overview

Fischer Chess is a chess puzzle generation and training system that extracts blunders from real games, classifies them by tactic type, and provides an interactive web interface for solving, tracking progress, and analysis. Deployed on AWS Lightsail with SQLite persistence.

---

## 1. Puzzle Generation

### 1.1 Input
- **FR-1.1.1**: Accept PGN games from Chess.com import (online API) or local PGN file upload
- **FR-1.1.2**: Games stored in SQLite database per user

### 1.2 Analysis Engine
- **FR-1.2.1**: Use Stockfish for position evaluation (server-side)
- **FR-1.2.2**: Auto-download platform-appropriate Stockfish binary if not provided
- **FR-1.2.3**: Configurable search depth (default: 12 for web, 18 for CLI)

### 1.3 Blunder Detection
- **FR-1.3.1**: Flag positions where eval drop from moving side's perspective >= threshold (default: 200cp)
- **FR-1.3.2**: Detect missed mates (not slower mates, not checkmate delivered, not positions still >500cp winning)
- **FR-1.3.3**: Player name filter: case-insensitive substring match against PGN White/Black headers; blank = keep all blunders

### 1.4 Acceptable Moves
- **FR-1.4.1**: MultiPV=5 analysis at each puzzle position
- **FR-1.4.2**: Moves within 50cp of best move marked as acceptable alternatives

### 1.5 Tactic Classification
- **FR-1.5.1**: Supported tactics: fork, discovered attack, discovered check, pin, skewer, back rank mate, smothered mate, checkmate, check, capture, promotion, trapped piece, positional
- **FR-1.5.2**: Multiple tags may apply to a single puzzle

---

## 2. Web Application — Main Page

### 2.1 User System
- **FR-2.1.1**: User select/create on login; localStorage persistence
- **FR-2.1.2**: Multi-user support with per-user games and puzzles
- **FR-2.1.3**: Password gate for app access (session-based)

### 2.2 Import
- **FR-2.2.1**: Chess.com import via modal (username + date range calendar pickers)
- **FR-2.2.2**: Local PGN file upload
- **FR-2.2.3**: Both save games to active user's DB

### 2.3 Run Analysis
- **FR-2.3.1**: Prompts for player name (case-insensitive substring match)
- **FR-2.3.2**: Blank player name keeps all blunders from both sides
- **FR-2.3.3**: Generates puzzles from DB games and saves to DB

### 2.4 Puzzle Queue & Lifecycle
- **FR-2.4.1**: Queue shows `active` puzzles first, then `solved_retry` at bottom
- **FR-2.4.2**: Solved on first try → status `solved_first_try`, auto-removed from queue
- **FR-2.4.3**: Solved on retry (wrong attempt then correct) → status `solved_retry`, stays in queue at bottom
- **FR-2.4.4**: "Skip" button → status `archived`, removed from queue
- **FR-2.4.5**: Puzzles stay in queue until manually archived via Skip

### 2.5 Puzzle Solving
- **FR-2.5.1**: Interactive chessboard with drag-and-drop
- **FR-2.5.2**: Board auto-orients to puzzle's turn
- **FR-2.5.3**: Three-tier feedback: correct (green), acceptable (amber, shows best), incorrect (red, snapback)
- **FR-2.5.4**: Chat-style text input accepting SAN or UCI notation
- **FR-2.5.5**: Hint button highlights solution source square

### 2.6 Post-Solve Exploration
- **FR-2.6.1**: Free moves via drag-and-drop and chat input after solving
- **FR-2.6.2**: Back/Forward/Reset buttons for navigation

### 2.7 Engine Analysis
- **FR-2.7.1**: Browser-side Stockfish WASM (stockfish.js 10.0.2)
- **FR-2.7.2**: Toggle on/off; displays 3 MultiPV lines with eval
- **FR-2.7.3**: Eval convention: + = white advantage, - = black advantage (absolute, not relative to side)
- **FR-2.7.4**: Auto-re-analyze on position change

### 2.8 Info Panel
- **FR-2.8.1**: Display puzzle metadata (move number, turn, FEN)
- **FR-2.8.2**: FEN is copyable

---

## 3. Web Application — Player/Stats Page

### 3.1 Stats Dashboard
- **FR-3.1.1**: Summary boxes: total puzzles, avg cp loss, games with blunders
- **FR-3.1.2**: Tactic breakdown

### 3.2 Trends
- **FR-3.2.1**: Chart.js line chart with flexible axes (date/game#, blunder rate/count/avg cp loss/total moves)
- **FR-3.2.2**: Date range filter with Apply button
- **FR-3.2.3**: Only shows analyzed games (INNER JOIN)

### 3.3 Recent Puzzles Table
- **FR-3.3.1**: Shows all puzzles with status, move, turn, best move, tactics
- **FR-3.3.2**: "Retry" button sets puzzle back to `active` (returns to main page queue)

### 3.4 Recent Games Table
- **FR-3.4.1**: Shows date, white, black, result, moves
- **FR-3.4.2**: Per-row delete button (cascades to associated puzzles)

### 3.5 Actions
- **FR-3.5.1**: Delete User button (removes all user data)
- **FR-3.5.2**: No import or Run Analysis on this page (those live on main page)

---

## 4. Deployment

- **FR-4.1**: AWS Lightsail nano instance ($3.50/mo)
- **FR-4.2**: Systemd service with auto-restart
- **FR-4.3**: SQLite database for persistence
- **FR-4.4**: Flask with debug mode, bound to 0.0.0.0:5001
- **FR-4.5**: GitHub repo for version control

---

## 5. Non-Functional Requirements

- **NFR-5.1**: Engine analysis runs entirely in-browser (no server round-trips)
- **NFR-5.2**: Path traversal prevention on file endpoints
- **NFR-5.3**: Minimal dependencies (python-chess, flask, requests)
- **NFR-5.4**: Stockfish auto-downloaded on server for puzzle generation

---

## 6. Future / Planned

- **FR-6.1**: Refine "positional" tactic into finer-grained categories
- **FR-6.2**: Bulk puzzle generation for large game libraries
- **FR-6.3**: Move back/forward/reset polish
