"""Make the paper tables able to hold users' simulator accounts.

Two constraints written for a platform-only table block it:

    paper_accounts:  UNIQUE (name)      -> two users both naming an account
                                           "Симулятор" would collide
    paper_trades:    signal_id NOT NULL -> a hand-opened trade has no signal

SQLite cannot drop a unique constraint or relax NOT NULL in place, so both tables
are rebuilt. They hold the platform's measured record — 106 trades at the time of
writing — and that record is the one thing the project cannot regenerate, so this
backs the file up first, copies every row explicitly, and refuses to drop the old
table unless the counts match.

Usage:
    python scripts/migrate_simulator.py --check   # report, change nothing
    python scripts/migrate_simulator.py           # migrate
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "winextraflow.db")

ACCOUNTS_NEW = """
CREATE TABLE paper_accounts_new (
    id CHAR(32) NOT NULL,
    user_id CHAR(32),
    name VARCHAR(60) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    starting_balance FLOAT NOT NULL,
    balance FLOAT NOT NULL,
    risk_per_trade FLOAT NOT NULL,
    min_wef INTEGER NOT NULL,
    external_ref VARCHAR(120),
    notes TEXT,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
)
"""

TRADES_NEW = """
CREATE TABLE paper_trades_new (
    id CHAR(32) NOT NULL,
    account_id CHAR(32) NOT NULL,
    signal_id CHAR(32),
    opened_manually BOOLEAN NOT NULL DEFAULT 0,
    ticker VARCHAR(20) NOT NULL,
    action VARCHAR(4) NOT NULL,
    entry_price FLOAT NOT NULL,
    take_profit FLOAT,
    stop_loss FLOAT,
    wef_at_open INTEGER,
    position_value FLOAT NOT NULL,
    units FLOAT NOT NULL,
    risk_money FLOAT NOT NULL,
    status VARCHAR(9) NOT NULL,
    close_price FLOAT,
    result_pct FLOAT,
    result_money FLOAT,
    opened_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    closed_at DATETIME,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(account_id) REFERENCES paper_accounts (id),
    FOREIGN KEY(signal_id) REFERENCES signals (id)
)
"""

ACC_COLS = ["id", "name", "currency", "starting_balance", "balance",
            "risk_per_trade", "min_wef", "external_ref", "notes",
            "created_at", "updated_at"]

TRD_COLS = ["id", "account_id", "signal_id", "ticker", "action", "entry_price",
            "take_profit", "stop_loss", "wef_at_open", "position_value", "units",
            "risk_money", "status", "close_price", "result_pct", "result_money",
            "opened_at", "closed_at", "created_at", "updated_at"]

TRD_INDEXES = [
    ("ix_paper_trades_account_id", "account_id"),
    ("ix_paper_trades_signal_id", "signal_id"),
    ("ix_paper_trades_ticker", "ticker"),
    ("ix_paper_trades_status", "status"),
]


def columns(db, table):
    return [r[1] for r in db.execute(f"PRAGMA table_info({table})")]


def main():
    check_only = "--check" in sys.argv
    if not os.path.exists(DB):
        print(f"База не найдена: {DB}")
        return 1

    db = sqlite3.connect(DB)
    acc_cols, trd_cols = columns(db, "paper_accounts"), columns(db, "paper_trades")
    n_acc = db.execute("SELECT COUNT(*) FROM paper_accounts").fetchone()[0]
    n_trd = db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]

    has_user_id = "user_id" in acc_cols
    has_manual = "opened_manually" in trd_cols

    print(f"paper_accounts: {n_acc} строк, user_id: {'есть' if has_user_id else 'НЕТ'}")
    print(f"paper_trades:   {n_trd} строк, opened_manually: "
          f"{'есть' if has_manual else 'НЕТ'}")

    if has_user_id and has_manual:
        print("\nСхема уже актуальна.")
        return 0
    if check_only:
        print("\n--check: изменений не вносил.")
        return 0

    backup = f"{DB}.bak-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    shutil.copy2(DB, backup)
    print(f"\nБэкап: {os.path.basename(backup)}")

    try:
        # Foreign keys stay off for the swap: the intermediate state has
        # paper_trades pointing at a table that is about to be renamed.
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("BEGIN")

        db.execute(ACCOUNTS_NEW)
        cols = ", ".join(ACC_COLS)
        db.execute(f"INSERT INTO paper_accounts_new ({cols}, user_id) "
                   f"SELECT {cols}, NULL FROM paper_accounts")

        db.execute(TRADES_NEW)
        cols = ", ".join(TRD_COLS)
        db.execute(f"INSERT INTO paper_trades_new ({cols}, opened_manually) "
                   f"SELECT {cols}, 0 FROM paper_trades")

        # Verify before anything is dropped. A short copy here would silently
        # discard measured trades, so this is the point of no return.
        got_acc = db.execute("SELECT COUNT(*) FROM paper_accounts_new").fetchone()[0]
        got_trd = db.execute("SELECT COUNT(*) FROM paper_trades_new").fetchone()[0]
        if (got_acc, got_trd) != (n_acc, n_trd):
            raise RuntimeError(f"перенесено {got_acc}/{n_acc} счетов, "
                               f"{got_trd}/{n_trd} сделок — откат")

        db.execute("DROP TABLE paper_trades")
        db.execute("DROP TABLE paper_accounts")
        db.execute("ALTER TABLE paper_accounts_new RENAME TO paper_accounts")
        db.execute("ALTER TABLE paper_trades_new RENAME TO paper_trades")

        db.execute("CREATE INDEX ix_paper_accounts_user_id "
                   "ON paper_accounts (user_id)")
        for name, col in TRD_INDEXES:
            db.execute(f"CREATE INDEX {name} ON paper_trades ({col})")
        db.execute("CREATE INDEX ix_paper_trades_opened_manually "
                   "ON paper_trades (opened_manually)")

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"\nОшибка: {e}\nБаза не изменена. Бэкап: {backup}")
        return 1
    finally:
        db.execute("PRAGMA foreign_keys=ON")

    # Post-conditions: the platform's rows must be exactly as they were, and all
    # of them must still count as platform rows.
    n_acc2 = db.execute("SELECT COUNT(*) FROM paper_accounts").fetchone()[0]
    n_trd2 = db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    plat_acc = db.execute("SELECT COUNT(*) FROM paper_accounts "
                          "WHERE user_id IS NULL").fetchone()[0]
    plat_trd = db.execute("SELECT COUNT(*) FROM paper_trades "
                          "WHERE opened_manually = 0").fetchone()[0]
    closed = db.execute("SELECT COUNT(*) FROM paper_trades "
                        "WHERE status IN ('CLOSED_TP','CLOSED_SL')").fetchone()[0]
    fk = db.execute("PRAGMA foreign_key_check").fetchall()

    print(f"\nСчетов: {n_acc2} (было {n_acc}), из них платформенных {plat_acc}")
    print(f"Сделок: {n_trd2} (было {n_trd}), из них конвейерных {plat_trd}, "
          f"закрытых {closed}")
    print(f"Целостность ссылок: {'ок' if not fk else f'НАРУШЕНА: {fk[:3]}'}")

    ok = (n_acc2 == n_acc and n_trd2 == n_trd
          and plat_acc == n_acc and plat_trd == n_trd and not fk)
    print("\nМиграция выполнена." if ok else "\nПРОВЕРЬТЕ РЕЗУЛЬТАТ — что-то не сходится.")
    return 0 if ok else 1


sys.exit(main())
