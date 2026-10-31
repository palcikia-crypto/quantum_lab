CREATE TABLE prices (
        ts INTEGER, symbol TEXT, price REAL, volume REAL, bid REAL, ask REAL, spread REAL,
        PRIMARY KEY (symbol, ts));
CREATE TABLE regime (
        ts INTEGER, symbol TEXT, regime TEXT, atr REAL, adx REAL, vol_z REAL,
        PRIMARY KEY (symbol, ts));
CREATE TABLE regime_history (
        symbol TEXT, ts INTEGER, regime TEXT, adx REAL, atr REAL,
        PRIMARY KEY (symbol, ts));
