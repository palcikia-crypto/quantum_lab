CREATE TABLE trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, side TEXT, strategy TEXT,
        entry_price REAL, exit_price REAL, pnl REAL,
        entry_ts INTEGER, exit_ts INTEGER,
        status TEXT DEFAULT 'OPEN', win_flag INTEGER DEFAULT 0, tp REAL, sl REAL, timeout_bars REAL);
CREATE TABLE sqlite_sequence(name,seq);
