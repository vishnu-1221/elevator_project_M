import numpy as np
import json
from embedding_service import get_embedding

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def search_parts(cursor, user_input, top_k=3):
    query_emb = get_embedding(user_input)

    cursor.execute("SELECT spare_part, description, embedding FROM lift_parts")
    rows = cursor.fetchall()

    results = []

    for part, desc, emb in rows:
        if not emb:
            continue

        emb = np.array(json.loads(emb))
        score = cosine_similarity(query_emb, emb)

        results.append((part, desc, score))

    results.sort(key=lambda x: x[2], reverse=True)

    return results[:top_k]