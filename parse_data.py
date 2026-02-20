import json
import re
import os
from bs4 import BeautifulSoup

def load_concatenated_json(filepath):
    """Loads concatenated JSON arrays from a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    data = []
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(content):
        content_slice = content[pos:].lstrip()
        if not content_slice:
            break
        try:
            obj, end = decoder.raw_decode(content_slice)
            if isinstance(obj, list):
                data.extend(obj)
            else:
                data.append(obj)
            pos += end
        except json.JSONDecodeError:
            break

    return data

def load_data(week_number):
    """Loads data for the specific week from JSON files."""
    print(f"Loading data for Week {week_number}...")

    # Load Curriculum
    curriculum_data = load_concatenated_json('Curriculum 0 final.txt')
    week_curriculum = next((item for item in curriculum_data if item.get("week") == week_number), None)
    if not week_curriculum:
        raise ValueError(f"Week {week_number} not found in Curriculum 0 final.txt")

    # Load Vocabulary
    vocab_data = load_concatenated_json('vocab_plan.txt')
    week_vocab = next((item for item in vocab_data if item.get("week") == week_number), None)
    if not week_vocab:
        raise ValueError(f"Week {week_number} not found in vocab_plan.txt")

    # Load Homework
    # homework_plan.json seems to be a single JSON file, but using the same loader is safer
    homework_data = load_concatenated_json('homework_plan.json')
    week_homework = next((item for item in homework_data if item.get("week") == week_number), None)
    if not week_homework:
        raise ValueError(f"Week {week_number} not found in homework_plan.json")

    return week_curriculum, week_vocab, week_homework

def process_cover_page(soup, week_number, week_data):
    """Updates the cover page with week number and theme."""
    print("Processing Cover Page...")

    # Update Title Tag
    if soup.title:
        soup.title.string = f"Week {week_number} Master Lesson Pack"

    # Update Cover Week Number
    cover_week = soup.find('h1', class_='cover-week')
    if cover_week:
        cover_week.string = f"WEEK {week_number}"

    # Update Themes
    # Assuming Part 2 Theme is 'theme' and Topic is 'topic'
    # The template has "Part 2 Theme" -> "Describing Places" (Topic Category?)
    # and "Part 3 Theme" -> "Urbanization & Community" (Topic?)

    # In Curriculum data: "theme": "People", "topic": "A Family Member You Are Proud Of"

    theme_texts = soup.find_all('h2', class_='cover-theme-text')
    if len(theme_texts) >= 2:
        theme_texts[0].string = week_data.get('theme', 'General')
        theme_texts[1].string = week_data.get('topic', 'Discussion')

def process_teacher_plan(soup, week_number, week_data):
    """Updates Teacher Lesson Plan pages."""
    print("Processing Teacher Plan...")

    topic = week_data.get('topic', '')

    # Update Header Bars (Teacher L1, Student L1, Student Practice, Teacher L2, Student L2, Deep Dive, Rapid Fire)
    headers = soup.find_all('span', class_='week-tag')
    for header in headers:
        if 'Lesson 1' in header.string:
            header.string = f"Week {week_number} • Lesson 1 • {topic}"
        elif 'Lesson 2' in header.string:
            header.string = f"Week {week_number} • Lesson 2 • {topic} (Part 3)"
        elif 'Self-Study' in header.string:
            header.string = f"Week {week_number} • Self-Study"

    # Update Learning Objectives (Page 3)
    # Target specific LOs based on topic
    # Find the L1 Teacher Plan section
    # We look for "Teacher Lesson Plan" and then the LO card

    # Bilibili Link
    bilibili_search = f"IELTS {topic} Speaking"
    bilibili_url = f"https://search.bilibili.com/all?keyword={bilibili_search.replace(' ', '%20')}"

    bili_btns = soup.find_all('a', class_='bili-btn')
    for btn in bili_btns:
        btn['href'] = bilibili_url

    # Lead-in Question
    tables = soup.find_all('table', class_='lp-table')
    if tables:
        # Assuming first table is L1
        l1_table = tables[0]
        rows = l1_table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) > 1 and "Lead-in" in cells[1].get_text():
                question = f"Do you like {topic}?"
                if "Family" in topic:
                    question = "Do you spend much time with your family?"

                new_html = f"<strong>Lead-in:</strong> Click Bilibili icon on Student Handout (Banner) to show 5-min warmup video (Search: IELTS {topic}). Ask: '{question}'"
                cells[1].clear()
                cells[1].append(BeautifulSoup(new_html, 'html.parser'))

    # Dynamic Differentiation (All Differentiation Boxes)
    diff_cards = soup.find_all('div', class_='card')
    for card in diff_cards:
        h2 = card.find('h2')
        if h2 and "Differentiation" in h2.get_text():
            # Found a differentiation card. Update content.
            # L1 Strategy (Sentence Starter)
            band5_div = card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if band5_div:
                # Dynamic sentence starter
                starter = f"I enjoy {topic} because..."
                if "Family" in topic: starter = "My family is important because..."
                elif "Place" in topic or "Country" in topic: starter = "I would love to visit..."

                band5_div.clear()
                band5_div.append(BeautifulSoup(f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: '{starter}'", 'html.parser'))

def process_vocabulary(soup, week_number, vocab_data):
    """Injects vocabulary into L1 and L2 tables."""
    print("Processing Vocabulary...")

    # Week 1 Logic: 7 New words, 0 Recycled, 3 Idioms for L1

    # L1 Vocabulary
    l1_vocab_list = vocab_data.get('l1_vocab', [])
    l1_idioms_list = vocab_data.get('l1_idioms', [])

    # Find L1 Vocab Table (Page 2)
    # It's in the Student Lesson 1 page.
    # Look for table with class 'vocab-table' inside a 'page l1' div

    vocab_tables = soup.find_all('table', class_='vocab-table')

    # Assuming first vocab table is L1 (Page 2)
    if len(vocab_tables) >= 1:
        l1_table = vocab_tables[0]
        tbody = l1_table.find('tbody')
        if tbody:
            tbody.clear() # Clear existing rows

            # Add Words (Limit to 7 for Week 1)
            count = 0
            for word_item in l1_vocab_list:
                if count >= 7: break

                word = word_item.get('word', '').split('(')[0].strip()
                pos = word_item.get('word', '').split('(')[1].replace(')', '') if '(' in word_item.get('word', '') else ''
                forms = word_item.get('Word Forms', '')
                meaning = word_item.get('meaning', '')
                recycled = word_item.get('recycled', False)

                row_html = f"<td><strong>{word}</strong> <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>({pos})</span>"
                if recycled and week_number > 1: # Week 1 has 0 recycled logic, but checking flag
                     row_html += " <span class='recycled-tag'>Recycled</span>"
                row_html += f"</td><td>{forms}</td><td><span class='vocab-cn'>{meaning}</span></td>"

                tr = soup.new_tag('tr')
                tr.append(BeautifulSoup(row_html, 'html.parser'))
                tbody.append(tr)
                count += 1

            # Add Idioms Header
            idiom_header = soup.new_tag('tr')
            idiom_header.append(BeautifulSoup("<td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td>", 'html.parser'))
            tbody.append(idiom_header)

            # Add Idioms (Limit 3)
            i_count = 0
            for idiom_item in l1_idioms_list:
                if i_count >= 3: break

                idiom = idiom_item.get('idiom', '')
                usage = idiom_item.get('usage', '')
                meaning = idiom_item.get('cn_idiom', '') # Using cn_idiom as per template looking like Chinese
                example = idiom_item.get('example_sentence', '')

                # Row 1: Idiom Info
                row1_html = f"<td><strong>{idiom}</strong></td><td>({usage})</td><td><span class='vocab-cn'>{meaning}</span></td>"
                tr1 = soup.new_tag('tr')
                tr1.append(BeautifulSoup(row1_html, 'html.parser'))
                tbody.append(tr1)

                # Row 2: Example
                row2_html = f"<td colspan='3'>\"{example}\"</td>"
                tr2 = soup.new_tag('tr', attrs={'class': 'vocab-example-row'})
                tr2.append(BeautifulSoup(row2_html, 'html.parser'))
                tbody.append(tr2)

                i_count += 1

    # L2 Vocabulary (Page 5)
    # Assuming second vocab table is L2 (Page 5)
    if len(vocab_tables) >= 2:
        l2_table = vocab_tables[1]
        tbody = l2_table.find('tbody')
        if tbody:
            tbody.clear()

            l2_vocab_list = vocab_data.get('l2_vocab', [])
            l2_idioms_list = vocab_data.get('l2_idioms', [])

            # Add Words (Standard logic for L2?)
            # Prompt says: "Week 1 logic: Inject exactly 7 New words...". Assuming this applies to L1.
            # For L2, usually it's Abstract nouns. Let's use the data provided.

            for word_item in l2_vocab_list:
                word = word_item.get('word', '').split('(')[0].strip()
                pos = word_item.get('word', '').split('(')[1].replace(')', '') if '(' in word_item.get('word', '') else ''
                forms = word_item.get('Word Forms', '')
                meaning = word_item.get('meaning', '')

                row_html = f"<td><strong>{word}</strong> <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>({pos})</span></td><td>{forms}</td><td><span class='vocab-cn'>{meaning}</span></td>"

                tr = soup.new_tag('tr')
                tr.append(BeautifulSoup(row_html, 'html.parser'))
                tbody.append(tr)

            # Add Idioms Header
            idiom_header = soup.new_tag('tr')
            idiom_header.append(BeautifulSoup("<td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td>", 'html.parser'))
            tbody.append(idiom_header)

            for idiom_item in l2_idioms_list:
                idiom = idiom_item.get('idiom', '')
                usage = idiom_item.get('usage', '')
                meaning = idiom_item.get('cn_idiom', '')
                example = idiom_item.get('example_sentence', '')

                row1_html = f"<td><strong>{idiom}</strong></td><td>({usage})</td><td><span class='vocab-cn'>{meaning}</span></td>"
                tr1 = soup.new_tag('tr')
                tr1.append(BeautifulSoup(row1_html, 'html.parser'))
                tbody.append(tr1)

                row2_html = f"<td colspan='3'>\"{example}\"</td>"
                tr2 = soup.new_tag('tr', attrs={'class': 'vocab-example-row'})
                tr2.append(BeautifulSoup(row2_html, 'html.parser'))
                tbody.append(tr2)

def process_student_l1(soup, week_data):
    """Updates Student Lesson 1 (Page 2) content."""
    print("Processing Student L1...")

    l1_data = week_data.get('lesson_1_part_2', {})
    q1_data = l1_data.get('q1', {})

    # Update Banner Title (Part 2: Theme)
    banner_title = soup.find('span', class_='header-title', string=re.compile(r'Part 2:'))
    if banner_title:
        theme = week_data.get('theme', 'General')
        banner_title.string = f"Part 2: {theme}"

    # Update Cue Card
    # Look for "CUE CARD: Describe..."
    cue_card_div = soup.find('div', style=lambda x: x and 'border-left:5px solid #fbc02d' in x)
    if cue_card_div:
        h3 = cue_card_div.find('h3')
        # Extract question text from Q1 HTML
        q1_html = q1_data.get('html', '')
        q1_soup = BeautifulSoup(q1_html, 'html.parser')

        # The first paragraph usually contains the prompt
        prompt_p = q1_soup.find('p')
        if prompt_p:
            prompt_text = prompt_p.get_text()
            # Split "You should say"
            if "You should say" in prompt_text:
                main_q = prompt_text.split("You should say")[0].strip()
                bullets = prompt_text.split("You should say:")[1].strip() if ":" in prompt_text else ""
            else:
                main_q = prompt_text
                bullets = ""

            if h3:
                h3.string = f"📌 CUE CARD: {main_q}"

            # Update bullets div
            bullets_div = cue_card_div.find('div', style=lambda x: x and 'color:#444' in x)
            if bullets_div and bullets:
                bullets_div.string = "You should say: " + bullets.replace("<br>", ", ").replace("\n", ", ")

    # Update Model Answer
    # Look for "Band 6.5 Model Answer"
    model_div = soup.find('div', class_='model-box') # The first model box is usually L1 Q1
    if model_div:
        # Get the answer part (usually second paragraph in source html)
        answer_p = q1_soup.find_all('p')[1] if len(q1_soup.find_all('p')) > 1 else None
        if answer_p:
            # We need to preserve the formatting from source HTML (highlight-yellow, strong, etc.)
            # The source HTML seems to use <mark class="highlight-yellow"> and <span class="highlight-transition">
            # The template uses <span class="highlight-transition"> and <span class="highlight-3clause">

            # We will use the inner HTML of the answer paragraph
            # But we might need to adjust classes if they differ

            # Using content directly from source JSON's HTML field for the answer part
            # Convert <mark class="highlight-yellow"> to ? The template doesn't seem to use mark highlight-yellow in the final HTML shown in read_file,
            # but it uses highlight-3clause.
            # Wait, the prompt says "Three clause sentences: Highlight using <span class=\"highlight-3clause\">Text</span> (Red text)."
            # The source text has `<mark class="highlight-yellow">`. I should check if I need to map it.
            # Source: <mark class="highlight-yellow"><span class="highlight-transition">...
            # Template CSS: .highlight-3clause { color: #c0392b; ... }

            # Let's trust the source HTML structure if it's already generated with intended classes,
            # OR map them.
            # Source has "highlight-yellow". Template has "highlight-3clause" (Red).
            # Maybe "highlight-yellow" corresponds to "highlight-3clause"?
            # Let's replace 'highlight-yellow' with 'highlight-3clause' just in case.

            new_content = str(answer_p).replace('<p>', '').replace('</p>', '')
            new_content = new_content.replace('highlight-yellow', 'highlight-3clause')

            # Inject
            model_div.clear()
            model_div.append(BeautifulSoup(new_content, 'html.parser'))

def extract_keyword(text):
    """Extracts a central keyword from the question text."""
    # Simple heuristic: Look for noun phrase after 'Describe a/an'
    match = re.search(r'Describe (?:a|an) ([A-Za-z\s]+)(?:who|that|which|where|\.)', text, re.IGNORECASE)
    if match:
        # Take first 2 words max
        words = match.group(1).split()
        return "<br>".join(words[:2]).upper()
    return "TOPIC"

def format_mind_maps(soup, week_data):
    """Updates Mind Maps on Page 3."""
    print("Processing Mind Maps...")

    l1_data = week_data.get('lesson_1_part_2', {})
    q1 = l1_data.get('q1', {})
    q2 = l1_data.get('q2', {})
    q3 = l1_data.get('q3', {})

    # 1. Main Brainstorming Map (Top of Page 3)

    # Extract Keyword from Q1 Question
    q1_html = q1.get('html', '')
    q1_soup = BeautifulSoup(q1_html, 'html.parser')
    q1_text = q1_soup.get_text()

    # Keyword Logic
    topic = week_data.get('topic', 'Topic')
    central_text = extract_keyword(q1_text)
    if central_text == "TOPIC" and topic:
        central_text = topic.split()[0].upper()

    # Special overrides for known topics
    if "Family Member" in topic: central_text = "FAMILY<br>MEMBER"
    elif "Job" in topic: central_text = "PERFECT<br>JOB"

    # Update Center
    spider_centers = soup.find_all('div', class_='spider-center')
    if len(spider_centers) > 0:
        spider_centers[0].clear()
        spider_centers[0].append(BeautifulSoup(central_text, 'html.parser'))

    # Update Legs (Hints)
    hints = q1.get('spider_diagram_hints', ["", "", "", ""])
    spider_legs = soup.find_all('div', class_='spider-legs')
    if len(spider_legs) > 0:
        legs = spider_legs[0].find_all('div', class_='spider-leg')
        for i, leg in enumerate(legs):
            if i < len(hints):
                span = leg.find('span')
                if span:
                    span.string = hints[i]

    # 2. Topic A (Q2) -> Part 2: Q2
    topic_a_card = soup.find('h3', string=re.compile(r'Topic A:'))
    if topic_a_card:
        q2_html = q2.get('html', '')
        q2_soup = BeautifulSoup(q2_html, 'html.parser')
        q2_text = q2_soup.get_text()

        topic_a_card.string = "Part 2: Q2"

        prompt_div = topic_a_card.find_next_sibling('div')
        if prompt_div:
            prompt_div.string = q2_soup.find('p').get_text() # Full prompt

        spider_container = topic_a_card.find_next_sibling('div', class_='spider-container')
        if spider_container:
            center = spider_container.find('div', class_='spider-center')
            if center:
                center_text = extract_keyword(q2_text)
                center.clear()
                center.append(BeautifulSoup(center_text, 'html.parser'))

            q2_hints = q2.get('spider_diagram_hints', [])
            legs = spider_container.find_all('div', class_='spider-leg')
            for i, leg in enumerate(legs):
                if i < len(q2_hints):
                    if len(leg.contents) > 0:
                        leg.contents[0].replace_with(q2_hints[i])

    # 3. Topic B (Q3) -> Part 2: Q3
    topic_b_card = soup.find('h3', string=re.compile(r'Topic B:'))
    if topic_b_card:
        q3_html = q3.get('html', '')
        q3_soup = BeautifulSoup(q3_html, 'html.parser')
        q3_text = q3_soup.get_text()

        topic_b_card.string = "Part 2: Q3"

        prompt_div = topic_b_card.find_next_sibling('div')
        if prompt_div:
            prompt_div.string = q3_soup.find('p').get_text()

        spider_container = topic_b_card.find_next_sibling('div', class_='spider-container')
        if spider_container:
            center = spider_container.find('div', class_='spider-center')
            if center:
                center_text = extract_keyword(q3_text)
                center.clear()
                center.append(BeautifulSoup(center_text, 'html.parser'))

            q3_hints = q3.get('spider_diagram_hints', [])
            legs = spider_container.find_all('div', class_='spider-leg')
            for i, leg in enumerate(legs):
                if i < len(q3_hints):
                    if len(leg.contents) > 0:
                        leg.contents[0].replace_with(q3_hints[i])

def generate_peer_question(q_text):
    """Generates a dynamic peer-led follow-up question."""
    q_text = q_text.lower()
    if "why" in q_text:
        return "👥 Peer Check: Ask your partner 'Do you agree with this reason?'"
    elif "do you think" in q_text or "opinion" in q_text:
        return "👥 Peer Check: Ask your partner 'Can you give an example to support this?'"
    elif "how" in q_text:
        return "👥 Peer Check: Ask your partner 'Is this the only way?'"
    elif "difference" in q_text or "compare" in q_text:
        return "👥 Peer Check: Ask your partner 'Which one do you prefer?'"
    else:
        return "👥 Peer Check: Ask your partner 'Why do you think that?'"

def process_student_l2(soup, week_data):
    """Updates Student Lesson 2 (Part 3) Q1-Q6."""
    print("Processing Student L2...")

    l2_data = week_data.get('lesson_2_part_3', {})

    # Helper to process Q
    def update_q(q_id, q_key, container_id=None, container_elem=None):
        data = l2_data.get(q_key, {})
        html = data.get('html', '')
        soup_frag = BeautifulSoup(html, 'html.parser')

        # Extract Question Text
        q_tag = soup_frag.find('strong')
        q_text = q_tag.get_text() if q_tag else ""

        # Extract Answer HTML (Answer usually in second p tag)
        ps = soup_frag.find_all('p')
        answer_html = ""
        if len(ps) > 1:
            # We want inner HTML of the p tag
            answer_html = ''.join(map(str, ps[1].contents))
            # Fix highlighting mapping
            answer_html = answer_html.replace('highlight-yellow', 'highlight-3clause')

        # Find container
        if container_id:
            card = soup.find('div', id=container_id)
        else:
            card = container_elem

        if card:
            # Update H3
            h3 = card.find('h3')
            if h3: h3.string = q_text

            # Update Model Box
            mbox = card.find('div', class_='model-box')
            if mbox:
                mbox.clear()
                mbox.append(BeautifulSoup(answer_html, 'html.parser'))

            # Update Hints (Scaffold text)
            hints = data.get('ore_hints', [])
            scaffold = card.find('ul', class_='scaffold-text')
            if scaffold:
                scaffold.clear()
                for hint in hints:
                    li = soup.new_tag('li')
                    li.string = hint
                    scaffold.append(li)

    # Q1 (Page 5)
    update_q(1, 'q1', container_id='p5-q1')

    # Q2 (Page 6)
    update_q(2, 'q2', container_id='p6-q2')

    # Q3 (Page 6)
    update_q(3, 'q3', container_id='p6-q3')

    # Q4, Q5, Q6 (Page 7 - Rapid Fire)
    l2_pages = soup.find_all('div', class_='l2')
    if len(l2_pages) >= 4:
        page7 = l2_pages[3]
        compact_cards = page7.find_all('div', class_='card compact')
        if len(compact_cards) >= 3:
            update_q(4, 'q4', container_elem=compact_cards[0])
            update_q(5, 'q5', container_elem=compact_cards[1])
            update_q(6, 'q6', container_elem=compact_cards[2])

    # Inject Peer-Led Follow-up Questions (Differentiation)
    # Add to bottom of writing spaces (scaffold-text container)
    scaffold_uls = soup.find_all('ul', class_='scaffold-text')
    for ul in scaffold_uls:
        # Find the question text associated with this scaffold
        # The scaffold is inside a card. The card has an h3 with the question.
        card = ul.find_parent('div', class_='card')
        q_text = ""
        if card:
            h3 = card.find('h3')
            if h3: q_text = h3.get_text()

        peer_q_div = soup.new_tag('div', attrs={'style': 'font-size:0.8em; color:#3498db; margin-top:5px; font-style:italic;'})
        peer_q_div.string = generate_peer_question(q_text)
        ul.parent.append(peer_q_div)

def process_homework(soup, week_number, homework_data):
    """Updates Homework page."""
    print("Processing Homework...")

    # 1. Vocab Review
    vocab_review = homework_data.get('vocab_review', [])
    # Find table
    hw_page = soup.find('div', class_='page hw')
    vocab_table = hw_page.find('table', class_='vocab-table')
    if vocab_table:
        tbody = vocab_table.find('tbody')
        if tbody:
            tbody.clear()
            for i, item in enumerate(vocab_review):
                word = item.get('word', '')
                option = item.get('option', '')
                synonym = item.get('synonym', '')

                # Tricky part: Template has Word | Chinese | Synonym
                # JSON has Word | Synonym | Option
                # And the template seems to be a matching exercise.
                # Template: 1. Bustling | ___ | ( ) A. Necessary
                # We need to construct this.

                row_html = f"<td>{i+1}. {word}</td><td style='border-bottom:1px solid #eee;'></td><td>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {option}. {synonym}</td>"
                tr = soup.new_tag('tr')
                tr.append(BeautifulSoup(row_html, 'html.parser'))
                tbody.append(tr)

    # 2. Grammar Clinic
    grammar_data = homework_data.get('grammar_clinic', [])
    grammar_box = hw_page.find('div', style=lambda x: x and 'display:flex; flex-direction:column; gap:15px;' in x)
    if grammar_box:
        grammar_box.clear()
        for i, item in enumerate(grammar_data):
            error = item.get('error', '')
            div = soup.new_tag('div', class_='grammar-sent')
            div.string = f"{i+1}. {error}"
            grammar_box.append(div)

    # 3. Writing Task
    writing_task = homework_data.get('writing_task', '')
    writing_card = hw_page.find('h3', string=re.compile(r'Writing Task'))
    if writing_card:
        writing_card.string = f"3. Writing Task: {writing_task} (10 minutes)"

    # Resize Writing Spaces
    # 1. Make the Writing Task Card a flex container
    if writing_card:
        # Writing card is inside a div with flex-grow:1. We need to find the card div itself.
        # writing_card is the H3 element.
        card_div = writing_card.parent
        card_div['style'] += "; display:flex; flex-direction:column;"

        # 2. Make the wrapper div (containing the two boxes) flex-grow
        # The wrapper is the div with margin-top:10px
        wrapper_div = card_div.find('div', style=lambda x: x and 'margin-top:10px' in x)
        if wrapper_div:
            wrapper_div['style'] += "; flex-grow:1; display:flex; flex-direction:column;"

    # 3. Update the Draft/Rewrite boxes
    writing_spaces = hw_page.find_all('div', class_='lines')
    for space in writing_spaces:
        # Only target the writing task spaces (usually larger ones in homework)
        if space.parent.find('strong'): # Draft/Polished Rewrite boxes
             space.parent['style'] = "border:1px solid #eee; padding:10px; border-radius:6px; background:var(--bg-pastel-green); flex:1; display:flex; flex-direction:column;"
             space['style'] = "flex-grow:1; height:auto;"

    # 4. Recording Challenge
    rec_card = hw_page.find('h3', string=re.compile(r'Recording Challenge')).parent
    if rec_card:
        h3 = rec_card.find('h3')
        if h3: h3.string = "🎙️ 4. Recording Challenge (<18 Mins)"

        details_div = rec_card.find('div', style=lambda x: x and 'display:flex' in x)
        if details_div:
            details_div.clear()
            span = soup.new_tag('span')
            span.string = "Record 3 x Part 2 (6 mins) and 6 x Part 3 Questions (12 mins)."
            details_div.append(span)

    # 5. Answer Key
    answer_key = homework_data.get('answer_key', '')
    key_div = hw_page.find('div', style=lambda x: x and 'transform:rotate(180deg)' in x)
    if key_div:
        key_div.string = answer_key

def main():
    week_number = 1

    # 1. Load Data
    week_curriculum, week_vocab, week_homework = load_data(week_number)

    # 2. Load Template
    with open('Week_2_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # 3. Process Content
    process_cover_page(soup, week_number, week_curriculum)
    process_teacher_plan(soup, week_number, week_curriculum)
    process_vocabulary(soup, week_number, week_vocab)
    process_student_l1(soup, week_curriculum)
    format_mind_maps(soup, week_curriculum)
    process_student_l2(soup, week_curriculum)
    process_homework(soup, week_number, week_homework)

    # 4. Save
    output_filename = f'Week_{week_number}_Lesson_Plan.html'
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    print(f"Successfully generated {output_filename}")

if __name__ == "__main__":
    main()
