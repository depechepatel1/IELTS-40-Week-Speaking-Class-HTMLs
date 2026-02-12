import json
import re
import sys

# Load Data
try:
    with open('week_1_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    print("CRITICAL: week_1_data.json not found. Run extract_week_1_data.py first.")
    sys.exit(1)

curriculum = data.get('curriculum')
vocab = data.get('vocab')
homework = data.get('homework')

if not curriculum or not vocab or not homework:
    print("CRITICAL: Missing data in week_1_data.json")
    sys.exit(1)

# Load Template
try:
    with open('Week_1 Jules.html', 'r', encoding='utf-8') as f:
        html = f.read()
except FileNotFoundError:
    print("CRITICAL: Week_1 Jules.html template not found.")
    sys.exit(1)

# --- Helpers ---
def replace_text(source, old, new):
    if old not in source:
        print(f"WARNING: Could not find '{old}' to replace.")
    return source.replace(old, new)

def generate_vocab_rows(vocab_list, is_idiom=False):
    rows = ""
    for item in vocab_list:
        if is_idiom:
            term = item.get('idiom', '')
            forms = item.get('usage', '')
            meaning = item.get('meaning', '')
            cn_meaning = f"<span class='vocab-cn'>{meaning}</span>"
            example = item.get('example_sentence', item.get('example', ''))

            rows += f"<tr><td><strong>{term}</strong></td><td>{forms}</td><td>{cn_meaning}</td></tr>\n"
            if example:
                rows += f"<tr class='vocab-example-row'><td colspan='3'>\"{example}\"</td></tr>\n"
        else:
            word_full = item.get('word', '')
            forms = item.get('Word Forms', '')
            meaning = item.get('meaning', '')
            recycled = item.get('recycled', False)

            word_cell = f"<strong>{word_full.split('(')[0].strip()}</strong>"
            if '(' in word_full:
                word_cell += f" ({word_full.split('(')[1]}"

            if recycled:
                word_cell += " <span class='recycled-tag'>Recycled</span>"

            cn_meaning = f"<span class='vocab-cn'>{meaning}</span>"
            rows += f"<tr><td>{word_cell}</td><td>{forms}</td><td>{cn_meaning}</td></tr>\n"
    return rows

def clean_question_text(text):
    return re.sub(r'^Q\d+[\.:]\s*', '', text)

def generate_mind_map_legs(bullet_points):
    legs_html = ""
    for bp in bullet_points:
        if ":" in bp:
            parts = bp.split(":", 1)
            label = parts[0].strip().upper()
            text = parts[1].strip()
        else:
            label = "POINT"
            text = bp

        display_text = (text[:15] + '..') if len(text) > 18 else text

        legs_html += f"""
        <div class="spider-leg">
            <strong>{label}:</strong><br>
            <span style="color:#777;">{display_text}</span>
        </div>
        """
    return legs_html

# --- Step 1: Teacher Plan (Page 3) ---
print("Processing Teacher Plan...")

html = replace_text(html, "Week 1 • Lesson 1 • Friendship", "Week 1 • Lesson 1 • Family")
html = replace_text(html, "Search: IELTS Friendship", "Search: IELTS Family Speaking")

new_objectives = """
<li><strong>Speaking:</strong> Describe a family member using adjectives of personality and emotion.</li>
<li><strong>Vocab:</strong> Use 7 target words (e.g., <em>Diligent, Selfless</em>) in context.</li>
<li><strong>Grammar:</strong> Use relative clauses ("who is...", "which is...") to describe people.</li>
"""
html = re.sub(r'(<h2>🎯 Learning Objectives</h2>\s*<ul.*?>)(.*?)(</ul>)', r'\1' + new_objectives + r'\3', html, flags=re.DOTALL, count=1)

diff_content = """
<div style="flex:1; background:#e8f8f5; padding:5px; border-radius:6px;">
    <strong>📉 Band 5.0 (Support)</strong><br>
    • Starters: "I want to talk about my..."<br>
    • Focus: "He is [Adjective] because..."
</div>
<div style="flex:1; background:#fef9e7; padding:5px; border-radius:6px;">
    <strong>📈 Band 6.0+ (Stretch)</strong><br>
    • Starters: "The relative I hold in high regard is..."<br>
    • Focus: "Not only is he..., but also..."
</div>
"""
html = re.sub(r'(<h2>🧩 Differentiation</h2>\s*<div style="display:flex; gap:10px; font-size:0.8em;">)(.*?)(</div>\s*</div>)', r'\1' + diff_content + r'\3', html, flags=re.DOTALL)


# --- Step 2: Student Lesson 1 (Part 2 Input) ---
print("Processing Lesson 1 Input...")

html = replace_text(html, "Describe a close friend", "Describe a family member")
html = replace_text(html, "IELTS%20Friendship", "IELTS%20Family%20Member")

q1_data = curriculum['part2'][0]
cue_card_html = f"""
<h3>📌 CUE CARD: {clean_question_text(q1_data['question'])}</h3>
<div style="font-size:0.9em; color:#444;">
    You should say: <strong>Who</strong> this person is, <strong>What</strong> they are like, <strong>How</strong> they help you, and <strong>Why</strong> you are proud of them.
</div>
"""
html = re.sub(r'(<div class="card" style="background:#fffde7; border-left:5px solid #fbc02d;">)(.*?)(</div>)', r'\1' + cue_card_html + r'\3', html, flags=re.DOTALL)

model_text = q1_data['model_answer']
model_text = model_text.replace('style="color: blue;"', 'class="highlight-transition"')
model_text = model_text.replace('<b>', '<strong>').replace('</b>', '</strong>')
model_text = re.sub(r'<span style="background-color: yellow;">(.*?)</span>', r'<span class="highlight-3clause">\1</span>', model_text)

html = re.sub(r'(<h2>🏆 Band 6.5 Model Answer</h2>\s*<div class="model-box">)(.*?)(</div>)', r'\1' + model_text + r'\3', html, flags=re.DOTALL)

l1_vocab_rows = generate_vocab_rows(vocab['l1_vocab'])
l1_vocab_rows += f'<tr><td colspan="3" style="background:#eee; font-weight:bold; color:#555;">🐎 Idioms</td></tr>\n'
l1_vocab_rows += generate_vocab_rows(vocab['l1_idioms'], is_idiom=True)

html = re.sub(r'(<h2>📚 Target Vocabulary & Idioms</h2>\s*<table class="vocab-table">.*?<tbody>)(.*?)(</tbody>)', r'\1' + l1_vocab_rows + r'\3', html, flags=re.DOTALL)


# --- Step 3: Student Practice ---
print("Processing Lesson 1 Practice...")

html = replace_text(html, '<div class="spider-center">MY<br>FRIEND</div>', '<div class="spider-center">MY<br>FAMILY</div>')

legs_html = generate_mind_map_legs(q1_data['bullet_points'])
html = re.sub(r'(<div class="spider-legs">)(.*?)(</div>)', r'\1' + legs_html + r'\3', html, count=1, flags=re.DOTALL)

q2_data = curriculum['part2'][1]
html = replace_text(html, "Topic A: A Helpful Neighbor", f"Topic A: {clean_question_text(q2_data['question'])}")
html = replace_text(html, '<div class="spider-center">Neighbor</div>', '<div class="spider-center">Achieve</div>')

q3_data = curriculum['part2'][2]
html = replace_text(html, "Topic B: An Admired Teacher", f"Topic B: {clean_question_text(q3_data['question'])}")
html = replace_text(html, '<div class="spider-center">Teacher</div>', '<div class="spider-center">Admire</div>')


# --- Step 4: Teacher Lesson Plan L2 ---
print("Processing Lesson 2 Teacher Plan...")
l2_title_old = "Week 1 • Lesson 2 • Abstract Topics"
l2_title_new = "Week 1 • Lesson 2 • Family Society"
html = replace_text(html, l2_title_old, l2_title_new)

l2_objectives = """
<li><strong>Logic:</strong> Use O.R.E. to discuss Family Roles.</li>
<li><strong>Vocab:</strong> Use abstract nouns (e.g., <em>Harmony, Instill</em>).</li>
<li><strong>Speaking:</strong> Discuss Family Pride & Society.</li>
"""

# ROBUST REPLACEMENT LOGIC
l2_header_pos = html.find(l2_title_new)
if l2_header_pos == -1:
    print("CRITICAL ERROR: L2 Header not found! Duplication logic aborted.")
    sys.exit(1)

# Fix: find "<ul" not "<ul>" because of potential attributes
start_ul = html.find("<ul", l2_header_pos)
end_ul = html.find("</ul>", start_ul) + 5

if start_ul == -1 or end_ul == 4: # -1 + 5 = 4
    print("CRITICAL ERROR: L2 UL block not found.")
    sys.exit(1)

# We need to find the '>' of the opening <ul...> tag to insert content properly
ul_tag_end = html.find(">", start_ul) + 1
# Replace content BETWEEN <ul> and </ul>
html = html[:ul_tag_end] + l2_objectives + html[end_ul-5:] # end_ul-5 is start of </ul>


# --- Step 5: Student Lesson 2 Input ---
print("Processing Lesson 2 Input...")
html = replace_text(html, "Part 3: Abstract Discussion", "Part 3: Family & Society")

l2_vocab_rows = generate_vocab_rows(vocab['l2_vocab'])
l2_vocab_rows += f'<tr><td colspan="3" style="background:#eee; font-weight:bold; color:#555;">🐎 Idioms</td></tr>\n'
l2_vocab_rows += generate_vocab_rows(vocab['l2_idioms'], is_idiom=True)

html = replace_text(html, "Abstract Vocabulary (7 Words + 3 Idioms)", "Part 3 Vocabulary")
vocab_header_pos = html.find("Part 3 Vocabulary")
table_start = html.find("<tbody>", vocab_header_pos)
table_end = html.find("</tbody>", table_start) + 8
html = html[:table_start] + "<tbody>" + l2_vocab_rows + "</tbody>" + html[table_end:]

q1_p3 = curriculum['part3'][0]
html = replace_text(html, "Q1: Is it important to have many friends?", f"{q1_p3['question']}")
model_q1 = q1_p3['model_answer']
model_q1 = model_q1.replace('style="color: blue;"', 'class="highlight-transition"')
model_q1 = re.sub(r'<span style="background-color: yellow;">(.*?)</span>', r'<span class="highlight-3clause">\1</span>', model_q1)

p5_q1_pos = html.find('id="p5-q1"')
box_start = html.find('<div class="model-box">', p5_q1_pos)
box_end = html.find('</div>', box_start) + 6
html = html[:box_start] + f'<div class="model-box">{model_q1}</div>' + html[box_end:]


# --- Step 6: Deep Dive ---
print("Processing Lesson 2 Deep Dive...")

q2_p3 = curriculum['part3'][1]
html = replace_text(html, "Q2: What causes arguments between friends?", f"{q2_p3['question']}")
model_q2 = q2_p3['model_answer'].replace('style="color: blue;"', 'class="highlight-transition"').replace('style="background-color: yellow;"', 'class="highlight-3clause"')

p6_q2_pos = html.find('id="p6-q2"')
box_start = html.find('<div class="model-box">', p6_q2_pos)
box_end = html.find('</div>', box_start) + 6
html = html[:box_start] + f'<div class="model-box">{model_q2}</div>' + html[box_end:]

q3_p3 = curriculum['part3'][2]
html = replace_text(html, "Q3: Do you think friends are more important than family?", f"{q3_p3['question']}")
model_q3 = q3_p3['model_answer'].replace('style="color: blue;"', 'class="highlight-transition"').replace('style="background-color: yellow;"', 'class="highlight-3clause"')

p6_q3_pos = html.find('id="p6-q3"')
box_start = html.find('<div class="model-box"', p6_q3_pos)
box_end = html.find('</div>', box_start) + 6
html = re.sub(r'(<div id="p6-q3".*?<div class="model-box".*?>)(.*?)(</div>)', r'\1' + model_q3 + r'\3', html, flags=re.DOTALL, count=1)


# --- Step 7: Rapid Fire ---
print("Processing Lesson 2 Rapid Fire...")

q4_p3 = curriculum['part3'][3]
html = replace_text(html, "Q4: Does social media help us make friends?", f"{q4_p3['question']}")
model_q4 = q4_p3['model_answer'].replace('style="color: blue;"', 'class="highlight-transition"')
html = re.sub(r'(<h3>Q4.*?</h3>\s*<div class="model-box">)(.*?)(</div>)', r'\1' + model_q4 + r'\3', html, flags=re.DOTALL, count=1)

q5_p3 = curriculum['part3'][4]
html = replace_text(html, "Q5: Is it possible to be real friends with colleagues?", f"{q5_p3['question']}")
model_q5 = q5_p3['model_answer'].replace('style="color: blue;"', 'class="highlight-transition"')
html = re.sub(r'(<h3>Q5.*?</h3>\s*<div class="model-box">)(.*?)(</div>)', r'\1' + model_q5 + r'\3', html, flags=re.DOTALL, count=1)

q6_p3 = curriculum['part3'][5]
html = replace_text(html, "Q6: Why is it harder to make friends as an adult?", f"{q6_p3['question']}")
model_q6 = q6_p3['model_answer'].replace('style="color: blue;"', 'class="highlight-transition"')
html = re.sub(r'(<h3>Q6.*?</h3>\s*<div class="model-box">)(.*?)(</div>)', r'\1' + model_q6 + r'\3', html, flags=re.DOTALL, count=1)


# --- Step 8: Homework ---
print("Processing Homework...")

hw_vocab = homework['vocab_review']
vocab_rows = ""
for i, item in enumerate(hw_vocab, 1):
    vocab_rows += f'<tr><td>{i}. {item["word"]}</td><td style="border-bottom:1px solid #eee;"></td><td>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {item["option"]}. {item["synonym"]}</td></tr>\n'

hw_pos = html.find('class="page hw"')
table_start = html.find('<tbody>', hw_pos)
table_end = html.find('</tbody>', table_start) + 8
html = html[:table_start] + "<tbody>" + vocab_rows + "</tbody>" + html[table_end:]

hw_grammar = homework['grammar_clinic']
grammar_divs = ""
for i, item in enumerate(hw_grammar, 1):
    grammar_divs += f'<div class="grammar-sent">{i}. {item["error"]}</div>\n'

html = re.sub(r'(<h3>2. Error Correction.*?<div style="display:flex; flex-direction:column; gap:15px; margin-top:10px;">)(.*?)(</div>)', r'\1' + grammar_divs + r'\3', html, flags=re.DOTALL)

hw_task = homework['writing_task']
html = replace_text(html, "Describe a Family Member (17 mins)", "Writing Task (17 mins)")
html = re.sub(r'<h3>3. Writing Task:.*?</h3>', f'<h3>3. Writing Task: {hw_task}</h3>', html)

key = homework['answer_key']
html = re.sub(r'<div style="text-align:center; transform:rotate\(180deg\).*?>.*?</div>', f'<div style="text-align:center; transform:rotate(180deg); color:#555; font-weight:bold; font-size:0.8em; margin-top:auto;">{key}</div>', html, flags=re.DOTALL)

# --- Final Cleanup ---
html = re.sub(r'Q(\d+)[:\.]\s*Q\d+[\.:]\s*', r'Q\1: ', html)

with open('Week_1_Family.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("✅ Week 1 HTML Generated: Week_1_Family.html")
