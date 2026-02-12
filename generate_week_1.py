3. validate_and_fix.py
import re
from bs4 import BeautifulSoup
import sys

def validate_and_fix(html_file):
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    fixed = False

    # 1. Check Mind Map Central Nodes (Generic "Topic A")
    # Finding divs with class spider-center
    spider_centers = soup.find_all("div", class_="spider-center")
    for center in spider_centers:
        text = center.get_text(separator=" ").strip()
        if "TOPIC A" in text.upper() or "TOPIC B" in text.upper():
            print(f"❌ Found Generic Mind Map Node: '{text}'")
            # In a real pipeline, we'd need the source data to fix this accurately.
            # Here we just flag it. The generation script should have handled it.
        else:
             print(f"✅ Mind Map Node: '{text}'")

    # 2. Check Part 3 Transitions (Reason Badge followed by Highlight)
    # Finding spans with badge-ore bg-r
    reasons = soup.find_all("span", class_="badge-ore bg-r")
    for i, r in enumerate(reasons):
        # SKIP BANNER: If the badge text is just "R", it's the legend banner.
        if r.get_text().strip() == "R":
            continue

        # The next sibling should be a highlight-transition span, or text then span?
        # Model: <span ...>Re</span> <span class="highlight-transition">...</span>
        # Or whitespace/text then span.
        
        next_tag = r.find_next_sibling("span")
        has_transition = False
        
        if next_tag and "highlight-transition" in next_tag.get("class", []):
            has_transition = True
        else:
            # Maybe inside the next text node? No, requirement is blue highlight.
            # Check if next_tag has style="color: blue" (if not converted)
            if next_tag and next_tag.has_attr("style") and "color: blue" in next_tag["style"]:
                has_transition = True
        
        if has_transition:
            print(f"✅ Part 3 Reason (index {i}): Transition found.")
        else:
            print(f"❌ Part 3 Reason (index {i}): Missing Blue Transition! -> Attempting Auto-Fix...")
            # Auto-Fix: Inject a generic transition if missing (this is a fallback)
            # In production, we'd want context-aware transitions.
            new_span = soup.new_tag("span", attrs={"class": "highlight-transition"})
            new_span.string = " This is because "
            r.insert_after(new_span)
            fixed = True

    # 3. Check Double Numbering "Q1: Q1."
    # Find h3 tags
    h3s = soup.find_all("h3")
    for h3 in h3s:
        text = h3.get_text()
        if re.search(r'Q\d+:\s*Q\d+\.', text):
            print(f"❌ Double Numbering found: '{text}' -> Fixing...")
            new_text = re.sub(r'(Q\d+):\s*Q\d+\.\s*', r'\1: ', text)
            h3.string = new_text
            fixed = True

    if fixed:
        print("💾 Saving fixed HTML...")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(str(soup))
    else:
        print("🎉 Validation Complete. No auto-fixes needed.")

if __name__ == "__main__":
    validate_and_fix("ielts_content_generation/Week_1_Generated.html")