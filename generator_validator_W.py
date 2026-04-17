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
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in .env")

client = Anthropic(api_key=api_key)

# =========================
# DB CONNECTION
# =========================
conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

cursor.execute("SELECT id, spare_part FROM lift_parts WHERE description IS NULL")
rows = cursor.fetchall()

# =========================
# SAFE TEXT EXTRACTOR
# =========================
def extract_text(response):
    texts = []
    for block in response.content:
        if hasattr(block, "text"):
            texts.append(block.text)
    return "\n".join(texts).strip()

# =========================
# SOURCE DETECTION (DEBUG ONLY)
# =========================
def detect_source(response):
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            if getattr(block, "name", "") == "web_search":
                return "WEB"
    return "MODEL"

# =========================
# GENERATOR (SMART WEB USAGE)
# =========================
def generate_symptom(part):

    prompt = f"""
You are an expert elevator fault diagnosis AI.

Spare Part: {part}

Task:
Generate real-world lift behavior symptoms caused by failure of this component.

IMPORTANT:
- Use web search if the component is specific, uncommon, or not widely known
- If you are not highly confident about the exact failure behavior, you MUST use web search
- Do NOT assume based on similar components
- Do NOT generalize from related parts
- Prefer web search over guessing
- If unsure, do not produce symptoms without grounding in real-world behavior

STRICT REQUIREMENTS:
- Generate 8 to 10 symptoms
- Each symptom must describe how the LIFT behaves
- Must be directly caused by this component failure
- Must NOT be generic or vague

CRITICAL:
- Describe ONLY lift/system behavior
- Do NOT describe internal component conditions
- Do NOT mention voltage, resistance, testing, or measurements
- Do NOT describe physical damage
- Each symptom must be ONE sentence
- Each symptom MUST be a COMPLETE sentence
- Do NOT leave any sentence unfinished
- Do NOT cut off mid-sentence
- Ensure all points are fully written before ending
- No explanations

Output:
Numbered list
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=700,
        temperature=0.3,

        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 1
        }],

        tool_choice={"type": "auto"},

        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    text = extract_text(response)
    source = detect_source(response)

    return text, source

# =========================
# VALIDATOR (STRICT FILTER)
# =========================
def validate_symptom(part, symptom):

    prompt = f"""
You are a highly strict elevator fault diagnosis validator.

Spare Part: {part}
Generated Symptoms:
{symptom}

Task:
Select ONLY the symptoms that are 100% correct lift behaviors caused by this component.

ACCEPT ONLY IF:
- Clearly and directly caused by THIS component
- Observable in real-world elevator operation
- Strongly specific to this component
- Commonly expected in real-world scenarios
- Would NOT occur if this component were functioning correctly

REJECT IF:
- Could be caused by multiple components
- Generic lift issue
- Weak or indirect causality
- Rare or unrealistic scenario
- Belongs to another subsystem (intercom, alarm, etc.)
- Mentions internal condition, measurement, or testing

CRITICAL:
- Prefer fewer high-confidence symptoms
- Do NOT try to fill a quota
- It is acceptable to return any number (including 0)

🚨 HARD RULE:
Return ONLY final answer. No explanation.

FORMAT:

VALID:
1. ...
2. ...
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return extract_text(response)

# =========================
# PARSER
# =========================
def extract_valid_symptoms(validation_text):

    lines = validation_text.split("\n")
    valid = []
    capture = False

    for line in lines:
        line = line.strip()

        if line.startswith("VALID"):
            capture = True
            continue

        if capture and line:
            if line[0].isdigit():
                line = line.split(".", 1)[-1].strip()
            valid.append(line)

    return valid

# =========================
# MAIN PIPELINE
# =========================
for part_id, part_name in rows:
    print(f"\nProcessing: {part_name}")

    try:
        # Generate
        symptoms, source = generate_symptom(part_name)

        print("\nGenerated:\n", symptoms)
        print(f"\nSOURCE: {source}")

        # Validate
        validation = validate_symptom(part_name, symptoms)
        print("\nValidated:\n", validation)

        # Extract valid
        valid_symptoms = extract_valid_symptoms(validation)

        if valid_symptoms:
            final_output = "\n".join(
                [f"{i+1}. {s}" for i, s in enumerate(valid_symptoms)]
            )

            print("\n✅ Stored:\n", final_output)

            cursor.execute("""
            UPDATE lift_parts
            SET description = ?
            WHERE id = ?
            """, (final_output, part_id))

        else:
            print("⚠️ No valid symptoms found")

        # Prevent rate limit
        time.sleep(3)

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(5)

# =========================
# SAVE & CLOSE
# =========================
conn.commit()
conn.close()

print("\nClaude Pipeline Completed")