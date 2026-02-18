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
    if 'Brainstorming Ideas:' in text:
        text = text.split('Brainstorming Ideas:')[0]
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    return text.strip()

def count_words(text):
    return len(clean_text(text).split())

def check_highlighting(text):
    errors = []
    main_body = text.split('Brainstorming Ideas:')[0] if 'Brainstorming Ideas:' in text else text
    if '<span style="color: blue;">' not in main_body:
        errors.append("Missing Blue Sentence Starter")
    # For Plain text answers (Q2/Q3 Part 2), highlighting is NOT expected.
    return errors

def check_ore_structure(text):
    errors = []
    if '<b>[Opinion]</b>' not in text:
        errors.append("Missing [Opinion]")
    if '<b>[Reason]</b>' not in text:
        errors.append("Missing [Reason]")
    if '<b>[Example]</b>' not in text:
        errors.append("Missing [Example]")
    return errors

def check_vocab_presence(text, vocab_list):
    missing = []
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

    print(f"DEBUG: Week {week_num} vocab data found.")

    l1_words = [v['word'] for v in week_vocab.get('l1_vocab', [])]
    l1_idioms = [v['idiom'] for v in week_vocab.get('l1_idioms', [])]
    all_l1_vocab = l1_words + l1_idioms

    l2_words = [v['word'] for v in week_vocab.get('l2_vocab', [])]
    l2_idioms = [v['idiom'] for v in week_vocab.get('l2_idioms', [])]
    all_l2_vocab = l2_words + l2_idioms

    print(f"Validating Week {week_num} from {json_file}...")

    # Iterate over all items in the list that match the week
    week_items = [item for item in content if item.get('week') == week_num]

    if not week_items:
        print(f"No content found for Week {week_num}")
        return

    l2_combined_text = ""

    print("\n--- Validation ---")

    for item in week_items:
        if 'part2' in item:
            for q in item['part2']:
                qid = q.get('id')
                ans = q.get('model_answer', '')
                w_count = count_words(ans)
                print(f"L1 Part 2 {qid} | Words: {w_count}")

                # Check Q1 Formatting (Blue/Bold/Yellow)
                if qid == 'Q1':
                    hl_errors = check_highlighting(ans)
                    if hl_errors: print(f"  [FAIL] Formatting: {hl_errors}")

                if w_count < 90:
                    print(f"  [FAIL] Word count too low ({w_count} < 90)")

        if 'part3' in item:
            for q in item['part3']:
                qid = q.get('id')
                ans = q.get('model_answer', '')
                w_count = count_words(ans)
                l2_combined_text += ans + " "
                print(f"L2 Part 3 {qid} | Words: {w_count}")

                if w_count < 50:
                    print(f"  [FAIL] Word count too low ({w_count} < 50)")

                ore_errors = check_ore_structure(ans)
                if ore_errors: print(f"  [FAIL] Structure: {ore_errors}")

    print("\nChecking L2 Vocab Coverage (Collective)...")
    missing_l2 = check_vocab_presence(l2_combined_text, all_l2_vocab)
    if missing_l2:
        print(f"  [FAIL] Missing L2 Vocab: {missing_l2}")
    else:
        print("  [PASS] All L2 vocab present across questions.")

if __name__ == "__main__":
    main()
