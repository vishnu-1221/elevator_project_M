import sqlite3

# connect to DB (creates file automatically)
conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

# create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS lift_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spare_part TEXT NOT NULL,
    description TEXT
)
""")


spare_parts = [
    "Accumulator 12V/7Ah", 
    "Shunt for door contact AZ01", 
    ]

# clear old data (avoid duplicates)
cursor.execute("DELETE FROM lift_parts")

# insert spare parts
for part in spare_parts:
    cursor.execute(
        "INSERT INTO lift_parts (spare_part) VALUES (?)",
        (part,)
    )

conn.commit()

# fetch and print
cursor.execute("SELECT * FROM lift_parts")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()