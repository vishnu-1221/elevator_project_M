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
# GENERATOR (8–10 SYMPTOMS)
# =========================
def generate_symptom(part):

    prompt = f"""
You are an expert elevator fault diagnosis AI trained on real-world maintenance scenarios.

Spare Part: {part}

Task:
Generate HIGH-QUALITY, REAL-WORLD observable failure symptoms caused by this component.

STRICT REQUIREMENTS:
- Generate between 8 to 10 symptoms
- Each symptom must reflect what a field technician can observe
- Must be directly attributable to this component failure
- Must NOT be generic
- Must NOT be vague
- Avoid deep internal explanations unless observable

CRITICAL:
- Each symptom must be ONE clear technical sentence
- No explanations
- Output as numbered list
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        temperature=0.3,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.content[0].text.strip()


# =========================
# VALIDATOR (STRICT PRECISION FILTER)
# =========================
def validate_symptom(part, symptom):

    prompt = f"""
You are a highly strict elevator fault diagnosis validator.

Spare Part: {part}
Generated Symptoms:
{symptom}

Task:
Select ONLY the symptoms that are 100% correct.

ACCEPT ONLY IF:
- Clearly and directly caused by this component failure
- Observable in real-world elevator operation
- Highly specific to this component
- No ambiguity or assumption required

REJECT IF:
- Even slightly generic
- Indirect or weak causality
- Could apply to multiple components
- Requires interpretation or assumption

CRITICAL:
- Only include symptoms that are unquestionably correct
- Do NOT try to fill a quota
- It is completely acceptable to return any number of valid symptoms (including 0)

🚨 HARD RULE:
If you include ANY explanation, your answer is WRONG.

You MUST ONLY return:

VALID:
1. ...
2. ...

No other text allowed.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.content[0].text.strip()

# =========================
# ROBUST PARSER
# =========================
def extract_valid_symptoms(validation_text):

    lines = validation_text.split("\n")
    valid = []

    # Case 1: Proper VALID format
    if "VALID:" in validation_text:
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

    else:
        # Case 2: Fallback for ✅ format
        for line in lines:
            line = line.strip()
            if "✅" in line:
                if "." in line:
                    line = line.split(".", 1)[-1].strip()
                valid.append(line)

    return valid


# =========================
# MAIN PIPELINE
# =========================
for part_id, part_name in rows:
    print(f"\nProcessing: {part_name}")

    try:
        # Step 1: Generate
        symptoms = generate_symptom(part_name)
        print("\nGenerated:\n", symptoms)

        # Step 2: Validate
        validation = validate_symptom(part_name, symptoms)
        print("\nValidated:\n", validation)

        # Step 3: Extract valid
        valid_symptoms = extract_valid_symptoms(validation)

        # 🔥 Debug fallback
        if not valid_symptoms:
            print("\n⚠️ Parser failed — raw validation output:")
            print(validation)

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

    except Exception as e:
        print("⚠️ Error:", e)
        time.sleep(2)


# =========================
# SAVE & CLOSE
# =========================
conn.commit()
conn.close()

print("\nClaude Pipeline Completed")