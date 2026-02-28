"""
db.py - Database connection, schema extraction, and query execution.
Supports SQLite files and uploaded CSV files (via DuckDB).
"""

import sqlite3
import pandas as pd
import duckdb
from sqlalchemy import create_engine, inspect, text
from pathlib import Path


# ─────────────────────────────────────────────
# SQLite helpers
# ─────────────────────────────────────────────

def get_sqlite_schema(db_path: str) -> str:
    """
    Extract schema from a SQLite database.
    Returns a human-readable schema string for use in prompts.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    schema_parts = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}');")
        columns = cursor.fetchall()
        col_defs = ", ".join(f"{col[1]} ({col[2]})" for col in columns)

        # Try to get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list('{table}');")
        fks = cursor.fetchall()
        fk_str = ""
        if fks:
            fk_refs = ", ".join(f"{fk[3]} → {fk[2]}.{fk[4]}" for fk in fks)
            fk_str = f"  [FK: {fk_refs}]"

        schema_parts.append(f"{table}({col_defs}){fk_str}")

    conn.close()
    return "\n".join(schema_parts)


def run_sqlite_query(db_path: str, sql: str) -> pd.DataFrame:
    """Execute a SQL query on a SQLite database and return results as DataFrame."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df


# ─────────────────────────────────────────────
# DuckDB helpers (for CSV uploads)
# ─────────────────────────────────────────────

def get_csv_schema(csv_path: str, table_name: str = "data") -> str:
    """Extract schema from an uploaded CSV file using DuckDB."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
    result = con.execute(f"DESCRIBE {table_name}").fetchdf()
    con.close()

    cols = ", ".join(f"{row['column_name']} ({row['column_type']})" for _, row in result.iterrows())
    return f"{table_name}({cols})"


def run_csv_query(csv_path: str, sql: str, table_name: str = "data") -> pd.DataFrame:
    """Execute a SQL query on a CSV file using DuckDB."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
    df = con.execute(sql).df()
    con.close()
    return df


# ─────────────────────────────────────────────
# Seed sample Chinook-style DB for demo
# ─────────────────────────────────────────────

def seed_sample_db(db_path: str = "db/sample.db"):
    """Create a minimal sample database if none exists."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if Path(db_path).exists():
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            CustomerId INTEGER PRIMARY KEY,
            FirstName TEXT, LastName TEXT,
            Country TEXT, Email TEXT
        );
        CREATE TABLE IF NOT EXISTS invoices (
            InvoiceId INTEGER PRIMARY KEY,
            CustomerId INTEGER,
            InvoiceDate TEXT,
            BillingCountry TEXT,
            Total REAL,
            FOREIGN KEY (CustomerId) REFERENCES customers(CustomerId)
        );
        CREATE TABLE IF NOT EXISTS invoice_items (
            InvoiceLineId INTEGER PRIMARY KEY,
            InvoiceId INTEGER,
            TrackId INTEGER,
            UnitPrice REAL,
            Quantity INTEGER,
            FOREIGN KEY (InvoiceId) REFERENCES invoices(InvoiceId)
        );
        CREATE TABLE IF NOT EXISTS tracks (
            TrackId INTEGER PRIMARY KEY,
            Name TEXT,
            AlbumId INTEGER,
            GenreId INTEGER,
            UnitPrice REAL,
            Milliseconds INTEGER
        );
        CREATE TABLE IF NOT EXISTS albums (
            AlbumId INTEGER PRIMARY KEY,
            Title TEXT,
            ArtistId INTEGER
        );
        CREATE TABLE IF NOT EXISTS artists (
            ArtistId INTEGER PRIMARY KEY,
            Name TEXT
        );
        CREATE TABLE IF NOT EXISTS genres (
            GenreId INTEGER PRIMARY KEY,
            Name TEXT
        );
    """)

    import random
    from datetime import datetime, timedelta

    random.seed(42)
    countries = ["USA", "UK", "Germany", "France", "Brazil", "Canada", "Australia"]
    genres = ["Rock", "Jazz", "Pop", "Classical", "Hip-Hop", "Electronic"]
    artists = ["The Beatles", "Miles Davis", "Taylor Swift", "Bach", "Kendrick Lamar", "Daft Punk"]

    for i, g in enumerate(genres, 1):
        c.execute("INSERT INTO genres VALUES (?,?)", (i, g))

    for i, a in enumerate(artists, 1):
        c.execute("INSERT INTO artists VALUES (?,?)", (i, a))

    for i in range(1, 21):
        c.execute("INSERT INTO albums VALUES (?,?,?)", (i, f"Album {i}", random.randint(1, 6)))

    for i in range(1, 201):
        c.execute("INSERT INTO tracks VALUES (?,?,?,?,?,?)", (
            i, f"Track {i}", random.randint(1, 20),
            random.randint(1, 6), round(random.choice([0.99, 1.29, 1.99]), 2),
            random.randint(150000, 400000)
        ))

    for i in range(1, 101):
        c.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (
            i, f"First{i}", f"Last{i}",
            random.choice(countries), f"user{i}@email.com"
        ))

    invoice_id = 1
    for cust_id in range(1, 101):
        for _ in range(random.randint(1, 5)):
            date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 730))
            total = round(random.uniform(1.99, 25.99), 2)
            country = random.choice(countries)
            c.execute("INSERT INTO invoices VALUES (?,?,?,?,?)", (
                invoice_id, cust_id, date.strftime("%Y-%m-%d"), country, total
            ))
            for _ in range(random.randint(1, 4)):
                c.execute("INSERT INTO invoice_items VALUES (?,?,?,?,?)", (
                    None, invoice_id, random.randint(1, 200),
                    round(random.choice([0.99, 1.29, 1.99]), 2), random.randint(1, 3)
                ))
            invoice_id += 1

    conn.commit()
    conn.close()
    print(f"✅ Sample DB seeded at {db_path}")
