import json
import re
from bs4 import BeautifulSoup

def load_concatenated_json_robust(filepath):
    """Robustly loads concatenated/messy JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return []

    data = []
    decoder = json.JSONDecoder()
    pos = 0
    length = len(content)

    while pos < length:
        # Skip whitespace, commas, and stray closing brackets
        while pos < length and (content[pos].isspace() or content[pos] in ',]'):
            pos += 1

        if pos == length:
            break

        try:
            obj, end = decoder.raw_decode(content, idx=pos)
            if isinstance(obj, list):
                data.extend(obj)
            else:
                data.append(obj)
            pos = end
        except json.JSONDecodeError:
            # Try to recover by skipping one char (if garbage)
            pos += 1

    return data

def extract_keyword(text):
    # Logic from parse_data.py
    match = re.search(r'Describe (?:a|an) ([A-Za-z\s]+)(?:who|that|which|where|\.)', text, re.IGNORECASE)
    if match:
        words = match.group(1).split()
        return " ".join(words[:2]).upper()
    # Fallback: Capitalize first 2 words
    return " ".join(text.split()[:2]).upper()

def get_peer_questions(q_text, week_num):
    # Deterministic generation
    q_lower = q_text.lower()

    # Band 5 (Generic)
    if "why" in q_lower: b5 = "Why do you think that?"
    elif "how" in q_lower: b5 = "Is this the only way?"
    elif "do you think" in q_lower: b5 = "Can you give an example?"
    else: b5 = "Why?"

    # Band 6 (Specific - Heuristic)
    # Just echo a keyword or use a template
    if "advantage" in q_lower: b6 = "Are there any downsides?"
    elif "disadvantage" in q_lower: b6 = "Are there any benefits?"
    elif "problem" in q_lower: b6 = "How can we solve this?"
    elif "government" in q_lower: b6 = "Should individuals also help?"
    else: b6 = "What other examples can you think of?"

    return {"b5": b5, "b6": b6}

def main():
    curriculum = load_concatenated_json_robust('Curriculum 0 final.txt')
    print(f"Loaded {len(curriculum)} weeks.")

    output = {}

    for item in curriculum:
        week = item.get('week')
        if not week: continue

        # Part 2 Keyword
        l1 = item.get('lesson_1_part_2', {})
        q1_html = l1.get('q1', {}).get('html', '')
        q1_text = BeautifulSoup(q1_html, 'html.parser').get_text()
        keyword = extract_keyword(q1_text)

        # Part 3 Peer Questions
        l2 = item.get('lesson_2_part_3', {})
        peer_qs = []
        for i in range(1, 7):
            q_data = l2.get(f'q{i}', {})
            q_html = q_data.get('html', '')
            q_text = BeautifulSoup(q_html, 'html.parser').get_text()
            qs = get_peer_questions(q_text, week)
            peer_qs.append(qs)

        output[str(week)] = {
            "part_2_keyword": keyword,
            "part_3_peer_qs": peer_qs
        }

    with open('ai_dynamic_content.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    print("Generated ai_dynamic_content.json")

if __name__ == "__main__":
    main()
