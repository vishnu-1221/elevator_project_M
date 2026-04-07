import sqlite3
import json
from embedding_service import get_embedding

conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

# Add column if not exists
try:
    cursor.execute("ALTER TABLE lift_parts ADD COLUMN embedding TEXT")
except:
    pass

cursor.execute("SELECT id, description FROM lift_parts WHERE embedding IS NULL")
rows = cursor.fetchall()

print(f"Generating embeddings for {len(rows)} records...")

for part_id, desc in rows:
    emb = get_embedding(desc)

    cursor.execute("""
        UPDATE lift_parts
        SET embedding = ?
        WHERE id = ?
    """, (json.dumps(emb), part_id))

conn.commit()
conn.close()

print("✅ Embeddings stored in DB")