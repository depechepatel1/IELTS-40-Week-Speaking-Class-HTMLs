import json
import re
import os
import random
import argparse
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
    return re.sub(r'Q\d+\.\s*', '', text).strip()

def extract_topic_keyword(topic_str):
    if "(" in topic_str:
        inner = topic_str.split("(")[1].split(")")[0]
        if "Family" in inner: return "Family"
        if "Working Abroad" in inner: return "Working Abroad"
        return inner.split(" ")[0]
    return topic_str.split(" ")[0]

def generate_differentiation(topic_keyword):
    # PGCE QTS strategies
    return {
        "band5": f"Use template: 'In my opinion... This is because...'",
        "band6": f"Sentence Starter: 'I really admire my... because...'<br>Complex Grammar: Use 'who' relative clauses."
    }

def process_mind_map_node(question_text):
    text = clean_text(question_text)
    text = text.replace("Describe a ", "").replace("Describe an ", "")
    words = text.split()
    if len(words) >= 2:
        return f"{words[0]} {words[1]}".upper()
    return words[0].upper()

def inject_transitions(html_content, type='informal'):
    str_content = html_content
    str_content = re.sub(r'<span style="color: blue;"><b>(.*?)</b></span>', r'<span class="highlight-transition">\1</span>', str_content)
    str_content = re.sub(r'<span style="color: blue;">(.*?)</span>', r'<span class="highlight-transition">\1</span>', str_content)

    parts = re.split(r'(\.\s+)', str_content)
    new_parts = []
    t_list = TRANSITIONS_INFORMAL if type == 'informal' else TRANSITIONS_FORMAL

    for i, part in enumerate(parts):
        if re.match(r'\.\s+', part):
            new_parts.append(part)
            continue
        if not part.strip():
            new_parts.append(part)
            continue

        has_trans = '<span class="highlight-transition">' in part[:100]

        if not has_trans and not part.strip().startswith('<'):
            if len(part.strip()) > 2:
                t = random.choice(t_list)
                part = f'<span class="highlight-transition">{t}</span> {part}'

        new_parts.append(part)

    return "".join(new_parts)

def process_ore_part3(html_content):
    str_content = html_content
    str_content = re.sub(r'<span style="background-color: #e0f7fa[^>]*><b>Opinion</b></span>', r'<span class="badge-ore bg-o">Op</span>', str_content)
    str_content = re.sub(r'<span style="background-color: #fff3e0[^>]*><b>Reason</b></span>', r'<span class="badge-ore bg-r">Re</span>', str_content)
    str_content = re.sub(r'<span style="background-color: #f1f8e9[^>]*><b>Example</b></span>', r'<span class="badge-ore bg-e">Ex</span>', str_content)
    str_content = re.sub(r'<span style="color: blue;"><b>(.*?)</b></span>', r'<span class="highlight-transition">\1</span>', str_content)

    pattern = r'(<span class="badge-ore [^>]+>[^<]+</span>)'
    parts = re.split(pattern, str_content)

    result = []
    for i, part in enumerate(parts):
        if re.match(pattern, part):
            result.append(part)
            continue

        if i > 0 and re.match(pattern, parts[i-1]):
            stripped = part.strip()
            has_transition = False
            if stripped.startswith('<span class="highlight-transition">'):
                has_transition = True
            elif stripped.startswith('<span style="background') and '<span class="highlight-transition">' in part[:150]:
                has_transition = True

            if not has_transition and len(stripped) > 1:
                t = random.choice(TRANSITIONS_FORMAL)
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

    # Update CSS for Grammar Sentence (Task 2)
    style_tag = soup.find('style')
    if style_tag:
        # Append override rule for safety
        style_tag.append("\n    .grammar-sent { padding: 2px 0 !important; margin-bottom: 2px !important; }")

    # GLOBAL & COVER
    soup.title.string = f"Week {week_num} Lesson Plan"
    soup.find('h1', class_='cover-week').string = f"WEEK {week_num}"
    theme_texts = soup.find_all('h2', class_='cover-theme-text')
    if len(theme_texts) >= 2:
        theme_texts[0].string = curr['topic']
        theme_texts[1].string = "Discussion & Abstract Concepts"

    # TEACHER PLAN (Page 3)
    header_title = soup.find('span', class_='week-tag')
    if header_title: header_title.string = f"Week {week_num} • Lesson 1 • {topic_keyword}"

    # Differentiation (Task 1: Fix Layout)
    diff_strategies = generate_differentiation(topic_keyword)
    # Find specific Differentiation boxes
    # We look for the flex container inside the Differentiation card.
    # The container has 'display:flex'. The items have 'flex:1'.

    for h2 in soup.find_all('h2'):
        if "Differentiation" in h2.text:
            diff_card = h2.parent
            # Find the flex container (div with display:flex)
            flex_container = diff_card.find('div', style=lambda s: s and 'display:flex' in s)
            if flex_container:
                # Get ONLY the flex items (Band 5 and Band 6 boxes)
                boxes = flex_container.find_all('div', style=lambda s: s and 'flex:1' in s)
                if len(boxes) >= 2:
                    # Band 5 Box
                    # Find text node to replace (last child usually)
                    if boxes[0].contents:
                        boxes[0].contents[-1].replace_with(diff_strategies['band5'])
                    else:
                        boxes[0].append(diff_strategies['band5'])

                    # Band 6 Box (Inject sentence starter here)
                    content_html = diff_strategies['band6']
                    # Using BS to parse HTML in string (for <br>)
                    new_tag = BeautifulSoup(content_html, 'html.parser')
                    if boxes[1].contents:
                        boxes[1].contents[-1].replace_with(new_tag)
                    else:
                        boxes[1].append(new_tag)

    # Lesson Procedure (Task 5)
    bili_search = f"IELTS {topic_keyword} Speaking"
    proc_table = soup.find('table', class_='lp-table')
    if proc_table:
        rows = proc_table.find('tbody').find_all('tr')
        if rows:
            # Row 1: Lead-in
            lead_in_cell = rows[0].find_all('td')[1]
            # Replace text inside contents (avoid wiping strong tag)
            for child in lead_in_cell.contents:
                if isinstance(child, str):
                    new_text = child.replace("IELTS Hometown", bili_search)
                    new_text = re.sub(r"Ask: '.*?'", f"Ask: 'Tell me about your {topic_keyword.lower()}.'", new_text)
                    child.replace_with(new_text)

            # Row 2: Input (Task 5a)
            input_cell = rows[1].find_all('td')[1]
            for child in input_cell.contents:
                if isinstance(child, str) and 'Highlight "Reliable"' in child:
                    child.replace_with(child.replace('Highlight "Reliable"', "Highlight vocabulary list words"))

            # Row 3: Vocab Drill (Task 5b)
            drill_cell = rows[2].find_all('td')[1]
            for child in drill_cell.contents:
                if isinstance(child, str) and 'Students make sentences with "Thick and thin".' in child:
                    child.replace_with(child.replace('Students make sentences with "Thick and thin".', ''))

    # STUDENT L1 (Page 4)
    page_l1_student = soup.find_all('div', class_='page l1')[1]
    page_l1_student.find('span', class_='week-tag').string = f"Week {week_num} • Lesson 1"

    cue_card_box = page_l1_student.find('div', class_='card', style=lambda s: s and 'border-left:5px solid' in s)
    if cue_card_box:
        part2_q = curr['part2'][0]['question']
        cue_card_box.find('h3').string = f"📌 CUE CARD: {clean_text(part2_q)}"
        bullets = curr['part2'][0].get('bullet_points', [])
        if bullets:
            bullet_text = "You should say: " + ", ".join(bullets)
            cue_card_box.find('div').string = bullet_text

    model_box = page_l1_student.find('div', class_='model-box')
    raw_model = curr['part2'][0]['model_answer']
    processed_model = inject_transitions(raw_model, 'informal')
    if model_box:
        model_box.clear()
        model_box.append(BeautifulSoup(processed_model, 'html.parser'))

    # Update Bilibili Link
    bili_btns = soup.find_all('a', class_='bili-btn')
    for btn in bili_btns:
        btn['href'] = f"https://search.bilibili.com/all?keyword={bili_search.replace(' ', '%20')}"

    # Update Vocab Table L1
    vocab_table = page_l1_student.find('table', class_='vocab-table')
    if vocab_table:
        tbody = vocab_table.find('tbody')
        tbody.clear()
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
        tbody.append(BeautifulSoup("<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>", 'html.parser'))
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

    # PRACTICE CIRCUIT (Page 5)
    page_circuit = soup.find_all('div', class_='page l1')[2]
    center_node = page_circuit.find('div', class_='spider-center')
    keyword_node = process_mind_map_node(curr['part2'][0]['question'])
    if " " in keyword_node: keyword_html = keyword_node.replace(" ", "<br>")
    else: keyword_html = keyword_node
    center_node.clear()
    center_node.append(BeautifulSoup(keyword_html, 'html.parser'))

    practice_cards = [div for div in page_circuit.find_all('div', class_='card') if div.find('div', class_='spider-container')]
    if len(practice_cards) >= 3:
        q2 = curr['part2'][1]
        card_a = practice_cards[1]
        card_a.find('h3').string = f"Topic A: {extract_topic_keyword(q2['question'])}"
        card_a.find('div', style=lambda s: s and 'font-size:0.85em' in s).string = q2['question']
        legs = card_a.find_all('div', class_='spider-leg')
        for idx, leg in enumerate(legs):
            if idx < len(q2['bullet_points']):
                bp_text = q2['bullet_points'][idx]
                parts = bp_text.split(":")
                label = parts[0].strip()
                sug = parts[1].strip() if len(parts) > 1 else ""
                leg.clear()
                leg.append(BeautifulSoup(f"<strong>{label}</strong><br><span style='color:#777; font-size:0.9em'>{sug}</span><div class='lines'></div>", 'html.parser'))

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

    # PART 3 PAGES
    page_p3_intro = soup.find_all('div', class_='page l2')[1]
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

    q1_card = page_p3_intro.find('div', id='p5-q1')
    if q1_card:
        q1_data = curr['part3'][0]
        q1_card.find('h3').string = q1_data['question']
        model_div = q1_card.find('div', class_='model-box')
        model_div.clear()
        model_div.append(BeautifulSoup(process_ore_part3(q1_data['model_answer']), 'html.parser'))
        scaffold = q1_card.find('ul', class_='scaffold-text')
        if scaffold:
            scaffold.clear()
            for bp in q1_data['bullet_points']:
                scaffold.append(BeautifulSoup(f"<li>{bp}</li>", 'html.parser'))

    page_p3_deep = soup.find('div', id='page6')
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

    page_p3_rapid = soup.find_all('div', class_='page l2')[3]
    q_cards = page_p3_rapid.find_all('div', class_='card compact')

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

    # HOMEWORK (Page 8)
    page_hw = soup.find('div', class_='page hw')
    vocab_review_card = page_hw.find('div', class_='card')
    tbody = vocab_review_card.find('tbody')
    tbody.clear()
    for item in hw['vocab_review']:
        row = soup.new_tag('tr')
        row.append(BeautifulSoup(f"<td>{item['word']}</td><td style='border-bottom:1px solid #eee;'></td><td>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {item['option']}. {item['synonym']}</td>", 'html.parser'))
        tbody.append(row)

    # Task 2: Error Correction (Padding reduced)
    error_card = page_hw.find_all('div', class_='card')[1]
    error_card['style'] += '; padding: 5px;'
    grammar_div = error_card.find('div', style=lambda s: s and 'display:flex' in s)
    grammar_div.clear()
    for item in hw['grammar_clinic']:
        grammar_div.append(BeautifulSoup(f"<div class='grammar-sent'>{item['error']}</div>", 'html.parser'))

    # Task 3: Writing Task (Flex Grow)
    writing_card = page_hw.find_all('div', class_='card')[2]
    writing_card.find('h3').string = f"3. Writing Task: {hw['writing_task']} (17 mins)"
    # IMPORTANT: Make the Card itself a flex container so children can grow
    writing_card['style'] += "; display: flex; flex-direction: column;"

    container = writing_card.find('div', style=lambda s: s and 'flex-direction:column' in s)
    container['style'] += "; flex-grow: 1;"
    for box in container.find_all('div', style=lambda s: s and 'border:1px solid' in s):
        box['style'] += "; flex: 1; display: flex; flex-direction: column;"
        lines = box.find('div', class_='lines')
        if lines:
            lines['style'] = "flex-grow: 1; height: auto;"

    # Task 4: Recording Challenge (Text Updated)
    rec_card = page_hw.find('div', style=lambda s: s and 'background:#eafaf1' in s)
    rec_text_div = rec_card.find('div', style=lambda s: s and 'display:flex' in s)
    if rec_text_div:
        # Clear existing spans and add new text
        rec_text_div.clear()
        rec_text_div.append(BeautifulSoup("<span>1. Part 2 X 3 Qs from lesson 1 (6m)</span>", 'html.parser'))
        rec_text_div.append(BeautifulSoup("<span>2. Part 3 X 3 Qs from lesson 2 (12m)</span>", 'html.parser'))
    # Update title to 18 minutes? The prompt said "changed to 18 minutes in total".
    rec_card.find('h3').string = "🎙️ 4. Recording Challenge (18m)"

    key_div = page_hw.find('div', style=lambda s: s and 'rotate(180deg)' in s)
    if key_div: key_div.string = hw['answer_key']

    output_filename = f"Week_{week_num}_Lesson_Plan.html"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    print(f"Generated {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Weekly Lesson Plan')
    parser.add_argument('--week', type=int, default=1, help='Week number to generate')
    args = parser.parse_args()

    try:
        curr, vocab, hw = load_data(args.week)
        generate_html(args.week, curr, vocab, hw)
    except Exception as e:
        print(f"Error: {e}")
