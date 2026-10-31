CREATE TABLE orderbooks (
        ts INTEGER, symbol TEXT,
        best_bid REAL, best_ask REAL, spread REAL,
        bid_depth REAL, ask_depth REAL, imbalance REAL,
        PRIMARY KEY (ts, symbol)
    );
CREATE TABLE trades (
        ts INTEGER, symbol TEXT, side TEXT, price REAL, volume REAL,
        PRIMARY KEY (ts, symbol, side, price)
    );
CREATE TABLE funding (
        ts INTEGER, symbol TEXT, funding_rate REAL, next_funding_ts INTEGER,
        PRIMARY KEY (ts, symbol)
    );
CREATE TABLE vwap (
        ts INTEGER, symbol TEXT, vwap_1m REAL, vwap_5m REAL,
        PRIMARY KEY (ts, symbol)
    );
CREATE INDEX idx_ob_sym_ts ON orderbooks(symbol, ts);
CREATE INDEX idx_tr_sym_ts ON trades(symbol, ts);
