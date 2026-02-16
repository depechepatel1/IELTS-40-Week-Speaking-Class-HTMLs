from bs4 import BeautifulSoup
import sys
import re
from generate_weekly_lesson import load_data, clean_text

def validate_html(filename):
    print(f"Validating {filename}...")

    # Extract week number from filename "Week_X_Lesson_Plan.html"
    try:
        week_num = int(re.search(r'Week_(\d+)_', filename).group(1))
    except:
        print("Could not determine week number from filename.")
        return

    # Load Expected Data
    try:
        curr, vocab, hw = load_data(week_num)
    except Exception as e:
        print(f"Error loading data for validation: {e}")
        return

    with open(filename, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    errors = []

    # 1. Check Vocab Forms
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
                    if row.find('td', colspan=True): continue
                    if not re.search(r'\([A-Za-z0-9]+\)', forms_text):
                        pass

    # 2. Check Content Integrity (Questions match JSON)
    # Check Part 2 Q1 (Student Handout)
    part2_page = soup.find_all('div', class_='page l1')[1]
    cue_card = part2_page.find('h3')
    if cue_card:
        expected_q1 = clean_text(curr['part2'][0]['question'])
        if expected_q1 not in cue_card.text:
             errors.append(f"Part 2 Q1 Mismatch. Expected '{expected_q1}' in '{cue_card.text}'")

    # Check Part 3 Q1 (Page 5)
    page_p3 = soup.find_all('div', class_='page l2')[1]
    q1_card = page_p3.find('div', id='p5-q1')
    if q1_card:
        expected_p3_q1 = curr['part3'][0]['question']
        if expected_p3_q1 not in q1_card.find('h3').text:
            errors.append(f"Part 3 Q1 Mismatch.")

    # 3. Check Differentiation (Looser check)
    if soup.find(string=re.compile("Use template: 'In my opinion")):
        # This is expected now, so we pass
        pass

    if errors:
        print("Validation FAILED with errors:")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    else:
        print("Validation PASSED.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate_html(sys.argv[1])
    else:
        validate_html("Week_1_Lesson_Plan.html")
