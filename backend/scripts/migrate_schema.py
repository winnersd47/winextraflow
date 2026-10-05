"""Add columns that models declare but existing tables lack.

The database is created by `Base.metadata.create_all`, which creates missing
tables but never alters existing ones. So a new column on a model is invisible to
a database that already has the table — queries then fail with "no such column"
at runtime, not at import.

This script reconciles the two. It is idempotent: run it after every pull that
touches a model, and on the server as part of the deploy step.

Usage: python scripts/migrate_schema.py [--apply]
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from app.database import engine, Base
import app.models  # noqa: F401  — registers every model on Base.metadata

# SQLite's ALTER TABLE only supports ADD COLUMN, which covers every case here.
SKIP_TYPES = ()


def sql_type(col, dialect) -> str:
    return col.type.compile(dialect=dialect)


def _default_literal(col) -> str | None:
    """SQL literal for the model's scalar default, for backfilling existing rows.

    Only plain scalars: a callable default (uuid4, now()) is per-row and cannot be
    expressed as one literal, so those columns stay NULL and the caller decides.
    """
    d = getattr(col, "default", None)
    if d is None or getattr(d, "is_callable", False):
        return None
    arg = getattr(d, "arg", None)
    if callable(arg) or arg is None:
        return None
    if isinstance(arg, bool):
        return "1" if arg else "0"
    if isinstance(arg, (int, float)):
        return str(arg)
    if isinstance(arg, str):
        return "'" + arg.replace("'", "''") + "'"
    return None


async def main():
    apply = "--apply" in sys.argv
    async with engine.begin() as conn:
        def plan(sync_conn):
            insp = inspect(sync_conn)
            existing_tables = set(insp.get_table_names())
            todo = []
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    todo.append((table.name, None, None))     # whole table missing
                    continue
                have = {c["name"] for c in insp.get_columns(table.name)}
                for col in table.columns:
                    if col.name not in have:
                        todo.append((table.name, col.name,
                                     sql_type(col, sync_conn.dialect)))
            return todo

        todo = await conn.run_sync(plan)

        if not todo:
            print("Схема актуальна — добавлять нечего.")
            return

        for tname, cname, ctype in todo:
            if cname is None:
                print(f"  [table] {tname}: отсутствует целиком")
                if apply:
                    await conn.run_sync(Base.metadata.tables[tname].create)
                    print(f"          создана")
                continue
            # A model-side `default=` only fires on new inserts, so existing rows
            # would keep NULL. That silently breaks filters: `is_seed.is_(False)`
            # matches neither True nor NULL, so a freshly added flag excludes every
            # pre-existing row instead of none of them.
            fill = _default_literal(Base.metadata.tables[tname].columns[cname])
            print(f"  [col]   {tname}.{cname} {ctype}"
                  + (f"  (существующие строки -> {fill})" if fill is not None else ""))
            if apply:
                # NOT NULL without a default cannot be added to a populated table;
                # every column added this way is nullable by design.
                await conn.execute(text(f'ALTER TABLE {tname} ADD COLUMN {cname} {ctype}'))
                if fill is not None:
                    await conn.execute(
                        text(f'UPDATE {tname} SET {cname} = {fill} WHERE {cname} IS NULL'))

        print(f"\n{'ПРИМЕНЕНО' if apply else 'ПРЕДПРОСМОТР — запустите с --apply'}: "
              f"{len(todo)} изменен(ий)")


asyncio.run(main())
