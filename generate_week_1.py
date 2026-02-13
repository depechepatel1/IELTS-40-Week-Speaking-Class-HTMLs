import json
import re
import os
import random
from bs4 import BeautifulSoup
import copy

# ==========================================
# 1. DATA LOADING
# ==========================================

def load_data(week_num=1):
    print(f"Loading data for Week {week_num}...")

    with open('Curriculum 0 final.txt', 'r', encoding='utf-8') as f:
        curriculum_data = json.load(f)
    week_curriculum = next((item for item in curriculum_data if item["week"] == week_num), None)
    if not week_curriculum: raise ValueError(f"Week {week_num} not found in Curriculum.")

    with open('vocab_plan.txt', 'r', encoding='utf-8') as f:
        vocab_content = f.read()
    vocab_blocks = vocab_content.split(']\n[')
    week_vocab = None
    for i, block in enumerate(vocab_blocks):
        json_str = block + ']' if i == 0 else ('[' + block if i == len(vocab_blocks) - 1 else '[' + block + ']')
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                found = next((item for item in data if item.get("week") == week_num), None)
                if found:
                    week_vocab = found
                    break
        except: pass

    if not week_vocab: raise ValueError(f"Week {week_num} not found in Vocab Plan.")

    with open('homework_plan.json', 'r', encoding='utf-8') as f:
        homework_data = json.load(f)
    week_homework = next((item for item in homework_data if item["week"] == week_num), None)
    if not week_homework: raise ValueError(f"Week {week_num} not found in Homework Plan.")

    return week_curriculum, week_vocab, week_homework

# ==========================================
# 2. CONTENT PROCESSING
# ==========================================

TRANSITIONS_INFORMAL = [
    "To start off,", "Actually,", "To be honest,", "As a matter of fact,",
    "Funny enough,", "Speaking of,", "Moving on to,", "What's more,",
    "On top of that,", "Finally,", "All in all,"
]

TRANSITIONS_FORMAL = [
    "It is generally agreed that", "From my perspective,", "Consequently,",
    "Furthermore,", "In addition,", "Conversely,", "For instance,",
    "It is evident that", "Undoubtedly,", "To summarize,"
]

def clean_text(text):
    # Remove Q1., Q2. etc from within text if present
    return re.sub(r'Q\d+\.\s*', '', text).strip()

def extract_topic_keyword(topic_str):
    # "People (A Family Member You Are Proud Of)" -> "Family"
    # "Places (Working Abroad...)" -> "Working Abroad"
    if "(" in topic_str:
        inner = topic_str.split("(")[1].split(")")[0]
        # Heuristic: pick the first Noun or main concept.
        # For "A Family Member You Are Proud Of", "Family" is good.
        if "Family" in inner: return "Family"
        if "Working Abroad" in inner: return "Working Abroad"
        return inner.split(" ")[0] # Fallback
    return topic_str.split(" ")[0]

def generate_differentiation(topic_keyword):
    # PGCE QTS strategies
    return {
        "band5": f"Sentence Starter: 'I really admire my... because...'",
        "band6": f"Complex Grammar: Use 'who' relative clauses (e.g., 'My father, who is...')"
    }

def process_mind_map_node(question_text):
    # "Describe a family member who you are proud of." -> "FAMILY MEMBER"
    # Simple heuristic: remove "Describe a ", take next 2 words or noun phrase
    text = clean_text(question_text) # Clean Q1. first
    text = text.replace("Describe a ", "").replace("Describe an ", "")
    # Rough extraction
    words = text.split()
    if len(words) >= 2:
        return f"{words[0]} {words[1]}".upper()
    return words[0].upper()

def inject_transitions(html_content, type='informal'):
    # This acts on the HTML content of the model answer
    # 1. Replace existing blue styles with class FIRST
    str_content = html_content
    str_content = re.sub(r'<span style="color: blue;"><b>(.*?)</b></span>', r'<span class="highlight-transition">\1</span>', str_content)
    str_content = re.sub(r'<span style="color: blue;">(.*?)</span>', r'<span class="highlight-transition">\1</span>', str_content)

    # 2. Inject into EVERY sentence if missing.
    # Logic: Split by ". " (Period + Space) which usually marks end of sentence.
    # We need to avoid splitting inside tags, but the input text is mostly text with inline tags.
    # We will iterate through parts.

    parts = re.split(r'(\.\s+)', str_content)
    new_parts = []

    # Select transition list
    t_list = TRANSITIONS_INFORMAL if type == 'informal' else TRANSITIONS_FORMAL

    for i, part in enumerate(parts):
        # Skip delimiters
        if re.match(r'\.\s+', part):
            new_parts.append(part)
            continue

        # If empty part, skip
        if not part.strip():
            new_parts.append(part)
            continue

        # Check if this part starts with a transition span
        # or inside a yellow highlighted span which contains a transition
        has_trans = '<span class="highlight-transition">' in part[:100] # Check start

        # Also check if it starts with <span class="badge-ore ..."> which counts as "handled" for Part 3 logic (separately)
        # But this function is generic.
        # For Part 2, we want every sentence.

        if not has_trans and not part.strip().startswith('<'):
            # It's plain text start. Inject.
            # Avoid injecting if it's just a closing tag or short text?
            if len(part.strip()) > 2:
                t = random.choice(t_list)
                # Capitalize first letter of part if we inject?
                # Actually we prepend, so the transition is Capitalized (usually in list),
                # and the original sentence might need lowercasing if it wasn't a proper noun?
                # Let's just prepend. "To start off, He works..." is acceptable.
                part = f'<span class="highlight-transition">{t}</span> {part}'

        new_parts.append(part)

    return "".join(new_parts)

def process_ore_part3(html_content):
    # Source: <span style="background-color: #e0f7fa...><b>Opinion</b></span> ...
    # Target: <span class="badge-ore bg-o">Op</span> ...

    str_content = html_content

    # Replace Opinion badges
    str_content = re.sub(r'<span style="background-color: #e0f7fa[^>]*><b>Opinion</b></span>', r'<span class="badge-ore bg-o">Op</span>', str_content)

    # Replace Reason badges
    str_content = re.sub(r'<span style="background-color: #fff3e0[^>]*><b>Reason</b></span>', r'<span class="badge-ore bg-r">Re</span>', str_content)

    # Replace Example badges
    str_content = re.sub(r'<span style="background-color: #f1f8e9[^>]*><b>Example</b></span>', r'<span class="badge-ore bg-e">Ex</span>', str_content)

    # Fix standard blue transitions to class
    str_content = re.sub(r'<span style="color: blue;"><b>(.*?)</b></span>', r'<span class="highlight-transition">\1</span>', str_content)

    # Ensure transitions follow badges
    # Pattern: Badge followed by content.
    # We want to find: (<span class="badge-ore ...">...</span>)(\s*)(.*?)
    # And check if group 3 starts with <span class="highlight-transition">

    def inject_after_badge_callback(match):
        badge = match.group(1)
        space = match.group(2)
        content = match.group(3)

        # If content starts with a transition span, leaving it alone
        if content.strip().startswith('<span class="highlight-transition">'):
            return match.group(0)

        # If content starts with <span style="background... which usually contains a transition inside, check that
        if content.strip().startswith('<span style="background'):
             # It might be the yellow highlight.
             # <span style="background-color: yellow;"><b><span class="highlight-transition">Unless</span>...
             if '<span class="highlight-transition">' in content[:100]:
                 return match.group(0)

        # Otherwise inject
        t = random.choice(TRANSITIONS_FORMAL)
        return f'{badge} <span class="highlight-transition">{t}</span>{space}{content}'

    # Regex to find Badge and immediate following content up to next badge or end
    # Note: Content might contain tags.
    # We match: (Badge)(Spaces)(Rest of text until next badge start or end of string)
    # But we can't match "until next badge" easily in one pass with replacement without consuming it.
    # Instead, we just look at the immediate start of the text after the badge.

    # We will split the text by the badges to process segments.
    # But regex replace is easier if we just match (Badge)(\s*)([^<]+|<(?!span class="badge-ore)|<span(?! class="badge-ore))
    # Actually, simpler:
    # Find all badges.

    # Let's try a regex that matches the badge and lookahead? No, replacement needs to consume.
    # We will iteratively replace.

    # Regex: (<span class="badge-ore [^>]+>[^<]+</span>)(\s*)(<span class="highlight-transition">)?
    # This checks if the transition is present immediately.

    # Strategy:
    # 1. Split string by (<span class="badge-ore [^>]+>[^<]+</span>)
    # This gives [Pre-text, Badge1, Post-text1, Badge2, Post-text2...]

    pattern = r'(<span class="badge-ore [^>]+>[^<]+</span>)'
    parts = re.split(pattern, str_content)

    result = []
    for i, part in enumerate(parts):
        # Even indices are text content, Odd indices are Badges (0 is pre-text usually empty or Opener)

        if re.match(pattern, part):
            result.append(part) # Add badge
            continue

        # This is a text part following a badge (or start of string)
        # Check if previous part was a badge
        if i > 0 and re.match(pattern, parts[i-1]):
            # This 'part' is the text following a badge.
            # Check if it has transition
            stripped = part.strip()

            has_transition = False
            if stripped.startswith('<span class="highlight-transition">'):
                has_transition = True
            elif stripped.startswith('<span style="background') and '<span class="highlight-transition">' in part[:150]:
                has_transition = True

            if not has_transition and len(stripped) > 1: # Ignore empty/space
                t = random.choice(TRANSITIONS_FORMAL)
                # Inject transition at start of part, preserving leading whitespace
                # part = " Text..." -> " <span...>Trans</span> Text..."
                leading_space = part[:len(part)-len(part.lstrip())]
                rest = part.lstrip()
                part = f'{leading_space}<span class="highlight-transition">{t}</span> {rest}'

        result.append(part)

    return "".join(result)

# ==========================================
# 3. HTML GENERATION
# ==========================================

def generate_html(week_num, curr, vocab, hw):
    # Load Template
    with open('Week_2_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        template_html = f.read()

    soup = BeautifulSoup(template_html, 'html.parser')

    topic_keyword = extract_topic_keyword(curr['topic'])

    # --------------------------
    # GLOBAL & COVER
    # --------------------------
    soup.title.string = f"Week {week_num} Lesson Plan"

    # Cover Page
    soup.find('h1', class_='cover-week').string = f"WEEK {week_num}"
    theme_texts = soup.find_all('h2', class_='cover-theme-text')
    if len(theme_texts) >= 2:
        theme_texts[0].string = curr['topic'] # Part 2 Theme
        theme_texts[1].string = "Discussion & Abstract Concepts" # Part 3 Theme (Generic or derived)

    # --------------------------
    # TEACHER PLAN (Page 3)
    # --------------------------
    # Update Header
    header_title = soup.find('span', class_='week-tag')
    if header_title: header_title.string = f"Week {week_num} • Lesson 1 • {topic_keyword}"

    # Update Differentiation
    diff_strategies = generate_differentiation(topic_keyword)
    diff_box = soup.find('div', class_='card') # We need to find the specific differentiation card.
    # It has <h2>🧩 Differentiation</h2>
    for h2 in soup.find_all('h2'):
        if "Differentiation" in h2.text:
            diff_card = h2.parent
            divs = diff_card.find_all('div', style=True) # The inner boxes
            if len(divs) >= 2:
                divs[0].contents[-1].replace_with(diff_strategies['band5']) # Band 5
                divs[1].contents[-1].replace_with(diff_strategies['band6']) # Band 6

    # Update Bilibili Search
    # Search term: "IELTS [Topic] Speaking"
    bili_search = f"IELTS {topic_keyword} Speaking"
    # Find the row in procedure table
    proc_table = soup.find('table', class_='lp-table')
    if proc_table:
        first_row = proc_table.find('tbody').find_tr_next_sibling # or find_all('tr')[0]
        rows = proc_table.find('tbody').find_all('tr')
        if rows:
            lead_in_cell = rows[0].find_all('td')[1]
            # Replace text "Search: IELTS Hometown" with new search
            lead_in_cell.string = lead_in_cell.text.replace("IELTS Hometown", bili_search)
            # Update 'Ask:' question
            lead_in_cell.string = re.sub(r"Ask: '.*?'", f"Ask: 'Tell me about your {topic_keyword.lower()}.'", lead_in_cell.string)

    # Update Bilibili Link Button HREF (Student Handout)
    bili_btns = soup.find_all('a', class_='bili-btn')
    for btn in bili_btns:
        btn['href'] = f"https://search.bilibili.com/all?keyword={bili_search.replace(' ', '%20')}"

    # --------------------------
    # STUDENT L1 (Page 4)
    # --------------------------
    # Find Page 4 container (div class="page l1" - second occurrence)
    page_l1_student = soup.find_all('div', class_='page l1')[1]

    # Update Header
    page_l1_student.find('span', class_='week-tag').string = f"Week {week_num} • Lesson 1"

    # Update Cue Card
    cue_card_box = page_l1_student.find('div', class_='card', style=lambda s: s and 'border-left:5px solid' in s)
    if cue_card_box:
        part2_q = curr['part2'][0]['question'] # Use Q1 as main
        cue_card_box.find('h3').string = f"📌 CUE CARD: {clean_text(part2_q)}"
        # Update bullets (Who, What etc) - Hard to parse dynamically perfectly, leave generic instruction or try to map
        # "You should say: Who they are..." -> The JSON doesn't strictly break this down in "question" field often.
        # But 'bullet_points' array exists in JSON!
        bullets = curr['part2'][0].get('bullet_points', [])
        if bullets:
            bullet_text = "You should say: " + ", ".join(bullets)
            cue_card_box.find('div').string = bullet_text

    # Update Model Answer
    model_box = page_l1_student.find('div', class_='model-box')
    raw_model = curr['part2'][0]['model_answer']
    processed_model = inject_transitions(raw_model, 'informal')
    if model_box:
        model_box.clear()
        model_box.append(BeautifulSoup(processed_model, 'html.parser'))

    # Update Vocab Table L1
    vocab_table = page_l1_student.find('table', class_='vocab-table')
    if vocab_table:
        tbody = vocab_table.find('tbody')
        tbody.clear()

        # Add Vocab
        for v in vocab['l1_vocab']:
            word = v['word'].split('(')[0].strip()
            pos = f"({v['word'].split('(')[1]}" if '(' in v['word'] else ""
            forms = v.get('Word Forms', '')
            meaning = v['meaning']

            row = soup.new_tag('tr')
            row.append(BeautifulSoup(f"<td><strong>{word}</strong> <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>{pos}</span></td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td>{forms}</td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td><span class='vocab-cn'>{meaning}</span></td>", 'html.parser'))
            tbody.append(row)

        # Add Idioms header
        tbody.append(BeautifulSoup("<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>", 'html.parser'))

        # Add Idioms
        for i in vocab['l1_idioms']:
            idiom = i['idiom']
            usage = i['usage']
            meaning = i['meaning']
            example = i['example_sentence']

            row = soup.new_tag('tr')
            row.append(BeautifulSoup(f"<td><strong>{idiom}</strong></td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td>{usage}</td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td><span class='vocab-cn'>{meaning}</span></td>", 'html.parser'))
            tbody.append(row)

            ex_row = soup.new_tag('tr', class_='vocab-example-row')
            ex_row.append(BeautifulSoup(f"<td colspan='3'>\"{example}\"</td>", 'html.parser'))
            tbody.append(ex_row)

    # --------------------------
    # PRACTICE CIRCUIT (Page 5)
    # --------------------------
    page_circuit = soup.find_all('div', class_='page l1')[2]

    # Update Brainstorming Map
    center_node = page_circuit.find('div', class_='spider-center')
    keyword_node = process_mind_map_node(curr['part2'][0]['question'])
    # Split for visual line break
    if " " in keyword_node:
        keyword_html = keyword_node.replace(" ", "<br>")
    else:
        keyword_html = keyword_node
    center_node.clear()
    center_node.append(BeautifulSoup(keyword_html, 'html.parser'))

    # Update Topic A/B Cards
    # We use Q2 and Q3 for these
    topics_container = page_circuit.find_all('div', class_='card')[2:] # Skip first two (Map, Banner)
    # Actually finding by style/content is safer.
    # The cards with spider-container inside.
    practice_cards = [div for div in page_circuit.find_all('div', class_='card') if div.find('div', class_='spider-container')]
    # First one is the Example map (already updated center).
    # Next two are Topic A and B.

    if len(practice_cards) >= 3:
        # Topic A -> Q2
        q2 = curr['part2'][1]
        card_a = practice_cards[1]
        card_a.find('h3').string = f"Topic A: {extract_topic_keyword(q2['question'])}"
        card_a.find('div', style=lambda s: s and 'font-size:0.85em' in s).string = q2['question']
        # Update legs? The template has generic "Who/Traits...".
        # Requirement: "Use shortened versions of the specific bullet points... give 2 one word suggestions"
        # The JSON 'bullet_points' has "Who: Uncle / Sister".
        # We need to map these to the legs.
        legs = card_a.find_all('div', class_='spider-leg')
        for idx, leg in enumerate(legs):
            if idx < len(q2['bullet_points']):
                # "Who: Uncle / Sister" -> "Who:\nUncle/Sister"
                bp_text = q2['bullet_points'][idx]
                parts = bp_text.split(":")
                label = parts[0].strip()
                sug = parts[1].strip() if len(parts) > 1 else ""
                leg.clear()
                leg.append(BeautifulSoup(f"<strong>{label}</strong><br><span style='color:#777; font-size:0.9em'>{sug}</span><div class='lines'></div>", 'html.parser'))

        # Topic B -> Q3
        q3 = curr['part2'][2]
        card_b = practice_cards[2]
        card_b.find('h3').string = f"Topic B: {extract_topic_keyword(q3['question'])}"
        card_b.find('div', style=lambda s: s and 'font-size:0.85em' in s).string = q3['question']
        legs = card_b.find_all('div', class_='spider-leg')
        for idx, leg in enumerate(legs):
            if idx < len(q3['bullet_points']):
                bp_text = q3['bullet_points'][idx]
                parts = bp_text.split(":")
                label = parts[0].strip()
                sug = parts[1].strip() if len(parts) > 1 else ""
                leg.clear()
                leg.append(BeautifulSoup(f"<strong>{label}</strong><br><span style='color:#777; font-size:0.9em'>{sug}</span><div class='lines'></div>", 'html.parser'))

    # --------------------------
    # PART 3 PAGES (6 & 7)
    # --------------------------
    # Page 6 (Vocab + Q1)
    page_l2_vocab = soup.find('div', class_='page l2', id=False) # The first one after teacher plan?
    # Actually the template has:
    # Page 4: Teacher L2
    # Page 5: Student L2 (Vocab + Q1)
    # Page 6: Deep Dive (Q1 cont, Q2, Q3)
    # Page 7: Rapid Fire (Q4, Q5, Q6)

    # Let's find Page 5
    page_p3_intro = soup.find_all('div', class_='page l2')[1]

    # Update Vocab L2
    vocab_table_l2 = page_p3_intro.find('table', class_='vocab-table')
    if vocab_table_l2:
        tbody = vocab_table_l2.find('tbody')
        tbody.clear()
        for v in vocab['l2_vocab']:
            word = v['word'].split('(')[0].strip()
            pos = f"({v['word'].split('(')[1]}" if '(' in v['word'] else ""
            forms = v.get('Word Forms', '')
            meaning = v['meaning']
            row = soup.new_tag('tr')
            row.append(BeautifulSoup(f"<td><strong>{word}</strong> <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>{pos}</span></td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td>{forms}</td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td><span class='vocab-cn'>{meaning}</span></td>", 'html.parser'))
            tbody.append(row)

        # Idioms L2
        tbody.append(BeautifulSoup("<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>", 'html.parser'))
        for i in vocab['l2_idioms']:
            idiom = i['idiom']
            usage = i['usage']
            meaning = i['meaning']
            example = i['example_sentence']
            row = soup.new_tag('tr')
            row.append(BeautifulSoup(f"<td><strong>{idiom}</strong></td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td>{usage}</td>", 'html.parser'))
            row.append(BeautifulSoup(f"<td><span class='vocab-cn'>{meaning}</span></td>", 'html.parser'))
            tbody.append(row)
            ex_row = soup.new_tag('tr', class_='vocab-example-row')
            ex_row.append(BeautifulSoup(f"<td colspan='3'>\"{example}\"</td>", 'html.parser'))
            tbody.append(ex_row)

    # Q1
    q1_card = page_p3_intro.find('div', id='p5-q1')
    if q1_card:
        q1_data = curr['part3'][0]
        q1_card.find('h3').string = q1_data['question']
        model_div = q1_card.find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q1_data['model_answer']), 'html.parser'))

        # Update Bullet Hints? "Ideas: ..."
        # Curriculum data has bullet_points like ["(Op) Get good grades", ...]
        # We should update the scaffold text.
        scaffold = q1_card.find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q1_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    # Page 6 (Q1 Cont, Q2, Q3)
    page_p3_deep = soup.find('div', id='page6')
    # Q2
    q2_card = page_p3_deep.find('div', id='p6-q2')
    if q2_card:
        q2_data = curr['part3'][1]
        q2_card.find('h3').string = q2_data['question']
        model_div = q2_card.find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q2_data['model_answer']), 'html.parser'))
        scaffold = q2_card.find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q2_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    # Q3
    q3_card = page_p3_deep.find('div', id='p6-q3')
    if q3_card:
        q3_data = curr['part3'][2]
        q3_card.find('h3').string = q3_data['question']
        model_div = q3_card.find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q3_data['model_answer']), 'html.parser'))
        scaffold = q3_card.find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q3_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    # Page 7 (Q4, Q5, Q6)
    page_p3_rapid = soup.find_all('div', class_='page l2')[3]
    q_cards = page_p3_rapid.find_all('div', class_='card compact')

    # Q4
    if len(q_cards) >= 1:
        q4_data = curr['part3'][3]
        q_cards[0].find('h3').string = q4_data['question']
        model_div = q_cards[0].find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q4_data['model_answer']), 'html.parser'))
        scaffold = q_cards[0].find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q4_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    # Q5
    if len(q_cards) >= 2:
        q5_data = curr['part3'][4]
        q_cards[1].find('h3').string = q5_data['question']
        model_div = q_cards[1].find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q5_data['model_answer']), 'html.parser'))
        scaffold = q_cards[1].find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q5_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    # Q6
    if len(q_cards) >= 3:
        q6_data = curr['part3'][5]
        q_cards[2].find('h3').string = q6_data['question']
        model_div = q_cards[2].find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q6_data['model_answer']), 'html.parser'))
        scaffold = q_cards[2].find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q6_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    # --------------------------
    # HOMEWORK (Page 8)
    # --------------------------
    page_hw = soup.find('div', class_='page hw')

    # 1. Vocab Review
    # hw['vocab_review'] is a list of dicts {word, synonym, option}
    vocab_review_card = page_hw.find('div', class_='card') # First card
    # Assuming standard structure: Table with Tbody
    tbody = vocab_review_card.find('tbody')
    tbody.clear()
    for item in hw['vocab_review']:
        # Format: <tr><td>1. Word</td><td...></td><td>( ) Option. Synonym</td></tr>
        row = soup.new_tag('tr')
        row.append(BeautifulSoup(f"<td>{item['word']}</td><td style='border-bottom:1px solid #eee;'></td><td>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {item['option']}. {item['synonym']}</td>", 'html.parser'))
        tbody.append(row)

    # 2. Error Correction
    # Reduce padding as requested
    error_card = page_hw.find_all('div', class_='card')[1]
    error_card['style'] += '; padding: 5px;' # Reduce padding

    grammar_div = error_card.find('div', style=lambda s: s and 'display:flex' in s)
    grammar_div.clear()
    for item in hw['grammar_clinic']:
        grammar_div.append(BeautifulSoup(f"<div class='grammar-sent'>{item['error']}</div>", 'html.parser'))

    # 3. Writing Task
    # Flex grow requested
    writing_card = page_hw.find_all('div', class_='card')[2]
    writing_card.find('h3').string = f"3. Writing Task: {hw['writing_task']} (17 mins)"

    # Ensure boxes fill space
    # The template has "Draft" and "Polished Rewrite" in a flex-col container
    container = writing_card.find('div', style=lambda s: s and 'flex-direction:column' in s)
    container['style'] += "; flex-grow: 1;"

    # Adjust inner boxes
    for box in container.find_all('div', style=lambda s: s and 'border:1px solid' in s):
        # Remove fixed height lines, make box grow
        box['style'] += "; flex: 1; display: flex; flex-direction: column;"
        lines = box.find('div', class_='lines')
        if lines:
            lines['style'] = "flex-grow: 1; height: auto;" # Overwrite fixed height

    # Update Answer Key at bottom
    key_div = page_hw.find('div', style=lambda s: s and 'rotate(180deg)' in s)
    if key_div:
        key_div.string = hw['answer_key']

    # WRITE OUTPUT
    output_filename = f"Week_{week_num}_Lesson_Plan.html"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    print(f"Generated {output_filename}")

# ==========================================
# 4. MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    try:
        curr, vocab, hw = load_data(1)
        generate_html(1, curr, vocab, hw)
    except Exception as e:
        print(f"Error: {e}")
