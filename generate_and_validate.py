import sqlite3
import time
import os
from openai import OpenAI
from dotenv import load_dotenv

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(" OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)

# =========================
# DB CONNECTION
# =========================
conn = sqlite3.connect("lift.db")
cursor = conn.cursor()

cursor.execute("SELECT id, spare_part FROM lift_parts WHERE description IS NULL")
rows = cursor.fetchall()


# =========================
# AGENT 1: GENERATOR (GPT-5 OPTIMIZED)
# =========================
def generate_symptom(part, feedback=None):

    prompt = f"""
You are an expert elevator fault diagnosis AI.

Spare Part: {part}

Task:
Generate ONE precise, realistic observable symptom caused by failure of this component.

Think internally:
- What is the component’s primary function?
- What is the most common failure mode?
- What is the direct observable effect?

{f"""
Previous attempt was rejected.

Feedback:
{feedback}

Correct the issue and generate an improved symptom.
- Do NOT reuse wording from previous attempt
""" if feedback else ""}

Requirements:
- Must reflect a DIRECT consequence of failure
- Must be specific to this component
- Must be realistic in real elevator systems
- Avoid generic or system-level descriptions

Output:
Return ONLY ONE clear technical sentence.
"""

    response = client.chat.completions.create(
        model="gpt-5.4",   # 🔥 UPGRADED MODEL
        temperature=0.3,   # better diversity for strong model
        messages=[
            {"role": "system", "content": "You are a professional elevator diagnostics assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()


# =========================
# AGENT 2: VALIDATOR (SIMPLIFIED FOR GPT-5)
# =========================
def validate_symptom(part, symptom):

    prompt = f"""
You are a highly strict elevator fault diagnosis validator.

Spare Part: {part}
Generated Symptom: {symptom}

Your job is to REJECT anything that is not PERFECTLY accurate.

Step 1: Identify component function internally
Step 2: Identify most common failure modes
Step 3: Check if symptom is a DIRECT and PRIMARY effect

STRICT VALIDATION RULES:

ACCEPT ONLY IF ALL ARE TRUE:
- The symptom is a direct and immediate result of THIS component failing
- The failure-to-symptom mapping is technically precise
- The symptom reflects a real-world observable behavior
- The symptom is NOT generic or reusable

REJECT IF ANY ONE IS TRUE:
- Symptom is indirect (chain reaction, not primary failure)
- Symptom is too generic (e.g., "elevator not working properly")
- Symptom describes system-level behavior instead of component-level
- Weak or unclear causality
- Missing mechanical/electrical specificity

CRITICAL RULE:
Even if the symptom is 80–90% correct → REJECT IT.

You must be extremely strict. Default to rejection unless it is undeniably precise.

Response format:
VALID
OR
INVALID: <very specific technical reason>
"""
    response = client.chat.completions.create(
        model="gpt-5.4", 
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a strict engineering validator."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()


# =========================
# AGENT LOOP EXECUTION
# =========================
MAX_ATTEMPTS = 5

for part_id, part_name in rows:
    print(f"\n Processing: {part_name}")

    feedback = None
    success = False

    for attempt in range(MAX_ATTEMPTS):
        try:
            # Step 1: Generate
            symptom = generate_symptom(part_name, feedback)
            print(f"\nAttempt {attempt + 1}:\n{symptom}")

            # Step 2: Validate
            validation = validate_symptom(part_name, symptom)

            if validation.startswith("VALID"):
                print("✅ Accepted")

                cursor.execute("""
                UPDATE lift_parts
                SET description = ?
                WHERE id = ?
                """, (symptom, part_id))

                success = True
                break

            else:
                print("❌ Rejected:", validation)

                # FEEDBACK LOOP
                feedback = f"""
The previous symptom was rejected.

Spare Part: {part_name}
Previous Symptom: {symptom}

Validator Feedback:
{validation}

Your task is to CORRECT the issue based on the validator feedback.

Instructions:
- Carefully analyze the validator feedback and understand the exact reason for rejection
- Identify what is wrong in the previous symptom
- Fix ONLY the issue mentioned in the feedback
- Do not introduce new issues while fixing

Requirements:
- Ensure strong and direct failure-to-symptom causality
- Ensure the symptom is specific to this component
- Avoid generic or system-level descriptions
- Do NOT reuse wording or structure from the previous attempt

Output:
Generate ONE corrected and improved symptom.
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

print("\n GPT-5 Agent Loop Completed")