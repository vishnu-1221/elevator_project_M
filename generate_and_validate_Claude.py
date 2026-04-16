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
# GENERATOR (LIFT BEHAVIOR SYMPTOMS)
# =========================
def generate_symptom(part):

    prompt = f"""
You are an expert elevator fault diagnosis AI trained on real-world maintenance scenarios.

Spare Part: {part}

Task:
Generate HIGH-QUALITY lift behavior symptoms caused by failure of this component.

STRICT REQUIREMENTS:
- Generate between 8 to 10 symptoms
- Each symptom must describe how the LIFT behaves when this component fails
- Focus on what a passenger or technician observes in lift operation
- Must be directly attributable to this component failure
- Must NOT be generic
- Must NOT be vague

CRITICAL:
- Describe ONLY lift/system behavior
- Do NOT describe internal component conditions (e.g., voltage, resistance, swelling)
- Do NOT mention measurements or testing procedures
- Do NOT describe physical damage of the component
- Each symptom must be ONE clear sentence
- No explanations

Think in terms of:
- Lift movement
- Door behavior
- Emergency operation
- Control response
- Passenger experience

Output:
Numbered list
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
# VALIDATOR (CAUSALITY-STRICT BEHAVIOR FILTER)
# =========================
def validate_symptom(part, symptom):

    prompt = f"""
You are a highly strict elevator fault diagnosis validator.

Spare Part: {part}
Generated Symptoms:
{symptom}

Task:
Select ONLY the symptoms that are 100% correct lift behaviors caused by failure of this specific component.

ACCEPT ONLY IF:
- Clearly and directly caused by failure of THIS component
- Observable in real-world elevator operation (passenger or technician perspective)
- Strongly specific to this component (not common to multiple failures)
- The symptom would NOT typically occur if this component were functioning correctly
- Describes clear lift/system behavior (what the lift does)

REJECT IF:
- Could be caused by multiple different components (not unique to this part)
- Generic lift issues (e.g., "lift not working", "door not opening")
- Weak or indirect causality
- Belongs to another subsystem (e.g., intercom, alarm, unrelated control systems)
- Describes internal component condition (e.g., voltage, resistance, swelling)
- Mentions measurements or testing procedures
- Describes physical damage of the component

CRITICAL:
- Be extremely strict about causality
- Prefer fewer high-confidence symptoms over many weak ones
- Only include symptoms that strongly indicate THIS component failure
- It is acceptable to return any number of valid symptoms (including 0)

 HARD RULE:
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