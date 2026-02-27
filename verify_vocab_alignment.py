import json
import os
from bs4 import BeautifulSoup
import re

def load_vocab_plan():
    try:
        # Load concatenated JSON logic similar to main script
        with open('vocab_plan.json', 'r', encoding='utf-8') as f:
            content = f.read()
        data = []
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(content):
            while pos < len(content) and (content[pos].isspace() or content[pos] in ',]'):
                pos += 1
            if pos == len(content): break
            try:
                obj, end = decoder.raw_decode(content, idx=pos)
                if isinstance(obj, list): data.extend(obj)
                else: data.append(obj)
                pos = end
            except json.JSONDecodeError: pos += 1
        return {item.get('week'): item for item in data}
    except Exception as e:
        print(f"Error loading vocab_plan.json: {e}")
        return {}

def verify_week(week_num, vocab_data):
    filepath = f"lessons/Week_{week_num}_Lesson_Plan.html"
    if not os.path.exists(filepath):
        print(f"Week {week_num}: HTML file not found.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    week_vocab = vocab_data.get(week_num)
    if not week_vocab:
        print(f"Week {week_num}: No vocab data in JSON.")
        return False

    # Check L1 Vocab Table
    # Usually the first table with class vocab-table
    tables = soup.find_all('table', class_='vocab-table')
    if len(tables) < 2:
        print(f"Week {week_num}: Found {len(tables)} vocab tables (expected at least 2).")
        return False

    l1_table = tables[0]
    l2_table = tables[1]

    # Extract words from HTML
    def extract_words(table):
        words = []
        rows = table.find_all('tr')
        for row in rows:
            tds = row.find_all('td')
            if not tds: continue
            # Skip header rows or idiom separators
            first_td_text = tds[0].get_text(strip=True)
            if 'Idioms' in first_td_text: continue

            # Word is in first column, usually inside <strong>
            first_col = tds[0]
            strong = first_col.find('strong')
            if strong:
                word = strong.text.strip()
                # Clean up if parens are inside strong (rare)
                if '(' in word:
                     word = word.split('(')[0].strip()
                words.append(word)
        return words

    html_l1_words = extract_words(l1_table)
    html_l2_words = extract_words(l2_table)

    # Extract expected words from JSON
    # JSON words are like "Diligent (Adj)", we need "Diligent"
    json_l1_words = [w.get('word', '').split('(')[0].strip() for w in week_vocab.get('l1_vocab', [])[:7]]
    json_l2_words = [w.get('word', '').split('(')[0].strip() for w in week_vocab.get('l2_vocab', [])[:7]]

    # Compare
    success = True

    # Check L1
    missing_l1 = [w for w in json_l1_words if w not in html_l1_words]
    if missing_l1:
        print(f"Week {week_num} L1 Mismatch: Missing {missing_l1}")
        success = False

    # Check L2
    missing_l2 = [w for w in json_l2_words if w not in html_l2_words]
    if missing_l2:
        print(f"Week {week_num} L2 Mismatch: Missing {missing_l2}")
        success = False

    if success:
        print(f"Week {week_num}: Vocab Verified ✅")
    return success

def main():
    print("Verifying Vocabulary Alignment...")
    vocab_data = load_vocab_plan()
    if not vocab_data: return

    # Check first 5 weeks or all
    for i in range(1, 6):
        verify_week(i, vocab_data)

if __name__ == "__main__":
    main()
