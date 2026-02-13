import json
import re

def load_json_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Try parsing directly
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback: Handle concatenated JSON arrays
        # The file might look like [...] [...]
        # We only need Week 1, which should be in the first array.
        # Find the first closing ']' that is at the root level.
        # Simple heuristic: find the first `]\n[` sequence.

        # Split by `]\n[` or `][`
        parts = re.split(r'\]\s*\[', content)
        if len(parts) > 1:
            # Reconstruct the first part
            first_part = parts[0] + ']'
            try:
                return json.loads(first_part)
            except Exception as e:
                print(f"Error parsing first part of {filepath}: {e}")
                return []

        # Another fallback: extract from start to first `]`
        # This is risky if `]` is inside a string, but unlikely for this file structure.
        return []

def extract():
    print("Extracting Week 1 Data...")

    # 1. Curriculum
    curriculum = load_json_file("Curriculum 0 final.txt")
    week1_curr = next((item for item in curriculum if item["week"] == 1), None)

    if not week1_curr:
        print("CRITICAL: Week 1 not found in Curriculum.")
        return

    # 2. Vocab
    vocab_list = load_json_file("vocab_plan.txt")
    week1_vocab = next((item for item in vocab_list if item["week"] == 1), None)

    if not week1_vocab:
        print("CRITICAL: Week 1 not found in Vocab Plan.")
        return

    # 3. Homework
    homework = load_json_file("homework_plan.json")
    week1_hw = next((item for item in homework if item["week"] == 1), None)

    if not week1_hw:
        print("CRITICAL: Week_1 not found in Homework Plan.")
        return

    week1_data = {
        "curriculum": week1_curr,
        "vocab": week1_vocab,
        "homework": week1_hw
    }

    with open("week_1_content.json", "w", encoding="utf-8") as f:
        json.dump(week1_data, f, indent=4, ensure_ascii=False)

    print("✅ Successfully extracted to week_1_content.json")

if __name__ == "__main__":
    extract()
