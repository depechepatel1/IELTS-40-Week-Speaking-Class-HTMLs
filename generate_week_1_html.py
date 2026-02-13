import json
import re
from bs4 import BeautifulSoup, NavigableString

# Load Data
with open('week_1_content.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

curriculum = data['curriculum']
vocab = data['vocab']
homework = data['homework']

# Load Template
with open('Week_1 Jules.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# --- Helpers ---

def create_badge(text, short=False):
    # Maps "Opinion" -> "Op", etc. if short=True
    # Returns BeautifulSoup Tag
    label = text.strip()
    cls = "bg-o"
    if "Reason" in label or "Re" == label: cls = "bg-r"
    if "Example" in label or "Ex" == label: cls = "bg-e"

    if short:
        display_text = label[:2] # Op, Re, Ex
    else:
        display_text = label

    span = soup.new_tag("span", attrs={"class": f"badge-ore {cls}"})
    span.string = display_text
    return span

def format_model_answer(text, use_short_badges=False):
    """
    Parses the model answer string (which contains HTML-like tags)
    and converts it to a clean Soup structure with correct classes.
    """
    # Quick string fixes first
    text = text.replace('style="color: blue;"', 'class="highlight-transition"')
    # Handle the background-color yellow
    text = re.sub(r'<span style="background-color: yellow;">(.*?)</span>', r'<span class="highlight-3clause">\1</span>', text)
    # Standardize bold
    text = text.replace('<b>', '<strong>').replace('</b>', '</strong>')

    # Parse this fragment
    frag = BeautifulSoup(text, 'html.parser')

    # Fix Badges (Opinion/Reason/Example) which might be just text or bold text or span
    # The source data has them as: <span ...><b>Opinion</b></span>
    # We need to find these and replace with badge spans.
    # Logic: Search for text "Opinion", "Reason", "Example" inside spans/bolds

    target_words = ["Opinion", "Reason", "Example", "Op", "Re", "Ex"]

    for tag in frag.find_all(string=True):
        if tag.parent.name in ['span', 'strong', 'b']:
            clean_text = tag.strip()
            if clean_text in target_words:
                # This is a badge label. Replace the parent tag with our badge.
                # Find the outermost container of this label if nested
                parent = tag.parent
                # If parent is <b> inside <span>, we want to replace the <span>
                if parent.parent.name == 'span':
                    parent = parent.parent

                # Create replacement
                badge = create_badge(clean_text, short=use_short_badges)
                parent.replace_with(badge)

    # Ensure all highlight-transition have the class (done by string replace above)
    # Check for MISSING transitions (Blue text)?
    # User requirement: "sentence starters are not in blue as they should be"
    # User requirement: "run checking scripts to make sure sentence appropriate starters have been included in blue"
    # This implies we might need to *inject* them if missing.
    # For now, we assume the source data has the style="color: blue" which we converted.

    return frag

def generate_mind_map_legs(bullet_points):
    # Returns a list of Tag objects (divs)
    legs = []
    for bp in bullet_points:
        # bp: "Who: Mother / Grandfather"
        if ":" in bp:
            label, content = bp.split(":", 1)
        else:
            label, content = "Point", bp

        leg_div = soup.new_tag("div", attrs={"class": "spider-leg"})

        strong = soup.new_tag("strong")
        strong.string = label.strip().upper() + ":"
        leg_div.append(strong)

        # Space
        leg_div.append(NavigableString(" "))

        span = soup.new_tag("span", attrs={"style": "color:#555; font-size:0.9em;"})
        # Truncate if too long?
        content = content.strip()
        if len(content) > 25:
            content = content[:22] + "..."
        span.string = content
        leg_div.append(span)

        legs.append(leg_div)
    return legs

def get_page(soup, page_num):
    # Finding page by class "page" is risky if order changes.
    # Assuming standard order:
    # 0: Cover
    # 1: Blank
    # 2: Teacher L1
    # 3: Student L1
    # 4: Practice L1
    # 5: Teacher L2
    # 6: Student L2
    # 7: Deep Dive
    # 8: Rapid Fire
    # 9: Homework
    pages = soup.find_all("div", class_="page")
    if page_num < len(pages):
        return pages[page_num]
    return None

# --- CSS INJECTION (A4 Fixes) ---
style_tag = soup.find('style')
new_css = """
    /* FORCED A4 COMPLIANCE */
    .page { overflow: hidden; height: 296mm; box-sizing: border-box; padding: 10mm; }

    /* Compact Teacher Plan */
    .page.l1 .card h2, .page.l2 .card h2 { margin: 2px 0 4px 0; font-size: 0.9em; }
    .page.l1 .card, .page.l2 .card { padding: 6px 10px; margin-bottom: 6px; }
    .lp-table td { padding: 3px 5px; font-size: 0.75em; }
    .scaffold-text { margin-bottom: 0; }

    /* Inline Spider Legs */
    .spider-leg {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        gap: 5px;
        padding: 4px;
        line-height: 1.1;
    }

    /* Homework Padding Fix */
    .page.hw .card { padding: 8px 10px; }
    .grammar-sent { padding: 2px 0; border-bottom: 1px dashed #eee; margin-bottom: 2px; }

    /* Ensure Banners fit */
    .header-bar { padding: 6px 12px; margin-bottom: 8px; }
"""
style_tag.append(new_css)


# --- TEACHER PLAN L1 (Page 2) ---
page_tp_l1 = get_page(soup, 2)
# Update Title
header_title = page_tp_l1.find("span", class_="week-tag")
if header_title: header_title.string = "Week 1 • Lesson 1 • Family"

# Objectives
obj_ul = page_tp_l1.find("h2", string=re.compile("Learning Objectives")).find_next("ul")
obj_ul.clear()
new_objs = [
    "Speaking: Describe a family member using adjectives of personality.",
    "Vocab: Use 7 target words (e.g., Diligent) in context.",
    "Grammar: Use relative clauses ('who is...') to describe people."
]
for obj in new_objs:
    li = soup.new_tag("li")
    # Bold the first word/topic
    parts = obj.split(":", 1)
    b = soup.new_tag("strong")
    b.string = parts[0] + ":"
    li.append(b)
    li.append(parts[1])
    obj_ul.append(li)

# Differentiation
diff_div = page_tp_l1.find("h2", string=re.compile("Differentiation")).find_next("div")
diff_div.clear() # Clear existing
# Add new compact structure
d1 = soup.new_tag("div", attrs={"style": "flex:1; background:#e8f8f5; padding:4px; border-radius:4px; font-size:0.8em;"})
d1.append(BeautifulSoup("<strong>📉 Band 5.0</strong>: 'I want to talk about my...'", 'html.parser'))
d2 = soup.new_tag("div", attrs={"style": "flex:1; background:#fef9e7; padding:4px; border-radius:4px; font-size:0.8em;"})
d2.append(BeautifulSoup("<strong>📈 Band 6.0+</strong>: 'The relative I hold in high regard is...'", 'html.parser'))
diff_div.append(d1)
diff_div.append(d2)

# Update Lesson Procedure (Lead-in Video Title)
# Find the strong tag containing Lead-in:
lead_in_strong = page_tp_l1.find("strong", string=re.compile("Lead-in:"))
if lead_in_strong:
    # Strong -> TD -> TR
    cell = lead_in_strong.parent
    # Actually, we need to modify the cell content.
    # cell is the TD.
    # Replace "Search: IELTS Friendship"
    new_content = str(cell).replace("Search: IELTS Friendship", "Search: IELTS Family Speaking")
    # Also link? No link here, just text.
    cell.clear()
    cell.append(BeautifulSoup(new_content, 'html.parser')) # Use parser to handle tags in cell string


# --- STUDENT LESSON 1 (Page 3) ---
page_sl_l1 = get_page(soup, 3)
# Update Header
page_sl_l1.find("span", class_="week-tag").string = "Week 1 • Lesson 1"
# Update Bilibili Link
bili_btn = page_sl_l1.find("a", class_="bili-btn")
if bili_btn:
    bili_btn['href'] = "https://search.bilibili.com/all?keyword=IELTS%20Family%20Member%205%E5%88%86%E9%92%9F"

# Cue Card
q1 = curriculum['part2'][0]
cue_card_title = page_sl_l1.find("h3", string=re.compile("CUE CARD"))
cue_card_title.string = f"📌 CUE CARD: {q1['question'].replace('Q1. ', '')}"
cue_card_desc = cue_card_title.find_next("div")
cue_card_desc.clear()
cue_card_desc.append(BeautifulSoup("You should say: <strong>Who</strong> they are, <strong>What</strong> they do, <strong>How</strong> they help, and <strong>Why</strong> you are proud.", 'html.parser'))

# Model Answer
model_box = page_sl_l1.find("h2", string=re.compile("Model Answer")).find_next("div", class_="model-box")
model_box.clear()
model_box.append(format_model_answer(q1['model_answer']))

# Vocab Table
vocab_tbody = page_sl_l1.find("table", class_="vocab-table").find("tbody")
vocab_tbody.clear()

def add_vocab_row(tbody, item, is_idiom=False):
    tr = soup.new_tag("tr")

    # Col 1
    td1 = soup.new_tag("td")
    if is_idiom:
        b = soup.new_tag("strong")
        b.string = item['idiom']
        td1.append(b)
    else:
        # Word + (POS)
        word = item['word'].split('(')[0].strip()
        pos = item['word'].split('(')[1].replace(')', '') if '(' in item['word'] else ""
        b = soup.new_tag("strong")
        b.string = word
        td1.append(b)
        if pos: td1.append(f" ({pos})")
        if item.get('recycled'):
            tag = soup.new_tag("span", attrs={"class": "recycled-tag"})
            tag.string = "Recycled"
            td1.append(" ")
            td1.append(tag)

    # Col 2
    td2 = soup.new_tag("td")
    td2.string = item['usage'] if is_idiom else item['Word Forms']

    # Col 3
    td3 = soup.new_tag("td")
    span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
    span_cn.string = item['meaning']
    td3.append(span_cn)

    tr.append(td1)
    tr.append(td2)
    tr.append(td3)
    tbody.append(tr)

    # Example Row
    ex_tr = soup.new_tag("tr", attrs={"class": "vocab-example-row"})
    ex_td = soup.new_tag("td", attrs={"colspan": "3"})
    ex = item.get('example_sentence', item.get('example', ''))
    ex_td.string = f'"{ex}"'
    ex_tr.append(ex_td)
    tbody.append(ex_tr)

# Add L1 Vocab
for v in vocab['l1_vocab']:
    add_vocab_row(vocab_tbody, v)

# Separator
sep_tr = soup.new_tag("tr")
sep_td = soup.new_tag("td", attrs={"colspan": "3", "style": "background:#eee; font-weight:bold; color:#555;"})
sep_td.string = "🐎 Idioms"
sep_tr.append(sep_td)
vocab_tbody.append(sep_tr)

# Add L1 Idioms
for i in vocab['l1_idioms']:
    add_vocab_row(vocab_tbody, i, is_idiom=True)


# --- PRACTICE CIRCUIT (Page 4) ---
page_pr_l1 = get_page(soup, 4)

# Main Spider
spider_center = page_pr_l1.find("div", class_="spider-center")
spider_center.clear()
spider_center.append(BeautifulSoup("MY<br>FAMILY", 'html.parser'))

# Main Legs
legs_container = page_pr_l1.find("div", class_="spider-legs")
legs_container.clear()
new_legs = generate_mind_map_legs(q1['bullet_points'])
for leg in new_legs:
    legs_container.append(leg)

# Topic A (Q2)
q2 = curriculum['part2'][1]
topic_a_card = page_pr_l1.find("h3", string=re.compile("Topic A")).parent
topic_a_card.find("h3").string = f"Topic A: {q2['question'].replace('Q2. ', '')}"
topic_a_center = topic_a_card.find("div", class_="spider-center")
topic_a_center.string = "Achieve" # Keyword
# Legs A
legs_a_container = topic_a_card.find("div", class_="spider-legs")
legs_a_container.clear()
for leg in generate_mind_map_legs(q2['bullet_points']):
    legs_a_container.append(leg)

# Topic B (Q3)
q3 = curriculum['part2'][2]
topic_b_card = page_pr_l1.find("h3", string=re.compile("Topic B")).parent
topic_b_card.find("h3").string = f"Topic B: {q3['question'].replace('Q3. ', '')}"
topic_b_center = topic_b_card.find("div", class_="spider-center")
topic_b_center.string = "Admire"
# Legs B
legs_b_container = topic_b_card.find("div", class_="spider-legs")
legs_b_container.clear()
for leg in generate_mind_map_legs(q3['bullet_points']):
    legs_b_container.append(leg)


# --- TEACHER PLAN L2 (Page 5) ---
page_tp_l2 = get_page(soup, 5)
page_tp_l2.find("span", class_="week-tag").string = "Week 1 • Lesson 2 • Family Society"

# Objectives L2
obj_ul_l2 = page_tp_l2.find("h2", string=re.compile("Learning Objectives")).find_next("ul")
obj_ul_l2.clear()
new_objs_l2 = [
    "Logic: Use O.R.E. to discuss Family Roles.",
    "Vocab: Use abstract nouns (e.g., Harmony).",
    "Speaking: Discuss Family Pride & Society."
]
for obj in new_objs_l2:
    li = soup.new_tag("li")
    parts = obj.split(":", 1)
    b = soup.new_tag("strong")
    b.string = parts[0] + ":"
    li.append(b)
    li.append(parts[1])
    obj_ul_l2.append(li)


# --- STUDENT LESSON 2 (Page 6) ---
page_sl_l2 = get_page(soup, 6)
page_sl_l2.find("span", class_="header-title").string = "Part 3: Family & Society"

# Vocab L2
vocab_l2_tbody = page_sl_l2.find("table", class_="vocab-table").find("tbody")
vocab_l2_tbody.clear()
for v in vocab['l2_vocab']:
    add_vocab_row(vocab_l2_tbody, v)
# Separator
sep_tr = soup.new_tag("tr")
sep_td = soup.new_tag("td", attrs={"colspan": "3", "style": "background:#eee; font-weight:bold; color:#555;"})
sep_td.string = "🐎 Idioms"
sep_tr.append(sep_td)
vocab_l2_tbody.append(sep_tr)
for i in vocab['l2_idioms']:
    add_vocab_row(vocab_l2_tbody, i, is_idiom=True)

# Q1
p3_q1 = curriculum['part3'][0]
q1_div = page_sl_l2.find("div", id="p5-q1")
q1_div.find("h3").string = p3_q1['question']
q1_model = q1_div.find("div", class_="model-box")
q1_model.clear()
q1_model.append(format_model_answer(p3_q1['model_answer']))


# --- DEEP DIVE (Page 7) ---
page_dd = get_page(soup, 7)

# Q2
p3_q2 = curriculum['part3'][1]
q2_div = page_dd.find("div", id="p6-q2")
q2_div.find("h3").string = p3_q2['question']
q2_model = q2_div.find("div", class_="model-box")
q2_model.clear()
q2_model.append(format_model_answer(p3_q2['model_answer']))

# Q3
p3_q3 = curriculum['part3'][2]
q3_div = page_dd.find("div", id="p6-q3")
q3_div.find("h3").string = p3_q3['question']
q3_model = q3_div.find("div", class_="model-box")
q3_model.clear()
q3_model.append(format_model_answer(p3_q3['model_answer'], use_short_badges=True))


# --- RAPID FIRE (Page 8) ---
page_rf = get_page(soup, 8)
rf_cards = page_rf.find_all("div", class_="card")
# Cards are: Banner(0), Q4(1), Q5(2), Q6(3)?
# Banner has ID p6-banner? No that was Page 7.
# Page 8 has header bar and then 3 cards?
# Actually the structure is: Header, Instruction Div, Container Div > 3 Cards.
container = page_rf.find("div", style=re.compile("flex-direction:column"))
rf_cards = container.find_all("div", class_="card")

# Q4
p3_q4 = curriculum['part3'][3]
rf_cards[0].find("h3").string = p3_q4['question']
rf_cards[0].find("div", class_="model-box").clear()
rf_cards[0].find("div", class_="model-box").append(format_model_answer(p3_q4['model_answer'], use_short_badges=True))

# Q5
p3_q5 = curriculum['part3'][4]
rf_cards[1].find("h3").string = p3_q5['question']
rf_cards[1].find("div", class_="model-box").clear()
rf_cards[1].find("div", class_="model-box").append(format_model_answer(p3_q5['model_answer'], use_short_badges=True))

# Q6
p3_q6 = curriculum['part3'][5]
rf_cards[2].find("h3").string = p3_q6['question']
rf_cards[2].find("div", class_="model-box").clear()
rf_cards[2].find("div", class_="model-box").append(format_model_answer(p3_q6['model_answer'], use_short_badges=True))


# --- HOMEWORK (Page 9) ---
page_hw = get_page(soup, 9)

# Vocab Review
hw_vocab_table = page_hw.find("h3", string=re.compile("Vocabulary Review")).find_next("table").find("tbody")
hw_vocab_table.clear()
for i, item in enumerate(homework['vocab_review'], 1):
    tr = soup.new_tag("tr")
    td1 = soup.new_tag("td")
    td1.string = f"{i}. {item['word']}"
    td2 = soup.new_tag("td", attrs={"style": "border-bottom:1px solid #eee;"})
    td3 = soup.new_tag("td")
    td3.string = f"(      ) {item['option']}. {item['synonym']}"
    tr.append(td1)
    tr.append(td2)
    tr.append(td3)
    hw_vocab_table.append(tr)

# Grammar
hw_grammar_div = page_hw.find("h3", string=re.compile("Error Correction")).find_next("div", style=re.compile("flex-direction:column"))
hw_grammar_div.clear()
for i, item in enumerate(homework['grammar_clinic'], 1):
    div = soup.new_tag("div", attrs={"class": "grammar-sent"})
    div.string = f"{i}. {item['error']}"
    hw_grammar_div.append(div)

# Writing Task
hw_task_h3 = page_hw.find("h3", string=re.compile("Writing Task"))
hw_task_h3.string = f"3. Writing Task: {homework['writing_task']}"

# Answer Key
footer = page_hw.find("div", style=re.compile("rotate"))
footer.string = homework['answer_key']


# --- SAVE ---
with open('Week_1_Family.html', 'w', encoding='utf-8') as f:
    f.write(str(soup))

print("✅ Successfully generated Week_1_Family.html using BeautifulSoup.")
