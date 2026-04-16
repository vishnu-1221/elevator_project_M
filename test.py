import os
import time
from anthropic import Anthropic
from dotenv import load_dotenv

# =========================
# LOAD ENV
# =========================
load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# =========================
# EXTRACT TEXT
# =========================
def extract_text(response):
    texts = []
    for block in response.content:
        if block.type == "text":
            texts.append(block.text.strip())
    return "\n".join(texts)

# =========================
# CLEAN EVIDENCE
# =========================
def clean_evidence(evidence):
    cleaned = []

    for line in evidence.split("\n"):
        line = line.strip()

        if not line:
            continue
        if "shutdown" in line.lower():
            continue
        if "unlevel" in line.lower():
            continue
        if "system" in line.lower():
            continue
        if len(line) < 10:
            continue

        cleaned.append(line)

    return "\n".join(cleaned)

# =========================
# CLEAN SOURCES
# =========================
def clean_sources(text):
    sources = []

    if "Sources:" in text:
        raw = text.split("Sources:")[-1].split("\n")

        for s in raw:
            s = s.strip()
            if s.startswith("http"):
                sources.append(s)

    return "\n".join(sources) if sources else "No valid sources"

# =========================
# TOOL HANDLER WITH QUERY PRINT
# =========================
def call_with_tools(params):
    response = client.messages.create(**params)

    while True:
        tool_calls = [b for b in response.content if b.type == "tool_use"]

        if not tool_calls:
            return response

        print("\n================ TOOL DEBUG ================")

        tool_results = []

        for tool in tool_calls:
            print(f"🌐 Tool Used: {tool.name}")

            # 🔥 PRINT EXACT INTERNAL QUERY
            if hasattr(tool, "input"):
                print("🔎 Internal Search Query:")
                print(tool.input)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool.id,
                "content": "Search executed"
            })

        print("===========================================")

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

# =========================
# SEARCH AGENT
# =========================
def search_evidence(part_name):

    prompt = f"""
Search for real-world observable failure symptoms of: {part_name}

STRICT INSTRUCTIONS:
- Use web search
- Extract ONLY symptoms directly caused by THIS component
- Ignore system-level effects (shutdown, unleveling, etc.)
- Return clean bullet points (max 8)
- No explanations

Sources:
- Include only valid full URLs
- Remove broken links
"""

    params = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "tools": [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 2
        }],
        "tool_choice": {"type": "tool", "name": "web_search"},
        "messages": [{"role": "user", "content": prompt}]
    }

    response = call_with_tools(params)
    raw_text = extract_text(response)

    evidence = clean_evidence(raw_text)
    sources = clean_sources(raw_text)

    return evidence, sources

# =========================
# GENERATOR
# =========================
def generate_from_evidence(part_name, evidence):

    prompt = f"""
Part: {part_name}

Evidence:
{evidence}

Task:
Generate up to 5 observable failure symptoms.

Rules:
- ONLY use evidence
- Ignore anything not specific to this component
- No guessing
- No extra text

Output:
1. ...
2. ...
"""

    params = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 200,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = client.messages.create(**params)
    return extract_text(response)

# =========================
# RUN TEST
# =========================
def run_test(part_name):

    print("\n==============================")
    print(f"🔧 PART: {part_name}")
    print("==============================")

    # 🔎 SEARCH
    evidence, sources = search_evidence(part_name)

    print("\n📄 CLEANED EVIDENCE:\n")
    print(evidence)

    print("\n🔗 CLEAN SOURCES:\n")
    print(sources)

    time.sleep(2)

    # ⚙️ GENERATE
    symptoms = generate_from_evidence(part_name, evidence)

    print("\n⚙️ GENERATED SYMPTOMS:\n")
    print(symptoms)

    print("\n==============================")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    run_test("Elevator door motor")