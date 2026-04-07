import sqlite3
import os
from openai import OpenAI
from search_service import search_parts

# =========================
# OpenAI Client
# =========================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# Query Normalization
# =========================
def normalize_query(query):
    prompt = f"""
Convert the following elevator issue into a precise technical symptom.

User Input:
{query}

Output:
One clear, technical sentence describing the observable issue.
"""

    response = client.chat.completions.create(
        model="gpt-5.4",
        temperature=0,
        messages=[
            {"role": "system", "content": "You convert user complaints into technical elevator symptoms."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()


# =========================
# DB CONNECTION
# =========================
conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

print(" Lift Sense AI Search System")

while True:
    user_input = input("\nEnter lift symptom (or 'exit'): ")

    if user_input.lower() == "exit":
        break

    # =========================
    # Normalize Input
    # =========================
    try:
        normalized_query = normalize_query(user_input)
        print("\n Normalized Query:")
        print(normalized_query)
    except Exception as e:
        print("⚠️ Normalization failed, using raw input:", e)
        normalized_query = user_input

    # =========================
    # Search
    # =========================
    results = search_parts(cursor, normalized_query)

    print("\n Top Matching Parts:")
    for part, desc, score in results:
        print(f"- {part} (score: {round(score, 3)})")
        print(f"  Description: {desc}\n")

conn.close()