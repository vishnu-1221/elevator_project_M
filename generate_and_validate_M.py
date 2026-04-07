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
# AGENT 1: GENERATOR (MULTI-SYMPTOM + WEB SEARCH)
# =========================
def generate_symptom(part, feedback=None):

    prompt = f"""
You are an expert elevator fault diagnosis AI.

Spare Part: {part}

Task:
Generate the most important observable symptoms caused by failure of this component.

IMPORTANT:
- You MUST use web search to ensure real-world accuracy
- Do NOT rely only on internal knowledge
- Select the most common real-world failure symptoms

Output Rules:
- If only one valid symptom exists → return ONE
- If multiple exist → return up to MAXIMUM 5
- Do NOT force 5 if fewer are sufficient

Requirements (for EACH symptom):
- Must be a direct and immediate consequence of failure
- Must be specific to this component
- Must reflect real-world observable behavior
- Must NOT be generic or system-level

{f"""
Previous attempt was rejected.

Feedback:
{feedback}

Correct ONLY the issues mentioned.
Do NOT reuse wording.
""" if feedback else ""}

CRITICAL:
- Return output as a numbered list
- Each symptom must be ONE clear technical sentence
- Do NOT include explanation or extra text

Example:
1. ...
2. ...
"""

    response = client.messages.create(
        model="claude-sonnet-4.6",
        max_tokens=400,
        temperature=0.3,

        tools=[{
            "type": "web_search",
            "max_uses": 2
        }],

        tool_choice={"type": "web_search"},

        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.content[0].text.strip()


# =========================
# AGENT 2: VALIDATOR (MULTI-SYMPTOM STRICT)
# =========================
def validate_symptom(part, symptom):

    prompt = f"""
You are a highly strict elevator fault diagnosis validator.

Spare Part: {part}
Generated Symptoms:
{symptom}

Validate EACH symptom individually.

ACCEPT a symptom ONLY IF:
- Direct and immediate failure effect
- Technically precise
- Real-world observable
- Component-specific

REJECT a symptom IF:
- Indirect
- Generic
- System-level
- Weak causality
- Lacks specificity

CRITICAL:
- Be extremely strict
- Even 90% correct → REJECT that symptom
- Do NOT explain beyond required format

Response format:

If ALL symptoms are valid:
VALID

If ANY symptom is invalid:
INVALID:
- Symptom <number>: <reason>
"""

    response = client.messages.create(
        model="claude-sonnet-4.6",
        max_tokens=300,
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.content[0].text.strip()


# =========================
# AGENT LOOP
# =========================
MAX_ATTEMPTS = 5

for part_id, part_name in rows:
    print(f"\nProcessing: {part_name}")

    feedback = None
    success = False

    for attempt in range(MAX_ATTEMPTS):
        try:
            symptoms = generate_symptom(part_name, feedback)
            print(f"\nAttempt {attempt+1}:\n{symptoms}")

            validation = validate_symptom(part_name, symptoms)

            if validation.startswith("VALID"):
                print("✅ Accepted")

                cursor.execute("""
                UPDATE lift_parts
                SET description = ?
                WHERE id = ?
                """, (symptoms, part_id))

                success = True
                break

            else:
                print("❌ Rejected:", validation)

                feedback = f"""
You are correcting previously rejected symptoms.

Spare Part: {part_name}

Previous Symptoms:
{symptoms}

Validator Feedback:
{validation}

Task:
- Identify incorrect symptoms
- Fix ONLY those symptoms
- Keep correct ones unchanged

Requirements:
- Direct failure-to-symptom causality
- Component-specific
- No generic/system-level issues

CRITICAL:
- Return corrected symptoms as a numbered list
- Each symptom must be ONE sentence
- No explanation
"""

        except Exception as e:
            print("⚠️ Error:", e)
            time.sleep(2)

    if not success:
        print("⚠️ Failed after max attempts")

# =========================
# SAVE & CLOSE
# =========================
conn.commit()
conn.close()

print("\nClaude Agent Loop Completed")

