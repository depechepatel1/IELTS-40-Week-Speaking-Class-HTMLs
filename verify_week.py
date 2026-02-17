import json
import re
import sys

def load_json_concatenated(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        objects = []
        decoder = json.JSONDecoder()
        pos = 0
        content = content.strip()
        while pos < len(content):
            while pos < len(content) and content[pos].isspace():
                pos += 1
            if pos >= len(content):
                break

            try:
                obj, idx = decoder.raw_decode(content[pos:])
                objects.append(obj)
                pos += idx
            except json.JSONDecodeError:
                pos += 1

        flat_list = []
        for o in objects:
            if isinstance(o, list):
                flat_list.extend(o)
            else:
                flat_list.append(o)
        return flat_list
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_text(text):
    # Remove the Brainstorming Ideas section if present
    if 'Brainstorming Ideas:' in text:
        text = text.split('Brainstorming Ideas:')[0]

    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    return text.strip()

def count_words(text):
    return len(clean_text(text).split())

def check_highlighting(text):
    errors = []
    # Only check main body, not appended notes
    main_body = text.split('Brainstorming Ideas:')[0] if 'Brainstorming Ideas:' in text else text

    if '<span style="color: blue;">' not in main_body:
        errors.append("Missing Blue Sentence Starter")
    if '<b>' not in main_body:
        errors.append("Missing Bold Vocab")
    if '<span style="background-color: yellow;">' not in main_body:
        errors.append("Missing Yellow Complex Sentence")
    return errors

def check_ore_structure(text):
    errors = []
    if '<b>[Opinion]</b>' not in text:
        errors.append("Missing [Opinion] tag")
    if '<b>[Reason]</b>' not in text:
        errors.append("Missing [Reason] tag")
    if '<b>[Example]</b>' not in text:
        errors.append("Missing [Example] tag")
    return errors

def check_vocab_presence(text, vocab_list):
    missing = []
    # Check only main body
    main_body = text.split('Brainstorming Ideas:')[0] if 'Brainstorming Ideas:' in text else text
    text_lower = main_body.lower()

    for v in vocab_list:
        core_word = v.split('(')[0].strip()
        if core_word.lower() not in text_lower:
            missing.append(core_word)
    return missing

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 verify_week.py <week_num> <json_file>")
        return

    week_num = int(sys.argv[1])
    json_file = sys.argv[2]

    try:
        content = load_json(json_file)
        vocab_data = load_json_concatenated('vocab_plan.txt')
    except Exception as e:
        print(f"Error loading files: {e}")
        return

    week_vocab = next((w for w in vocab_data if w.get('week') == week_num), None)
    if not week_vocab:
        print(f"Week {week_num} vocab not found in vocab_plan.txt.")
        return

    l1_words = [v['word'] for v in week_vocab.get('l1_vocab', [])]
    l1_idioms = [v['idiom'] for v in week_vocab.get('l1_idioms', [])]
    all_l1_vocab = l1_words + l1_idioms

    l2_words = [v['word'] for v in week_vocab.get('l2_vocab', [])]
    l2_idioms = [v['idiom'] for v in week_vocab.get('l2_idioms', [])]
    all_l2_vocab = l2_words + l2_idioms

    print(f"Validating Week {week_num} from {json_file}...")

    week_content = next((item for item in content if item.get('week') == week_num), None)
    if not week_content:
        print(f"Week {week_num} content not found in {json_file}")
        return

    # --- L1 Validation ---
    print("\n--- L1 Part 2 Validation ---")
    l1_questions = week_content.get('l1_part2_questions', [])
    for q in l1_questions:
        ans = q.get('model_answer', '')
        w_count = count_words(ans)
        print(f"Q: {q['id']} Words: {w_count}")

        if not (90 <= w_count <= 110):
            print(f"  [FAIL] Length {w_count} not in 90-110")

        hl_errors = check_highlighting(ans)
        if hl_errors:
            print(f"  [FAIL] Highlighting: {hl_errors}")

        missing = check_vocab_presence(ans, all_l1_vocab)
        if missing:
             print(f"  [FAIL] Missing Vocab: {missing}")
        else:
             print("  [PASS] All vocab present.")

        # Check if prompts and bullets are present (basic check)
        if 'Brainstorming Ideas:' not in ans:
             print("  [FAIL] Missing appended Brainstorming Ideas")

    # --- L2 Validation ---
    print("\n--- L2 Part 3 Validation ---")
    l2_combined_text = ""
    l2_questions = week_content.get('l2_part3_questions', [])
    for q in l2_questions:
        ans = q.get('model_answer', '')
        w_count = count_words(ans)
        l2_combined_text += ans + " "
        print(f"Q: {q['id']} Words: {w_count}")

        if not (50 <= w_count <= 70):
             print(f"  [FAIL] Length {w_count} not in 50-70")

        hl_errors = check_highlighting(ans)
        if hl_errors:
            print(f"  [FAIL] Highlighting: {hl_errors}")

        ore_errors = check_ore_structure(ans)
        if ore_errors:
            print(f"  [FAIL] O-R-E Structure: {ore_errors}")
        else:
            print("  [PASS] O-R-E Structure valid.")

        if 'idea_suggestions' not in q or len(q['idea_suggestions']) != 1:
            print(f"  [FAIL] Missing or incorrect idea_suggestions (found {len(q.get('idea_suggestions', []))})")

    print("\nChecking L2 Vocab Coverage (Set)...")
    missing_l2 = check_vocab_presence(l2_combined_text, all_l2_vocab)
    if missing_l2:
        print(f"  [FAIL] Missing L2 Vocab in set: {missing_l2}")
    else:
        print("  [PASS] All L2 vocab present in set.")

if __name__ == "__main__":
    main()
