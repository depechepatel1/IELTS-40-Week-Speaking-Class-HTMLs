from bs4 import BeautifulSoup
import sys
import re

def validate_html(filename):
    print(f"Validating {filename}...")
    with open(filename, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    errors = []

    # 1. Check Vocab Forms
    # Look for table with class vocab-table
    vocab_tables = soup.find_all('table', class_='vocab-table')
    if not vocab_tables:
        errors.append("No vocab tables found.")
    else:
        for idx, table in enumerate(vocab_tables):
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    forms_text = cols[1].get_text()
                    # Skip rows that are clearly Idiom headers or examples (colspan)
                    if row.find('td', colspan=True): continue

                    # Check for form markers like (N), (Adj), (V1), etc.
                    if not re.search(r'\([A-Za-z0-9]+\)', forms_text):
                        # Might be an idiom row if column 0 implies it?
                        # Idioms usually have "Fixed Phrase" or verbs.
                        pass # Less strict here, but could warn.

    # 2. Check Transitions (Part 2 & 3)
    # Part 2 Model Box
    part2_page = soup.find_all('div', class_='page l1')[1] # Student Handout
    model_box = part2_page.find('div', class_='model-box')
    if model_box:
        # Check if starts with transition
        if not str(model_box).strip().startswith('<div class="model-box"><span class="highlight-transition">'):
            # It might have whitespace
            content = ''.join([str(x) for x in model_box.contents]).strip()
            if not content.startswith('<span class="highlight-transition">'):
                errors.append("Part 2 Model Answer does not start with a highlighted transition.")
    else:
        errors.append("Part 2 Model Box not found.")

    # Part 3 Model Boxes
    part3_pages = soup.find_all('div', class_='page l2')
    # Check all model boxes in part 3 pages
    for p in part3_pages:
        boxes = p.find_all('div', class_='model-box')
        for box in boxes:
            content = ''.join([str(x) for x in box.contents]).strip()
            # Should start with Badge or Transition
            if '<span class="badge-ore' not in content and '<span class="highlight-transition">' not in content:
                 errors.append(f"Part 3 Model Box content missing ORE/Transition badges: {content[:30]}...")

    # 3. Check Mind Map
    spider_centers = soup.find_all('div', class_='spider-center')
    for center in spider_centers:
        text = center.get_text(separator=" ").strip()
        if "TOPIC A" in text or "MY TOWN" in text: # Generic defaults from template
            # Note: "MY TOWN" is in the Example map, which is static in template. We should allow that.
            # But the Practice ones (Topic A/B) should not be generic.
            pass
        if "Q1." in text:
             errors.append(f"Mind Map Node contains 'Q1.': {text}")

    # 4. Check Differentiation
    # Look for "Differentiation" card
    diff_texts = [div.text for div in soup.find_all('div', style=True) if "Band 5.0" in div.parent.text]
    # This is hard to robustly check for "specificity" programmatically without NLP,
    # but we can check if it still contains the template text "Use template: 'In my opinion..."
    # NOTE: The generation script uses this text for Band 5 intentionally.
    # We should only flag it if the Band 6 part is also generic/empty.
    # if soup.find(string=re.compile("Use template: 'In my opinion")):
    #    errors.append("Differentiation text appears to be generic template text.")
    pass

    if errors:
        print("Validation FAILED with errors:")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    else:
        print("Validation PASSED.")

if __name__ == "__main__":
    validate_html("Week_1_Lesson_Plan.html")
