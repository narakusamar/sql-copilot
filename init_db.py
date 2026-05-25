"""
初始化 superstore 数据库，从 CSV 加载数据，并做类型转换
"""
import sqlite3
import csv
from pathlib import Path
from datetime import datetime

CSV_PATH = "/home/naraku/datasets/market/Sample - Superstore.csv"
DB_PATH = Path(__file__).parent / "superstore.db"

# 列名 → SQLite 类型
COLUMN_TYPES = {
    "Row_ID": "INTEGER", "Order_ID": "TEXT", "Order_Date": "TEXT",
    "Ship_Date": "TEXT", "Ship_Mode": "TEXT", "Customer_ID": "TEXT",
    "Customer_Name": "TEXT", "Segment": "TEXT", "Country": "TEXT",
    "City": "TEXT", "State": "TEXT", "Postal_Code": "TEXT",
    "Region": "TEXT", "Product_ID": "TEXT", "Category": "TEXT",
    "Sub_Category": "TEXT", "Product_Name": "TEXT",
    "Sales": "REAL", "Quantity": "INTEGER", "Discount": "REAL", "Profit": "REAL",
}

INTEGER_COLS = {"Row_ID", "Quantity"}
REAL_COLS = {"Sales", "Discount", "Profit"}
DATE_COLS = {"Order_Date", "Ship_Date"}


def parse_date(val: str) -> str:
    """M/D/YYYY → YYYY-MM-DD"""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return val.strip()


def convert_value(col: str, val: str):
    """将 CSV 字符串转为正确类型"""
    val = val.strip()
    if col in DATE_COLS:
        return parse_date(val)
    if col in INTEGER_COLS:
        try:
            return int(val)
        except ValueError:
            return 0
    if col in REAL_COLS:
        try:
            return float(val)
        except ValueError:
            return 0.0
    return val


def init_from_csv():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 先删旧表
    cursor.execute("DROP TABLE IF EXISTS superstore")

    with open(CSV_PATH, "r", encoding="cp1252") as f:
        reader = csv.reader(f)
        headers = next(reader)
        cols = [h.strip().replace(" ", "_").replace("-", "_") for h in headers]

        # 按正确类型建表
        col_defs = [f'"{c}" {COLUMN_TYPES.get(c, "TEXT")}' for c in cols]
        cursor.execute(f"CREATE TABLE superstore ({', '.join(col_defs)})")

        placeholders = ", ".join(["?" for _ in cols])
        quoted_cols = ", ".join(f'"{c}"' for c in cols)

        batch = []
        for row in reader:
            converted = [convert_value(cols[i], v) for i, v in enumerate(row)]
            batch.append(converted)
            if len(batch) >= 1000:
                cursor.executemany(
                    f"INSERT INTO superstore ({quoted_cols}) VALUES ({placeholders})",
                    batch,
                )
                batch = []
        if batch:
            cursor.executemany(
                f"INSERT INTO superstore ({quoted_cols}) VALUES ({placeholders})",
                batch,
            )

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM superstore")
    count = cursor.fetchone()[0]
    print(f"Loaded {count} rows into superstore table.")

    cursor.execute("PRAGMA table_info('superstore')")
    for row in cursor.fetchall():
        print(f"  {row[1]:20s} {row[2]}")
    conn.close()


if __name__ == "__main__":
    init_from_csv()
