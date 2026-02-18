import json
import re
import sys

# ... (Include necessary functions from verify_week.py) ...
# I will just write a minimal debug script

def load_json_concatenated(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        objects = []
        decoder = json.JSONDecoder()
        pos = 0
        content = content.strip()
        while pos < len(content):
            while pos < len(content) and content[pos].isspace(): pos += 1
            if pos >= len(content): break
            obj, idx = decoder.raw_decode(content[pos:])
            objects.append(obj)
            pos += idx
        flat_list = []
        for o in objects:
            if isinstance(o, list): flat_list.extend(o)
            else: flat_list.append(o)
        return flat_list
    except: return []

def debug():
    vocab_data = load_json_concatenated('vocab_plan.txt')
    week_vocab = next((w for w in vocab_data if w.get('week') == 14), None)

    l2_words = [v['word'] for v in week_vocab.get('l2_vocab', [])]
    l2_idioms = [v['idiom'] for v in week_vocab.get('l2_idioms', [])]
    all_l2 = l2_words + l2_idioms

    print("Loaded L2 Vocab:")
    for v in all_l2:
        print(f"  Raw: '{v}', Core: '{v.split('(')[0].strip()}'")

    with open('batch14_week14.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Get text
    text = ""
    for q in data[0]['part3']:
        text += q['model_answer'] + " "

    print("\nOriginal Text Sample:")
    print(text[:200])

    # Cleaning logic from verify_week.py
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = text.strip()

    print("\nCleaned Text Sample:")
    print(text[:200])

    print("\nChecking Matches:")
    text_lower = text.lower()
    for v in all_l2:
        core = v.split('(')[0].strip()
        if core.lower() not in text_lower:
            print(f"  [FAIL] '{core}' not found in text.")
        else:
            print(f"  [PASS] '{core}' found.")

if __name__ == "__main__":
    debug()
