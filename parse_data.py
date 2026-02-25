import json
import re
import os
import time
import random
from bs4 import BeautifulSoup
import traceback

def load_data():
    print("Loading data files...")
    try:
        with open('master Curiculum.json', 'r', encoding='utf-8') as f:
            curriculum_data = json.load(f)
    except FileNotFoundError:
        print("Error: master Curiculum.json not found.")
        return None, None, None, None, None

    try:
        with open('noun_or_verb_phrases_for_weekly_topics.json', 'r', encoding='utf-8') as f:
            phrase_list = json.load(f)
            phrase_data = {item['week']: item for item in phrase_list}
    except FileNotFoundError:
        print("Warning: noun_or_verb_phrases_for_weekly_topics.json not found.")
        phrase_data = {}

    try:
        def load_concatenated_json(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            data = []
            decoder = json.JSONDecoder()
            pos = 0
            while pos < len(content):
                while pos < len(content) and (content[pos].isspace() or content[pos] in ',]'):
                    pos += 1
                if pos == len(content): break
                try:
                    obj, end = decoder.raw_decode(content, idx=pos)
                    if isinstance(obj, list): data.extend(obj)
                    else: data.append(obj)
                    pos = end
                except json.JSONDecodeError: pos += 1
            return data

        vocab_data_list = load_concatenated_json('vocab_plan.json')
        vocab_data = {item.get('week'): item for item in vocab_data_list}
        
        homework_data_list = load_concatenated_json('homework_plan.json')
        homework_data = {item.get('week'): item for item in homework_data_list}

    except Exception as e:
        print(f"Error loading auxiliary files: {e}")
        vocab_data = {}
        homework_data = {}
        
    try:
        with open('peer_check_questions.json', 'r', encoding='utf-8') as f:
            peer_data_list = json.load(f)
            peer_data = {item['week']: item for item in peer_data_list}
    except FileNotFoundError:
        print("Warning: peer_check_questions.json not found.")
        peer_data = {}

    return curriculum_data, phrase_data, vocab_data, homework_data, peer_data

def get_week_phrase(week_number, phrase_data):
    week_info = phrase_data.get(week_number, {})
    return week_info.get('grammar_target_phrase', 'this topic')

def process_teacher_plan(soup, week_number, week_curriculum, phrase_data):
    target_phrase = get_week_phrase(week_number, phrase_data)
    if not isinstance(target_phrase, str): target_phrase = str(target_phrase)
    
    l1_page = soup.find('div', class_='l1')
    if l1_page:
        lo_card = l1_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                for li in ul.find_all('li'):
                    if "Grammar:" in li.text:
                        li.string = f"Grammar: Use narrative tenses or relevant grammar for {target_phrase}."
        
        diff_card = l1_page.find('h2', string=re.compile(r'Differentiation')).parent
        if diff_card:
            b5_div = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if b5_div:
                b5_div.clear()
                b5_html = f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: 'I like {target_phrase} because...'<br>• Peer Check: Simple generic prompts (e.g., 'Why?')."
                b5_div.append(BeautifulSoup(b5_html, 'html.parser'))
            
            b6_div = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if b6_div:
                b6_div.clear()
                b6_html = f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: 'Admittedly...', 'Conversely...'<br>• Peer Check: Ask specific questions about {target_phrase}."
                b6_div.append(BeautifulSoup(b6_html, 'html.parser'))

        lp_table = l1_page.find('table', class_='lp-table')
        if lp_table:
            rows = lp_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 1 and "Lead-in" in cells[1].text:
                    topic = week_curriculum.get('topic', 'IELTS Speaking')
                    search_term = f"IELTS {topic} Speaking"
                    new_html = f"<strong>Lead-in:</strong> Click Bilibili icon on Student Handout (Banner) to show 5-min warmup video (Search: {search_term}). Ask: 'Do you think {target_phrase} is important in your life?'"
                    cells[1].clear()
                    cells[1].append(BeautifulSoup(new_html, 'html.parser'))

    l2_pages = soup.find_all('div', class_='l2')
    l2_teacher_page = None
    for p in l2_pages:
        if "Teacher Lesson Plan" in p.text:
            l2_teacher_page = p
            break

    if l2_teacher_page:
        lo_card = l2_teacher_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                for li in ul.find_all('li'):
                    if "Speaking:" in li.text:
                        li.string = f"Speaking: Discuss abstract ideas about {target_phrase}."

        diff_card = l2_teacher_page.find('h2', string=re.compile(r'Differentiation')).parent
        if diff_card:
            b6_div = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if b6_div:
                b6_div.clear()
                b6_html = f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: 'Admittedly...', 'Conversely...'<br>• Peer Check: Ask: 'Do you think {target_phrase} is important in your life?'"
                b6_div.append(BeautifulSoup(b6_html, 'html.parser'))

def format_mind_maps(soup, week_number, phrase_data):
    target_phrase = get_week_phrase(week_number, phrase_data).upper()
    spider_centers = soup.find_all('div', class_='spider-center')
    for center in spider_centers:
        center.clear()
        center.append(BeautifulSoup(target_phrase, 'html.parser'))

def process_homework(soup, week_number, homework_data):
    hw_page = soup.find('div', class_='hw')
    if not hw_page: return

    sec1_card = hw_page.find('h3', string=re.compile(r'Vocabulary Review')).parent
    if sec1_card:
        sec1_card['style'] = (sec1_card.get('style', '') or '') + "; background: var(--bg-pastel-green);"
        table = sec1_card.find('table')
        if table:
            for td in table.find_all('td'):
                existing_style = td.get('style', '')
                td['style'] = existing_style + "; padding: 12px 5px;"

    sec2_card = hw_page.find('h3', string=re.compile(r'Error Correction')).parent
    if sec2_card:
        sec2_card['style'] = (sec2_card.get('style', '') or '') + "; background: var(--bg-pastel-green);"
    
    grammar_data = homework_data.get('grammar_clinic', [])
    grammar_box = hw_page.find('div', style=lambda x: x and 'display:flex; flex-direction:column; gap:5px;' in x)
    if grammar_box:
        grammar_box.clear()
        for i, item in enumerate(grammar_data):
            error = item.get('error', '')
            div = soup.new_tag('div', attrs={'class': 'grammar-sent'})
            div.string = f"{i+1}. {error}"
            grammar_box.append(div)
            
    vocab_review = homework_data.get('vocab_review', [])
    vocab_table = hw_page.find('table', class_='vocab-table')
    if vocab_table:
        tbody = vocab_table.find('tbody')
        if tbody:
            tbody.clear()
            words_list = []
            synonyms_list = []
            for item in vocab_review:
                words_list.append(item.get('word', ''))
                synonyms_list.append({"option": item.get('option', ''), "synonym": item.get('synonym', '')})
            random.shuffle(synonyms_list)
            for i in range(len(words_list)):
                word = words_list[i]
                if i < len(synonyms_list):
                    option = synonyms_list[i]['option']
                    synonym = synonyms_list[i]['synonym']
                else: option, synonym = "?", "?"
                row_html = f"<td style='padding: 12px 5px;'>{i+1}. {word}</td><td style='border-bottom:1px solid #eee;'></td><td style='padding: 12px 5px;'>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {option}. {synonym}</td>"
                tr = soup.new_tag('tr')
                tr.append(BeautifulSoup(row_html, 'html.parser'))
                tbody.append(tr)

    sec3_card = hw_page.find('h3', string=re.compile(r'Writing Task')).parent
    if sec3_card:
        writing_task_text = homework_data.get('writing_task', '')
        sec3_card.clear()
        h3 = soup.new_tag('h3')
        h3.string = f"3. Writing Task: {writing_task_text} (10 minutes)"
        sec3_card.append(h3)
        instructions_html = """
        <div style="font-size:0.9em; line-height:1.6; padding:10px;">
        <strong>👉 On the next page:</strong><br>
        1. Write a first draft answer for the question above.<br>
        2. Scan your written answer into your AI and ask it to 'Minimally correct the grammar and vocabulary in this answer'.<br>
        3. Write the corrected answer your AI gave to you in the 'Polished Rewrite' box.
        </div>
        """
        sec3_card.append(BeautifulSoup(instructions_html, 'html.parser'))
        sec3_card['style'] = "flex-grow:1; border-left:5px solid var(--hw-accent); background: var(--bg-pastel-green); display:flex; flex-direction:column; justify-content:center;"

    sec4_card = hw_page.find('h3', string=re.compile(r'Recording Challenge')).parent
    if sec4_card:
        sec4_card.clear()
        sec4_html = """
        <h3 style="color:var(--hw-accent); margin:0 0 10px 0;">🎙️ 4. Recording Challenge (&lt;18 Mins)</h3>
        <div style="font-size:0.85em; line-height:1.5;">
        <strong>Part 1: AI Shadow Reading (19 mins)</strong> Use the AI Speaking Avatar. Choose British or American accent.<br>
        <strong>Task A (10 mins): Shadow read model answers:</strong><br>
        After Lesson 1: Use the AI APP to shadow read this week's Lesson 2 Part 3 model answers.<br>
        After Lesson 2: Use the AI app to shadow read next weeks lesson 1 part 2 model answers.<br>
        <strong>Task B (9 mins): Part 1:</strong> Use the AI app for Pronunciation Practice by reading the Tongue Twisters.<br>
        <strong>Part 2: Recording Task (18 mins):</strong> Using the AI app, record - 3 x Part 2 answers from this weeks lessons (6 mins) 6 x Part 3 answers from this weeks lessons (12 mins).
        </div>
        """
        sec4_card.append(BeautifulSoup(sec4_html, 'html.parser'))
        sec4_card['style'] = "flex-grow:1; border-left:5px solid var(--hw-accent); background: var(--bg-pastel-green); border-radius:12px; padding:10px; display:flex; flex-direction:column; justify-content:center;"

    answer_key = homework_data.get('answer_key', '')
    key_div = hw_page.find('div', style=lambda x: x and 'transform:rotate(180deg)' in x)
    if key_div:
        key_div.string = answer_key

def process_writing_page(soup):
    blank_page = soup.find('div', class_='blank-page')
    if not blank_page:
        blank_page = soup.new_tag('div', attrs={'class': 'page'})
        soup.body.append(blank_page)

    blank_page['class'] = ['page', 'hw']
    blank_page.clear()

    header_html = """
    <div class="header-bar">
    <span class="header-title">✍️ Writing Homework</span>
    <span class="week-tag">Draft & Polished Rewrite</span>
    </div>
    """
    blank_page.append(BeautifulSoup(header_html, 'html.parser'))

    title = soup.new_tag('h2')
    title.string = "Writing Homework"
    title['style'] = "text-align:center; margin-top:10px; color:var(--primary-color);"
    blank_page.append(title)

    content_html = """
    <div style="display:flex; flex-direction:column; gap:20px; flex-grow:1; height:100%; padding-bottom:10px;">
        <div class="card" style="flex:1; display:flex; flex-direction:column; background:var(--bg-pastel-green); border:1px solid #ccc;">
            <h3 style="margin:0 0 5px 0; color:#555;">Draft Written Homework</h3>
            <div class="lines" style="flex-grow:1; height:auto; width:100%;"></div>
        </div>
        <div class="card" style="flex:1; display:flex; flex-direction:column; background:var(--bg-pastel-green); border:1px solid #ccc;">
            <h3 style="margin:0 0 5px 0; color:#555;">Polished Rewrite</h3>
            <div class="lines" style="flex-grow:1; height:auto; width:100%;"></div>
        </div>
    </div>
    """
    blank_page.append(BeautifulSoup(content_html, 'html.parser'))

    return blank_page

def reorder_pages(soup, writing_page):
    writing_page.extract()
    soup.body.append(writing_page)

def process_layout_adjustments(soup):
    page6 = soup.find('div', id='page6')
    if page6:
        q1_cont = page6.find('div', id='p6-q1-cont')
        if q1_cont: q1_cont.decompose()
        q2 = page6.find('div', id='p6-q2')
        q3 = page6.find('div', id='p6-q3')
        if q2: q2['style'] = "flex:1; display:flex; flex-direction:column;"
        if q3: q3['style'] = "flex:1; display:flex; flex-direction:column;"

    l2_pages = soup.find_all('div', class_='l2')
    if l2_pages:
        page9 = l2_pages[-1]
        style_tag = soup.new_tag('style')
        style_tag.string = """
            @page { margin: 5mm; }
            .page { padding: 10mm; }
        """
        soup.head.append(style_tag)
        banner = page9.find('div', class_='header-bar')
        if banner:
            banner['style'] = "margin-top: 5mm; margin-bottom: 0px;"
        cards = page9.find_all('div', class_='card')
        for card in cards:
            card['style'] = (card.get('style', '') or '') + "; margin-bottom: 5px;"
        stack = page9.find('div', style=lambda x: x and 'display:flex' in x and 'gap:15px' in x)
        if stack:
            stack['style'] = stack['style'].replace('gap:15px', 'gap:5px').replace('padding: 0 15px 20px 15px', 'padding: 0;')

def populate_content(soup, week_curriculum, vocab_data, peer_data):
    process_cover(soup, week_curriculum)
    update_vocab_tables(soup, vocab_data)
    update_student_l1(soup, week_curriculum)
    update_student_l2(soup, week_curriculum, peer_data)

def process_cover(soup, week_data):
    if soup.title: soup.title.string = f"Week {week_data.get('week')} Master Lesson Pack"
    cover_week = soup.find('h1', class_='cover-week')
    if cover_week: cover_week.string = f"WEEK {week_data.get('week')}"
    cover_title = soup.find('h2', class_='cover-title-large')
    if cover_title: cover_title.string = week_data.get('theme', '')
    cover_sub = soup.find('div', class_='cover-subtitle')
    if cover_sub: cover_sub.string = week_data.get('topic', '')

def update_vocab_tables(soup, week_vocab):
    if not week_vocab: return
    l1_vocab = week_vocab.get('l1_vocab', [])
    l1_idioms = week_vocab.get('l1_idioms', [])
    vocab_tables = soup.find_all('table', class_='vocab-table')

    def fill_table(table, vocab, idioms):
        tbody = table.find('tbody')
        if not tbody: return
        tbody.clear()
        for i, item in enumerate(vocab):
            if i >= 7: break
            word = item.get('word', '').split('(')[0].strip()
            pos = item.get('word', '').split('(')[1].replace(')', '') if '(' in item.get('word', '') else ''
            row = f"<td><strong>{word}</strong> <span style='font-style:italic;font-size:0.9em;'>({pos})</span></td><td>{item.get('forms','')}</td><td><span class='vocab-cn'>{item.get('meaning','')}</span></td>"
            tbody.append(BeautifulSoup(f"<tr>{row}</tr>", 'html.parser'))
        tbody.append(BeautifulSoup("<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>", 'html.parser'))
        for i, item in enumerate(idioms):
            if i >= 3: break
            row1 = f"<td><strong>{item.get('idiom','')}</strong></td><td>({item.get('usage','')})</td><td><span class='vocab-cn'>{item.get('cn_idiom','')}</span></td>"
            tbody.append(BeautifulSoup(f"<tr>{row1}</tr>", 'html.parser'))
            if item.get('example_sentence'):
                tbody.append(BeautifulSoup(f"<tr class='vocab-example-row'><td colspan='3'>\"{item.get('example_sentence')}\"</td></tr>", 'html.parser'))

    if len(vocab_tables) >= 1: fill_table(vocab_tables[0], l1_vocab, l1_idioms)
    if len(vocab_tables) >= 2: fill_table(vocab_tables[1], week_vocab.get('l2_vocab', []), week_vocab.get('l2_idioms', []))

def format_bullet_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    raw_str = soup.decode_contents() if soup.name else str(soup)
    parts = re.split(r'<br\s*/?>', raw_str)
    
    formatted_parts = []
    main_text = ""
    bullet_lines = []
    
    if "You should say" in parts[0]:
        main_text = parts[0].strip()
        bullet_lines = parts[1:]
    else:
        found = False
        for i, p in enumerate(parts):
            if "You should say" in p:
                main_text = " ".join(parts[:i+1]).strip()
                bullet_lines = parts[i+1:]
                found = True
                break
        if not found: return html_content

    formatted_bullets = []
    for line in bullet_lines:
        clean_line = BeautifulSoup(line, 'html.parser').get_text().strip()
        if not clean_line: continue
        words = clean_line.split(' ', 1)
        if len(words) > 0:
            first = words[0]
            rest = " " + words[1] if len(words) > 1 else ""
            formatted_bullets.append(f"<strong>{first}</strong>{rest}")
    
    return f"{main_text} {', '.join(formatted_bullets)}"

def update_student_l1(soup, week_data):
    l1 = week_data.get('lesson_1_part_2', {})
    q1 = l1.get('q1', {})
    q2 = l1.get('q2', {})
    q3 = l1.get('q3', {})
    
    banner = soup.find('span', class_='header-title', string=re.compile(r'Part 2:'))
    if banner: banner.string = f"Part 2: {week_data.get('theme', 'General')}"

    cue = soup.find('div', style=lambda x: x and 'border-left:5px solid #fbc02d' in x)
    if cue:
        h3 = cue.find('h3')
        q1_html = q1.get('html', '')
        bs = BeautifulSoup(q1_html, 'html.parser')
        ps = bs.find_all('p')
        if len(ps) > 0:
            raw = ps[0].decode_contents()
            if "You should say" in raw:
                parts = raw.split("You should say")
                q_text = BeautifulSoup(parts[0], 'html.parser').get_text().strip()
                if h3: h3.string = f"📌 CUE CARD: {q_text}"
                bullets_div = cue.find('div', style=lambda x: x and 'color:#444' in x)
                if bullets_div:
                    bullets_div.clear()
                    clean_bullets = format_bullet_text(str(ps[0]))
                    bullets_div.append(BeautifulSoup(clean_bullets, 'html.parser'))

    q2_card = soup.find('h3', string=re.compile(r'Part 2: Q2'))
    if q2_card:
        prompt_div = q2_card.find_next_sibling('div')
        if prompt_div:
            q2_bs = BeautifulSoup(q2.get('html', ''), 'html.parser')
            p = q2_bs.find('p')
            if p:
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(format_bullet_text(str(p)), 'html.parser'))
    q3_card = soup.find('h3', string=re.compile(r'Part 2: Q3'))
    if q3_card:
        prompt_div = q3_card.find_next_sibling('div')
        if prompt_div:
            q3_bs = BeautifulSoup(q3.get('html', ''), 'html.parser')
            p = q3_bs.find('p')
            if p:
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(format_bullet_text(str(p)), 'html.parser'))

def update_student_l2(soup, week_data, peer_data):
    l2_data = week_data.get('lesson_2_part_3', {})
    week_peer = peer_data.get(week_data.get('week'), {}).get('lesson_2_part_3', {})
    
    # Update Header Tags
    tags = soup.find_all('span', class_='week-tag')
    for tag in tags:
        if "(Part 3)" in tag.text:
            tag.string = f"Week {week_data.get('week')} • Lesson 2 • {week_data.get('topic', '')} (Part 3)"
    
    # Locate Cards
    q1_card = soup.find('div', id='p5-q1')
    q2_card = soup.find('div', id='p6-q2')
    q3_card = soup.find('div', id='p6-q3')
    
    q4_card, q5_card, q6_card = None, None, None
    l2_pages = soup.find_all('div', class_='l2')
    if l2_pages:
        # Assuming the last L2 page is the Rapid Fire one
        rf_page = l2_pages[-1]
        cards = rf_page.find_all('div', class_='card')
        # Filter for question cards (checking h3 content or position)
        q_cards = [c for c in cards if c.find('h3') and "Q" in c.find('h3').text]
        if len(q_cards) >= 3:
            q4_card = q_cards[0]
            q5_card = q_cards[1]
            q6_card = q_cards[2]
            
    cards_map = {
        'q1': q1_card, 'q2': q2_card, 'q3': q3_card,
        'q4': q4_card, 'q5': q5_card, 'q6': q6_card
    }

    for q_key, card in cards_map.items():
        if not card: continue

        q_info = l2_data.get(q_key, {})
        html_content = q_info.get('html', '')
        if not html_content: continue

        # Parse Question and Model
        bs = BeautifulSoup(html_content, 'html.parser')
        ps = bs.find_all('p')
        if len(ps) >= 1:
            q_text = ps[0].get_text().strip().replace(f"{q_key.upper()}: ", "").replace(f"{q_key.upper()}:", "")
            # Update H3
            h3 = card.find('h3')
            if h3: h3.string = f"{q_key.upper()}: {q_text}"
            
        if len(ps) >= 2:
            model_html = "".join([str(x) for x in ps[1].contents]) # Inner HTML of 2nd p
            model_box = card.find('div', class_='model-box')
            if model_box:
                model_box.clear()
                model_box.append(BeautifulSoup(model_html, 'html.parser'))
                
        # Update Scaffold
        hints = q_info.get('ore_hints', [])
        scaffold_ul = card.find('ul', class_='scaffold-text')
        if scaffold_ul and hints:
            scaffold_ul.clear()
            for hint in hints:
                li = soup.new_tag('li')
                li.string = hint
                scaffold_ul.append(li)
                
        # Update Peer Check
        p_q_data = week_peer.get(q_key, {})
        b5_q = p_q_data.get('band_5_peer_question', '')
        b6_q = p_q_data.get('band_6_plus_peer_question', '')

        if b5_q:
            b5_div = card.find('div', string=re.compile(r'Band 5 Peer Check'))
            if not b5_div: # Try searching nested children
                b5_div = card.find('div', style=lambda x: x and 'color:#7f8c8d' in x) # heuristic
                # Better: search text recursively
                for div in card.find_all('div'):
                    if "Band 5 Peer Check" in div.text:
                        # Reconstruct the inner HTML
                        div.clear()
                        div.append(BeautifulSoup(f"📉 <strong>Band 5 Peer Check:</strong> Ask: '{b5_q}'", 'html.parser'))
                        break

        if b6_q:
            b6_div = card.find('div', string=re.compile(r'Band 6 Peer Check'))
            if not b6_div:
                 for div in card.find_all('div'):
                    if "Band 6 Peer Check" in div.text:
                        div.clear()
                        div.append(BeautifulSoup(f"📈 <strong>Band 6 Peer Check:</strong> Ask: '{b6_q}'", 'html.parser'))
                        break

def main():
    print("Generating all 40 lesson plans...")
    os.makedirs('lessons', exist_ok=True)
    
    curriculum, phrases, vocab, homework, peer_data = load_data()
    if not curriculum: return

    with open('Week_1_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        template_html = f.read()

    success_count = 0
    errors = []

    # Batch Processing
    total_weeks = 40
    batch_size = 5

    for start in range(1, total_weeks + 1, batch_size):
        end = min(start + batch_size, total_weeks + 1)
        print(f"Processing Batch: Weeks {start} to {end-1}")

        for week_num in range(start, end):
            try:
                week_data = next((w for w in curriculum if w['week'] == week_num), None)
                if not week_data:
                    print(f"Skipping Week {week_num}: No Data")
                    continue
                
                week_vocab = vocab.get(week_num)
                week_homework = homework.get(week_num)

                soup = BeautifulSoup(template_html, 'html.parser')

                populate_content(soup, week_data, week_vocab, peer_data)
                process_teacher_plan(soup, week_num, week_data, phrases)
                format_mind_maps(soup, week_num, phrases)
                process_homework(soup, week_num, week_homework)
                writing_page = process_writing_page(soup)
                process_layout_adjustments(soup)
                reorder_pages(soup, writing_page)

                with open(f'lessons/Week_{week_num}_Lesson_Plan.html', 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                print(f"Generated Week {week_num}")
                success_count += 1

            except Exception as e:
                error_msg = f"Failed Week {week_num}: {e}"
                print(error_msg)
                traceback.print_exc()
                with open('generation_errors.log', 'a', encoding='utf-8') as log_file:
                    log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {error_msg}\n")

        time.sleep(1) # Prevent system throttling

if __name__ == "__main__":
    main()
