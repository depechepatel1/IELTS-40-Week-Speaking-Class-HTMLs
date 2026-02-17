import json
import re
import sys

def load_json_concatenated(filepath):
    """Parses a file containing multiple concatenated JSON objects."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        objects = []
        decoder = json.JSONDecoder()
        pos = 0
        content = content.strip()
        while pos < len(content):
            # Skip whitespace
            while pos < len(content) and content[pos].isspace():
                pos += 1
            if pos >= len(content):
                break

            try:
                obj, idx = decoder.raw_decode(content[pos:])
                objects.append(obj)
                pos += idx
            except json.JSONDecodeError:
                # If we hit a snag, try skipping one char (simple error recovery)
                pos += 1

        # Flatten the list of lists if necessary
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
    # Remove Brainstorming Ideas section for word count
    if 'Brainstorming Ideas:' in text:
        text = text.split('Brainstorming Ideas:')[0]

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove glosses like [你好]
    text = re.sub(r'\[.*?\]', '', text)
    return text.strip()

def count_words(text):
    return len(clean_text(text).split())

def check_highlighting(text):
    errors = []
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
        # Extract core word (e.g., "Diligent" from "Diligent (Adj)")
        core_word = v.split('(')[0].strip()
        # Simple inclusion check (case-insensitive)
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

    # Find vocab for this week
    week_vocab = next((w for w in vocab_data if w.get('week') == week_num), None)
    if not week_vocab:
        print(f"Week {week_num} vocab not found in vocab_plan.txt.")
        return

    # Prepare Vocab Lists
    l1_words = [v['word'] for v in week_vocab.get('l1_vocab', [])]
    l1_idioms = [v['idiom'] for v in week_vocab.get('l1_idioms', [])]
    all_l1_vocab = l1_words + l1_idioms

    l2_words = [v['word'] for v in week_vocab.get('l2_vocab', [])]
    l2_idioms = [v['idiom'] for v in week_vocab.get('l2_idioms', [])]
    all_l2_vocab = l2_words + l2_idioms

    print(f"Validating Week {week_num} from {json_file}...")

    # Find content for this week
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

        # Word Count Check
        len_status = "PASS" if 90 <= w_count <= 110 else f"FAIL ({w_count})"

        # Vocab Check (Individual Answer must contain relevant vocab,
        # BUT usually vocab is split across answers or all expected in one?
        # The prompt implies strictly using the list.
        # Usually Part 2 answers should use target vocab.
        # Strategy: Check if *at least some* vocab is used, or ALL?
        # Previous strategy: The prompt said "Highlight vocabulary list words".
        # I will check if the answer contains vocab from the list.
        # Actually, typically for these tasks, the set of vocab is distributed or specific words are assigned.
        # However, checking for *missing* vocab from the *entire* list in *one* answer might be too strict if the list is huge.
        # But wait, looking at Week 6-9, the user requirements were strict.
        # Let's check for Missing Vocab based on the text provided.
        # Actually, let's just print missing ones for information, but require Highlighting.

        hl_errors = check_highlighting(ans)

        # Identify which vocab words are actually in the text
        present_vocab = [v.split('(')[0].strip() for v in all_l1_vocab if v.split('(')[0].strip().lower() in ans.lower()]

        print(f"Q: {q['id']} | Words: {w_count} [{len_status}] | Vocab Used: {len(present_vocab)}/{len(all_l1_vocab)}")
        if hl_errors:
            print(f"  [FAIL] Formatting: {hl_errors}")

        # We want to ensure specific vocab is used.
        # Ideally, we want 100% coverage across the week? Or per question?
        # In Part 2, typically we want to showcase as much as possible.
        # Let's flag if coverage is very low (<3 words).
        if len(present_vocab) < 3:
             print("  [WARN] Low vocab usage.")

    # --- L2 Validation ---
    print("\n--- L2 Part 3 Validation ---")
    l2_combined_text = ""
    l2_questions = week_content.get('l2_part3_questions', [])
    for q in l2_questions:
        ans = q.get('model_answer', '')
        w_count = count_words(ans)
        l2_combined_text += ans + " "

        len_status = "PASS" if 50 <= w_count <= 70 else f"FAIL ({w_count})"

        hl_errors = check_highlighting(ans)
        ore_errors = check_ore_structure(ans)

        print(f"Q: {q['id']} | Words: {w_count} [{len_status}]")
        if hl_errors: print(f"  [FAIL] Formatting: {hl_errors}")
        if ore_errors: print(f"  [FAIL] Structure: {ore_errors}")

    # Check Total L2 Vocab Coverage across all Part 3 answers
    print("\nChecking L2 Vocab Coverage (Collective)...")
    missing_l2 = check_vocab_presence(l2_combined_text, all_l2_vocab)
    if missing_l2:
        print(f"  [FAIL] Missing L2 Vocab: {missing_l2}")
    else:
        print("  [PASS] All L2 vocab present across questions.")

if __name__ == "__main__":
    main()
