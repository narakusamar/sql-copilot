import sqlite3
from core.config import Config


def _get_sqlite_conn():
    return sqlite3.connect(Config.DB_PATH)


def _get_mysql_conn():
    import pymysql
    return pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor)


def _get_pg_conn():
    import psycopg2
    return psycopg2.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        dbname=Config.DB_NAME)


class SQLExecutor:
    def __init__(self):
        self.db_type = Config.DB_TYPE

    def _get_conn(self):
        if self.db_type == "mysql":
            return _get_mysql_conn()
        elif self.db_type == "postgresql":
            return _get_pg_conn()
        else:
            return _get_sqlite_conn()

    def run(self, sql: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            result = cursor.fetchall()
            conn.close()
            return result, None
        except Exception as e:
            conn.close()
            return None, str(e)

    def run_with_columns(self, sql: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            conn.close()
            return columns, rows, None
        except Exception as e:
            conn.close()
            return [], None, str(e)

    def run_with_commit(self, sql: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            conn.commit()
            conn.close()
            return cursor.rowcount, None
        except Exception as e:
            conn.rollback()
            conn.close()
            return None, str(e)

    def get_schema(self) -> str:
        if self.db_type == "mysql":
            return self._get_mysql_schema()
        elif self.db_type == "postgresql":
            return self._get_pg_schema()
        else:
            return self._get_sqlite_schema()

    def get_tables(self) -> list[str]:
        if self.db_type == "mysql":
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        elif self.db_type == "postgresql":
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        else:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables

    # ── SQLite ──

    def _get_sqlite_schema(self) -> str:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        schema_lines = []
        for (table,) in tables:
            cursor.execute(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
            ddl = cursor.fetchone()[0]
            cursor.execute(f"PRAGMA table_info('{table}')")
            sample = cursor.execute(
                f"SELECT * FROM \"{table}\" LIMIT 3").fetchall()
            schema_lines.append(ddl + ";")
            if sample:
                schema_lines.append(f"-- 示例数据: {sample}")
        conn.close()
        return "\n".join(schema_lines)

    # ── MySQL ──

    def _get_mysql_schema(self) -> str:
        conn = self._get_conn()
        cursor = conn.cursor()
        tables = self.get_tables()
        schema_lines = []
        for table in tables:
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            _, ddl = cursor.fetchone()
            schema_lines.append(ddl + ";")
            cursor.execute(f"SELECT * FROM `{table}` LIMIT 3")
            sample = cursor.fetchall()
            if sample:
                schema_lines.append(f"-- 示例数据: {sample}")
        conn.close()
        return "\n".join(schema_lines)

    # ── PostgreSQL ──

    def _get_pg_schema(self) -> str:
        conn = self._get_conn()
        cursor = conn.cursor()
        tables = self.get_tables()
        schema_lines = []
        for table in tables:
            cursor.execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table,))
            cols = cursor.fetchall()
            col_defs = ", ".join(
                f"{c[0]} {c[1]}" + (" NOT NULL" if c[2] == "NO" else "")
                for c in cols)
            schema_lines.append(
                f"CREATE TABLE {table} ({col_defs});")
            cursor.execute(
                f"SELECT * FROM \"{table}\" LIMIT 3")
            sample = cursor.fetchall()
            if sample:
                schema_lines.append(f"-- 示例数据: {sample}")
        conn.close()
        return "\n".join(schema_lines)
