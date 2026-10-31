CREATE TABLE trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, side TEXT, strategy TEXT,
        entry_price REAL, exit_price REAL, pnl REAL,
        status TEXT, entry_ts INTEGER, exit_ts INTEGER,
        tp REAL, sl REAL);
CREATE TABLE sqlite_sequence(name,seq);
