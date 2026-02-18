import json
import re

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def load_vocab_text(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def parse_vocab(content, weeks):
    # Regex to find week blocks
    vocab_data = {}

    # Split by "week":
    week_blocks = re.split(r'"week":\s*(\d+)', content)

    for i in range(1, len(week_blocks), 2):
        week_num = int(week_blocks[i])
        if week_num not in weeks:
            continue

        block = week_blocks[i+1]

        # Simple extraction using regex for vocab items
        # "word": "...", "meaning": "..."
        # We need to distinguish l1 vs l2.

        l1_section = block.split('"l2_vocab"')[0]
        l2_section = block.split('"l2_vocab"')[1] if '"l2_vocab"' in block else ""

        def extract_words(text):
            # Find all words/idioms
            # "word": "X", ... "meaning": "Y"
            # "idiom": "X", ... "meaning": "Y"
            items = []
            # Combine regex for word and idiom
            # We want the word/idiom string and the meaning string

            # Simple approach: Find "word": "(.*?)" ... "meaning": "(.*?)"
            # This is brittle if order changes, but consistent in file.

            # Better: manually parse the pseudo-json
            # It looks valid JSON fragment. Let's try to repair it to a list?
            # It's actually a list of objects.

            # Let's just regex specific keys
            # L1 Vocab
            words = re.findall(r'"word":\s*"(.*?)".*?"meaning":\s*"(.*?)"', text, re.DOTALL)
            idioms = re.findall(r'"idiom":\s*"(.*?)".*?"meaning":\s*"(.*?)"', text, re.DOTALL)

            return words + idioms

        vocab_data[week_num] = {
            'l1': extract_words(l1_section),
            'l2': extract_words(l2_section)
        }

    return vocab_data

def extract_data():
    target_weeks = [14, 15, 16, 17]

    # 1. Questions from Curriculum
    curr_data = load_json('Origional curriculum.txt')
    questions_data = {}

    for week in curr_data:
        w = week.get('week')
        if w in target_weeks:
            questions_data[w] = {
                'topic': week.get('topic'),
                'l1_questions': week.get('l1_part2_questions', []),
                'l2_questions': week.get('l2_part3_questions', [])
            }

    # 2. Vocab
    vocab_content = load_vocab_text('vocab_plan.txt')
    vocab_data = parse_vocab(vocab_content, target_weeks)

    # Combine
    final_data = {}
    for w in target_weeks:
        final_data[w] = {
            'questions': questions_data.get(w),
            'vocab': vocab_data.get(w)
        }

    with open('weeks_14_17_data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    print("Data extracted to weeks_14_17_data.json")

if __name__ == "__main__":
    extract_data()
