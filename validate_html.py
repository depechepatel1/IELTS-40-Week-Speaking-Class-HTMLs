import re
from bs4 import BeautifulSoup

def validate(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    issues = []

    # 1. Check for "Friendship" leftovers
    # We expect "Friendship" might appear in "Friendship & Social Interaction" theme if that wasn't updated?
    # The Template had "Friendship & Social Interaction" in cover page.
    # In my script I didn't explicitly replace the Cover Page Theme text?
    # Let's check cover page.
    cover_text = soup.find(class_="cover-theme-text")
    if cover_text and "Friendship" in cover_text.get_text():
        issues.append("⚠️ Cover Page Theme might still say 'Friendship'")

    # Check general body
    if "IELTS Friendship" in html:
        issues.append("❌ Found 'IELTS Friendship' (Video Search Term?)")

    # 2. Check Double Numbering
    if re.search(r'Q\d+[:\.]\s*Q\d+[\.:]', html):
        issues.append("❌ Double Numbering found (e.g. Q1: Q1.)")

    # 3. Check Part 3 Transitions
    # Find all model-box divs
    models = soup.find_all(class_="model-box")
    for i, model in enumerate(models):
        if not model.find(class_="highlight-transition"):
            issues.append(f"⚠️ Part 3 Model {i+1} missing 'highlight-transition' class")

    # 4. Check Mind Map Legs (Main)
    # The first spider-legs should have specific content like "Mother" or "Grandfather"
    legs_container = soup.find(class_="spider-legs")
    if legs_container:
        legs_text = legs_container.get_text()
        if "Traits" in legs_text and "Help" in legs_text and "Feel" in legs_text:
             # This suggests it wasn't replaced with specific bullets?
             # Wait, my script replaced the *first* container.
             # Let's check if the text inside contains specific keywords from Q1
             if "Mother" not in legs_text and "Father" not in legs_text and "Grandfather" not in legs_text:
                 # Note: The Q1 bullets had "Mother / Grandfather".
                 issues.append("⚠️ Main Mind Map might not be updated (Generic labels found?)")

    if not issues:
        print("✅ Validation Passed: No critical issues found.")
    else:
        print("Validation Issues:")
        for issue in issues:
            print(issue)

if __name__ == "__main__":
    validate("Week_1_Family.html")
