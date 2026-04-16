import sqlite3
import time
import os
from anthropic import Anthropic
from dotenv import load_dotenv

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# =========================
# DB CONNECTION
# =========================
conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

cursor.execute("SELECT id, spare_part FROM lift_parts WHERE description IS NULL")
rows = cursor.fetchall()

# =========================
# CACHE
# =========================
evidence_cache = {}
structured_cache = {}

# =========================
# RESPONSE PARSER
# =========================
def extract_text(response):
    return "\n".join(
        block.text.strip()
        for block in response.content
        if block.type == "text"
    ).strip()

# =========================
# CLEAN EVIDENCE
# =========================
def clean_evidence(text):
    cleaned = []

    for line in text.split("\n"):
        line = line.strip()

        if not line:
            continue
        if line.startswith("##"):
            continue
        if "sources" in line.lower():
            continue
        if "shutdown" in line.lower():
            continue
        if "system" in line.lower():
            continue
        if len(line) < 10:
            continue

        cleaned.append(line)

    return "\n".join(cleaned[:25])  # limit size

# =========================
# EXTRACT SOURCES
# =========================
def extract_sources(text):
    sources = []

    for line in text.split("\n"):
        line = line.strip()
        if "http://" in line or "https://" in line:
            url = line.split(" ")[-1]
            if url.startswith("http"):
                sources.append(url)

    return "\n".join(sources) if sources else "No valid sources"

# =========================
# MODEL CALL (WITH BACKOFF)
# =========================
def call_model(params):
    delay = 2

    for _ in range(5):
        try:
            response = client.messages.create(**params)

            while True:
                tool_calls = [b for b in response.content if b.type == "tool_use"]

                if not tool_calls:
                    return response

                tool_results = []
                for tool in tool_calls:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool.id,
                        "content": "Search completed"
                    })

                response = client.messages.create(
                    model=params["model"],
                    max_tokens=params["max_tokens"],
                    messages=[
                        *params["messages"],
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results}
                    ],
                    tools=params.get("tools", [])
                )

        except Exception as e:
            if "rate_limit_error" in str(e):
                print(f"⏳ Rate limited, retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                print("⚠️ Model call failed:", e)
                time.sleep(2)

    return None

# =========================
# SEARCH
# =========================
def get_evidence(part):
    if part in evidence_cache:
        return evidence_cache[part]

    prompt = f"""
Search for real-world observable failure symptoms of: {part}

STRICT:
- Only component-specific symptoms
- No system-level effects
- No explanations
- Bullet format only

Sources:
- Include valid URLs only
"""

    params = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 350,
        "tools": [{
            "type": "web_search_20250305",
            "name": "web_search"
        }],
        "tool_choice": {"type": "tool", "name": "web_search"},
        "messages": [{"role": "user", "content": prompt}]
    }

    response = call_model(params)

    if not response:
        return "", ""

    raw = extract_text(response)

    evidence = clean_evidence(raw)
    sources = extract_sources(raw)

    evidence_cache[part] = (evidence, sources)

    time.sleep(3)
    return evidence, sources

# =========================
# STRUCTURED EXTRACTION
# =========================
def extract_structured_evidence(part, evidence):
    if part in structured_cache:
        return structured_cache[part]

    prompt = f"""
Part: {part}

Evidence:
{evidence}

Task:
Extract ALL observable failure symptoms.

STRICT:
- Do NOT miss any symptom
- Do NOT summarize loosely
- Merge duplicates only
- Keep concise but COMPLETE

Output:
- Bullet points only
"""

    params = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 150,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = call_model(params)

    structured = extract_text(response) if response else ""
    structured_cache[part] = structured

    time.sleep(3)
    return structured

# =========================
# GENERATOR (QUALITY FIRST)
# =========================
def generate_from_evidence(part, evidence, feedback=None):

    prompt = f"""
Part: {part}

Evidence:
{evidence}

Task:
Generate observable failure symptoms.

STRICT:
- ONLY use evidence
- Must be directly observable
- Must be component-specific
- Include ONLY strong, high-confidence symptoms
- Do NOT force number of outputs
- If only 2–3 good symptoms exist, return only those
- Maximum 5 allowed

{f"Fix only these:\n{feedback}" if feedback else ""}

Output:
1. ...
2. ...
"""

    params = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 180,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = call_model(params)
    return extract_text(response) if response else "ERROR"

# =========================
# VALIDATOR (VERY STRICT)
# =========================
def validate_with_evidence(part, symptoms, evidence):

    prompt = f"""
Part: {part}

Evidence:
{evidence}

Symptoms:
{symptoms}

STRICT VALIDATION:

For EACH symptom:
- Must be explicitly present in evidence
- If slightly inferred → REJECT
- If generic → REJECT
- If not physically observable → REJECT
- If not clearly component-specific → REJECT

If ANY symptom fails → INVALID

Return ONLY:

VALID

OR

INVALID:
- Symptom X: exact reason
"""

    params = {
        "model": "claude-sonnet-4-20250514",
        "temperature": 0,
        "max_tokens": 150,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = call_model(params)
    return extract_text(response) if response else "INVALID"

# =========================
# EXTRACT REJECTED
# =========================
def extract_rejected(text):
    return "\n".join(
        line for line in text.split("\n")
        if line.strip().startswith("-")
    )

# =========================
# MAIN LOOP
# =========================
MAX_ATTEMPTS = 3

for part_id, part_name in rows:
    print("\n==============================")
    print(f"Processing: {part_name}")

    raw_evidence, sources = get_evidence(part_name)

    if len(raw_evidence) < 20:
        print("⚠️ Weak evidence")
        continue

    structured_evidence = extract_structured_evidence(part_name, raw_evidence)

    feedback = None

    for attempt in range(MAX_ATTEMPTS):
        symptoms = generate_from_evidence(part_name, structured_evidence, feedback)

        print(f"\nAttempt {attempt+1}:\n{symptoms}")

        if "ERROR" in symptoms:
            continue

        validation = validate_with_evidence(part_name, symptoms, structured_evidence)

        if validation.startswith("VALID"):
            print("✅ Accepted")

            final_output = f"{symptoms}\n\nSources:\n{sources}"

            cursor.execute("""
            UPDATE lift_parts
            SET description = ?, extracted_text = ?
            WHERE id = ?
            """, (final_output, structured_evidence, part_id))

            break
        else:
            print("❌ Rejected:", validation)
            feedback = extract_rejected(validation)

    time.sleep(4)

# =========================
# SAVE
# =========================
conn.commit()
conn.close()

print("\n✅ Production Pipeline Completed")