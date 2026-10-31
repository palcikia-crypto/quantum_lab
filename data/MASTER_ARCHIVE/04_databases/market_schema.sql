CREATE TABLE candles (
        symbol TEXT, tf TEXT, ts INTEGER,
        o REAL, h REAL, l REAL, c REAL, v REAL,
        PRIMARY KEY (symbol, tf, ts)
    );
CREATE INDEX idx_candles ON candles(symbol, tf, ts);
CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT);
