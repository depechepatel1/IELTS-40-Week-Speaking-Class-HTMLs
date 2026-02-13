from bs4 import BeautifulSoup
import re

def audit_html(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    issues = []

    # 1. Check for "Friendship" leftovers (Template pollution)
    # The topic should be Family.
    if "IELTS Friendship" in html:
        issues.append("❌ 'IELTS Friendship' found (Video Search Term?)")

    # 2. Check for "Topic A" or "Topic B" generic titles
    # We replaced "Topic A: A Helpful Neighbor" with "Topic A: Describe a family member..."
    # So "Topic A:" is fine, but "Topic A: A Helpful Neighbor" is not.
    if "A Helpful Neighbor" in html:
        issues.append("❌ Generic Topic A Title found")
    if "An Admired Teacher" in html:
        issues.append("❌ Generic Topic B Title found")

    # 3. Check for Spider Diagram Artifacts ("Traits", "Evidence", "Feel")
    # These were the stacked legs in the template.
    # If our cleaner worked, these should be gone or replaced.
    # Actually, we replaced the *content* of .spider-legs.
    # The new content has "WHO:", "WHEN:", "WHAT:", "WHY:" based on Q1 bullets.
    # Let's check for Q1 legs.
    legs = soup.find_all("div", class_="spider-leg")
    leg_texts = [leg.get_text() for leg in legs]

    if not any("WHO:" in t for t in leg_texts):
        issues.append("❌ Q1 Spider Legs missing 'WHO:' label")

    # Check if artifacts exist (The template had 4 legs: Who, Traits, Evidence, Feeling)
    # If we see "Traits" in a leg *without* specific content, it's bad.
    # But Q2/Q3 might have different labels.

    # 4. Check O.R.E. Badges
    badges = soup.find_all("span", class_="badge-ore")
    if len(badges) == 0:
        issues.append("❌ No O.R.E. badges found")

    # 5. Check Blue Transitions
    blues = soup.find_all("span", class_="highlight-transition")
    if len(blues) == 0:
        issues.append("❌ No Blue Transitions found")

    if not issues:
        print("✅ Audit Passed: Content appears correct.")
    else:
        print("Audit Issues:")
        for issue in issues:
            print(issue)

if __name__ == "__main__":
    audit_html("Week_1_Family.html")
