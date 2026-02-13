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

def replace_inner_html(source, start_marker, new_content):
    start_pos = source.find(start_marker)
    if start_pos == -1:
        print(f"WARNING: Could not find start marker '{start_marker}'")
        return source

    tag_end = source.find('>', start_pos) + 1
    depth = 1
    current_pos = tag_end

    while depth > 0 and current_pos < len(source):
        next_open = source.find('<div', current_pos)
        next_close = source.find('</div>', current_pos)

        if next_close == -1:
            break

        if next_open != -1 and next_open < next_close:
            depth += 1
            current_pos = next_open + 4
        else:
            depth -= 1
            current_pos = next_close + 6

    if depth == 0:
        return source[:tag_end] + new_content + source[next_close:]
    else:
        print(f"WARNING: Could not find matching closing div for '{start_marker}'")
        return source

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

        display_text = (text[:18] + '..') if len(text) > 22 else text

        # INLINE FORMATTING (No <br>)
        legs_html += f"""
        <div class="spider-leg">
            <strong>{label}:</strong> <span style="color:#555; font-size:0.9em;">{display_text}</span>
        </div>
        """
    return legs_html

def format_model_answer(text, use_short_badges=False):
    label_map = {
        "Opinion": "Op" if use_short_badges else "Opinion",
        "Reason": "Re" if use_short_badges else "Reason",
        "Example": "Ex" if use_short_badges else "Example"
    }

    def badge_replacer(match):
        label_content = match.group(2)
        clean_label = re.sub(r'<[^>]+>', '', label_content).strip()

        if clean_label in label_map:
            new_label = label_map[clean_label]
            cls = "bg-o" if "Op" in clean_label else "bg-r" if "Re" in clean_label else "bg-e"
            return f'<span class="badge-ore {cls}">{new_label}</span>'
        return match.group(0)

    text = re.sub(r'(<span style="[^"]+">)(.*?)(</span>)', badge_replacer, text)
    # Ensure Blue Transitions
    text = text.replace('style="color: blue;"', 'class="highlight-transition"')

    # 3-Clause
    text = re.sub(r'<span style="background-color: yellow;">(.*?)</span>', r'<span class="highlight-3clause">\1</span>', text)

    # Clean
    text = text.replace('<b>', '<strong>').replace('</b>', '</strong>')
    text = text.replace('<strong><span', '<span').replace('</span></strong>', '</span>')

    # CHECK FOR MISSING TRANSITION (If no blue span found)
    if 'highlight-transition' not in text:
        # Inject default transition at start if missing
        text = f'<span class="highlight-transition">To begin with,</span> {text}'

    return text

# --- Step 0: Inject Compact CSS & Fixes ---
print("Injecting Compact CSS & Layout Fixes...")
compact_css = """
    /* Aggressive Layout Fixes */
    .page { overflow: hidden; height: 296mm; padding: 8mm !important; }

    /* Compact Teacher Plan */
    .compact-plan .card { padding: 5px 8px !important; margin-bottom: 6px !important; }
    .compact-plan h2 { margin: 2px 0 4px 0 !important; font-size: 0.9em !important; }
    .compact-plan .lp-table td { padding: 2px 4px !important; font-size: 0.7em !important; }
    .compact-plan .lp-table th { padding: 3px !important; }
    .compact-plan li { margin-bottom: 0 !important; line-height: 1.2; }

    /* Spider Diagram Fixes */
    .spider-leg { padding: 2px !important; line-height: 1.1; display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 5px; }
    .spider-leg strong { white-space: nowrap; font-size: 0.7em; }
    .spider-leg span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* Homework Fixes */
    .grammar-sent { padding: 3px 0 !important; border-bottom: 1px dashed #eee; font-size: 0.85em !important; }
    .page.hw .card { padding: 8px !important; }
    .diff-box { margin-top: 4px !important; padding: 4px !important; font-size: 0.75em !important; }
    .lines { line-height: 20px; background-size: 100% 20px; }
"""
html = html.replace('</style>', f'{compact_css}\n</style>')

# Apply class to ALL pages to ensure safety, or specific ones?
# User wants "Lesson 1 procedure", "Lesson 2 procedure", "Homework".
# Let's apply .compact-plan to L1 and L2 Teacher Plans.
html = html.replace('<div class="page l1">', '<div class="page l1 compact-plan">', 1)
html = html.replace('<div class="page l2">', '<div class="page l2 compact-plan">', 1)
# Apply to Homework page too for padding fixes
html = html.replace('<div class="page hw">', '<div class="page hw compact-plan">', 1)


# --- Step 1: Teacher Plan (Page 3 - L1) ---
print("Processing Teacher Plan L1...")

html = replace_text(html, "Week 1 • Lesson 1 • Friendship", "Week 1 • Lesson 1 • Family")
html = replace_text(html, "Search: IELTS Friendship", "Search: IELTS Family Speaking")

new_objectives = """
<li><strong>Speaking:</strong> Describe a family member using adjectives of personality.</li>
<li><strong>Vocab:</strong> Use 7 target words (e.g., <em>Diligent</em>) in context.</li>
<li><strong>Grammar:</strong> Use relative clauses ("who is...") to describe people.</li>
"""
html = re.sub(r'(<h2>🎯 Learning Objectives</h2>\s*<ul.*?>)(.*?)(</ul>)', r'\1' + new_objectives + r'\3', html, flags=re.DOTALL, count=1)

diff_content = """
<div style="flex:1; background:#e8f8f5; padding:4px; border-radius:4px;">
    <strong>📉 Band 5.0</strong>: "I want to talk about my..."
</div>
<div style="flex:1; background:#fef9e7; padding:4px; border-radius:4px;">
    <strong>📈 Band 6.0+</strong>: "The relative I hold in high regard is..."
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
<div style="font-size:0.85em; color:#444;">
    Say: <strong>Who</strong>, <strong>What</strong> they are like, <strong>How</strong> they help, <strong>Why</strong> proud.
</div>
"""
# Use replace_inner_html for Card content to be safe
html = replace_inner_html(html, '<div class="card" style="background:#fffde7; border-left:5px solid #fbc02d;">', cue_card_html)

model_text = format_model_answer(q1_data['model_answer'])
html = re.sub(r'(<h2>🏆 Band 6.5 Model Answer</h2>\s*<div class="model-box">)(.*?)(</div>)', r'\1' + model_text + r'\3', html, flags=re.DOTALL)

l1_vocab_rows = generate_vocab_rows(vocab['l1_vocab'])
l1_vocab_rows += f'<tr><td colspan="3" style="background:#eee; font-weight:bold; color:#555;">🐎 Idioms</td></tr>\n'
l1_vocab_rows += generate_vocab_rows(vocab['l1_idioms'], is_idiom=True)

html = re.sub(r'(<h2>📚 Target Vocabulary & Idioms</h2>\s*<table class="vocab-table">.*?<tbody>)(.*?)(</tbody>)', r'\1' + l1_vocab_rows + r'\3', html, flags=re.DOTALL)


# --- Step 3: Student Practice ---
print("Processing Lesson 1 Practice...")

html = replace_text(html, '<div class="spider-center">MY<br>FRIEND</div>', '<div class="spider-center">MY<br>FAMILY</div>')

legs_html = generate_mind_map_legs(q1_data['bullet_points'])
# First spider map
html = replace_inner_html(html, '<div class="spider-legs">', legs_html)

# Topic A (Q2)
q2_data = curriculum['part2'][1]
html = replace_text(html, "Topic A: A Helpful Neighbor", f"Topic A: {clean_question_text(q2_data['question'])}")
html = replace_text(html, '<div class="spider-center">Neighbor</div>', '<div class="spider-center">Achieve</div>')
# Fix Topic A Legs
legs_a = generate_mind_map_legs(q2_data['bullet_points'])
# We need to target the *second* spider-legs container.
# Strategy: Split, replace, join?
# Or find position of "Topic A" and replace next spider-legs
pos_a = html.find(f"Topic A: {clean_question_text(q2_data['question'])}")
html = replace_inner_html(html[pos_a:], '<div class="spider-legs">', legs_a)
# Wait, replace_inner_html returns the modified snippet. We need to stitch it back.
# This logic is complex.
# Alternative: Regex with count=1 after specific marker.
parts = html.split(f"Topic A: {clean_question_text(q2_data['question'])}")
if len(parts) > 1:
    # Modify the second part (which contains the spider legs for Topic A)
    parts[1] = replace_inner_html(parts[1], '<div class="spider-legs">', legs_a)
    html = f"Topic A: {clean_question_text(q2_data['question'])}".join(parts)

# Topic B (Q3)
q3_data = curriculum['part2'][2]
html = replace_text(html, "Topic B: An Admired Teacher", f"Topic B: {clean_question_text(q3_data['question'])}")
html = replace_text(html, '<div class="spider-center">Teacher</div>', '<div class="spider-center">Admire</div>')
# Fix Topic B Legs
legs_b = generate_mind_map_legs(q3_data['bullet_points'])
parts = html.split(f"Topic B: {clean_question_text(q3_data['question'])}")
if len(parts) > 1:
    parts[1] = replace_inner_html(parts[1], '<div class="spider-legs">', legs_b)
    html = f"Topic B: {clean_question_text(q3_data['question'])}".join(parts)


# --- Step 4: Teacher Lesson Plan L2 ---
print("Processing Lesson 2 Teacher Plan...")
l2_title_old = "Week 1 • Lesson 2 • Abstract Topics"
l2_title_new = "Week 1 • Lesson 2 • Family Society"
html = replace_text(html, l2_title_old, l2_title_new)

l2_objectives = """
<li><strong>Logic:</strong> O.R.E. Family Roles.</li>
<li><strong>Vocab:</strong> Abstract nouns.</li>
<li><strong>Speaking:</strong> Family & Society.</li>
"""

l2_header_pos = html.find(l2_title_new)
if l2_header_pos != -1:
    # Replace UL manually
    start_ul = html.find("<ul", l2_header_pos)
    end_ul = html.find("</ul>", start_ul) + 5
    ul_tag_end = html.find(">", start_ul) + 1
    html = html[:ul_tag_end] + l2_objectives + html[end_ul-5:]


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

# Q1 (Long Form ORE)
q1_p3 = curriculum['part3'][0]
html = replace_text(html, "Q1: Is it important to have many friends?", f"{q1_p3['question']}")
model_q1 = format_model_answer(q1_p3['model_answer'], use_short_badges=False)

p5_q1_pos = html.find('id="p5-q1"')
html = replace_inner_html(html[p5_q1_pos:], '<div class="model-box">', model_q1)
# Stitching needed if replace_inner_html truncates? No, it returns modified string.
# But here we are passing substring.
# Let's do a robust replace in full string.
full_p5_chunk = replace_inner_html(html[p5_q1_pos:], '<div class="model-box">', model_q1)
html = html[:p5_q1_pos] + full_p5_chunk


# --- Step 6: Deep Dive ---
print("Processing Lesson 2 Deep Dive...")

q2_p3 = curriculum['part3'][1]
html = replace_text(html, "Q2: What causes arguments between friends?", f"{q2_p3['question']}")
model_q2 = format_model_answer(q2_p3['model_answer'], use_short_badges=False)

p6_q2_pos = html.find('id="p6-q2"')
# Replace inner of model box
# Find the model box div INSIDE p6-q2
mb_start = html.find('<div class="model-box">', p6_q2_pos)
html = replace_inner_html(html, html[mb_start:mb_start+30], model_q2) # Pass the unique tag? No, replace_inner_html takes marker.
# Issue: markers are not unique globally.
# Strategy: targeted replace.
full_p6_q2 = replace_inner_html(html[p6_q2_pos:], '<div class="model-box">', model_q2)
html = html[:p6_q2_pos] + full_p6_q2

q3_p3 = curriculum['part3'][2]
html = replace_text(html, "Q3: Do you think friends are more important than family?", f"{q3_p3['question']}")
model_q3 = format_model_answer(q3_p3['model_answer'], use_short_badges=True)

p6_q3_pos = html.find('id="p6-q3"')
# Q3 has style style="margin-bottom:10px;" on model box
full_p6_q3 = replace_inner_html(html[p6_q3_pos:], '<div class="model-box"', model_q3)
html = html[:p6_q3_pos] + full_p6_q3


# --- Step 7: Rapid Fire ---
print("Processing Lesson 2 Rapid Fire...")

q4_p3 = curriculum['part3'][3]
html = replace_text(html, "Q4: Does social media help us make friends?", f"{q4_p3['question']}")
model_q4 = format_model_answer(q4_p3['model_answer'], use_short_badges=True)
# Find Q4 Header
q4_pos = html.find(f"{q4_p3['question']}")
full_q4 = replace_inner_html(html[q4_pos:], '<div class="model-box">', model_q4)
html = html[:q4_pos] + full_q4

q5_p3 = curriculum['part3'][4]
html = replace_text(html, "Q5: Is it possible to be real friends with colleagues?", f"{q5_p3['question']}")
model_q5 = format_model_answer(q5_p3['model_answer'], use_short_badges=True)
q5_pos = html.find(f"{q5_p3['question']}")
full_q5 = replace_inner_html(html[q5_pos:], '<div class="model-box">', model_q5)
html = html[:q5_pos] + full_q5

q6_p3 = curriculum['part3'][5]
html = replace_text(html, "Q6: Why is it harder to make friends as an adult?", f"{q6_p3['question']}")
model_q6 = format_model_answer(q6_p3['model_answer'], use_short_badges=True)
q6_pos = html.find(f"{q6_p3['question']}")
full_q6 = replace_inner_html(html[q6_pos:], '<div class="model-box">', model_q6)
html = html[:q6_pos] + full_q6


# --- Step 8: Homework ---
print("Processing Homework...")

hw_vocab = homework['vocab_review']
vocab_rows = ""
for i, item in enumerate(hw_vocab, 1):
    vocab_rows += f'<tr><td>{i}. {item["word"]}</td><td style="border-bottom:1px solid #eee;"></td><td>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {item["option"]}. {item["synonym"]}</td></tr>\n'

hw_pos = html.find('class="page hw')
table_start = html.find('<tbody>', hw_pos)
table_end = html.find('</tbody>', table_start) + 8
html = html[:table_start] + "<tbody>" + vocab_rows + "</tbody>" + html[table_end:]

hw_grammar = homework['grammar_clinic']
grammar_divs = ""
for i, item in enumerate(hw_grammar, 1):
    grammar_divs += f'<div class="grammar-sent">{i}. {item["error"]}</div>\n'

# Find the container for grammar sentences
grammar_header = html.find('2. Error Correction', hw_pos)
html = replace_inner_html(html[grammar_header:], '<div style="display:flex; flex-direction:column; gap:15px; margin-top:10px;">', grammar_divs)
html = html[:grammar_header] + html # Stitch back? No, replace_inner_html on substring returns truncated string.
# CORRECT STITCHING:
# full_grammar_section = replace_inner_html(html[grammar_header:], ...)
# html = html[:grammar_header] + full_grammar_section
full_grammar = replace_inner_html(html[grammar_header:], '<div style="display:flex; flex-direction:column; gap:15px; margin-top:10px;">', grammar_divs)
html = html[:grammar_header] + full_grammar

hw_task = homework['writing_task']
html = replace_text(html, "Describe a Family Member (17 mins)", "Writing Task (17 mins)")
html = re.sub(r'<h3>3. Writing Task:.*?</h3>', f'<h3>3. Writing Task: {hw_task}</h3>', html)

key = homework['answer_key']
# Robust key replacement
key_pos = html.find('Key: 1. Reliable')
if key_pos != -1:
    key_end_div = html.find('</div>', key_pos)
    html = html[:key_pos] + key + html[key_end_div:]

# --- Final Cleanup ---
html = re.sub(r'Q(\d+)[:\.]\s*Q\d+[\.:]\s*', r'Q\1: ', html)

with open('Week_1_Family.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("✅ Week 1 HTML Generated: Week_1_Family.html")
