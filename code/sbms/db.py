"""Database connection helpers.

Every change that touches stock or orders goes through transaction(), so if any
step fails the whole thing is rolled back and nothing is left half-saved.
"""
from contextlib import contextmanager

import pymysql
import pymysql.cursors

from . import config


def get_connection(database=None):
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=database if database is not None else config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@contextmanager
def transaction():
    """Yield a cursor; commit if the block finishes, roll back if it raises."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def fetch_one(sql, params=None):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
