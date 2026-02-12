import json
import re

def load_json_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to parse the first JSON array if multiple are concatenated
        try:
            # Find the first closing square bracket that balances the first opening one
            # But a simpler heuristic: The file likely contains multiple [...] blocks.
            # Let's split by "][" or "]\n["
            # Or just Regex to capture the first [...] block
            match = re.search(r'\[.*?\]', content, re.DOTALL) # This might be greedy and capture everything if nested? No, JSON arrays nest.

            # Better approach: Use raw string searching
            depth = 0
            json_str = ""
            start = content.find('[')
            if start == -1: return []

            for i, char in enumerate(content[start:], start):
                json_str += char
                if char == '[':
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        break
            return json.loads(json_str)
        except Exception as e:
            print(f"Error extracting JSON from {filepath}: {e}")
            return []

def extract_week_1():
    print("Loading data files...")

    # Load Curriculum
    curriculum_data = load_json_file('Curriculum 0 final.txt')
    week_1_curriculum = next((item for item in curriculum_data if item["week"] == 1), None)

    if not week_1_curriculum:
        print("CRITICAL: Week 1 not found in Curriculum!")
        return

    # Load Vocab
    vocab_data = load_json_file('vocab_plan.txt')
    week_1_vocab = next((item for item in vocab_data if item["week"] == 1), None)

    if not week_1_vocab:
        print("CRITICAL: Week 1 not found in Vocab Plan!")
        return

    # Load Homework
    homework_data = load_json_file('homework_plan.json')
    week_1_homework = next((item for item in homework_data if item["week"] == 1), None)

    if not week_1_homework:
        print("CRITICAL: Week 1 not found in Homework Plan!")
        return

    # Consolidate Data
    week_1_data = {
        "meta": {
            "week": 1,
            "topic": week_1_curriculum["topic"]
        },
        "curriculum": week_1_curriculum,
        "vocab": week_1_vocab,
        "homework": week_1_homework
    }

    # Save to file
    with open('week_1_data.json', 'w', encoding='utf-8') as f:
        json.dump(week_1_data, f, indent=4, ensure_ascii=False)

    print("✅ Week 1 data extracted to 'week_1_data.json'")

if __name__ == "__main__":
    extract_week_1()
