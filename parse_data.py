import json
import re
import os
import time
import random
from bs4 import BeautifulSoup

def load_concatenated_json(filepath):
    """Loads concatenated JSON arrays from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
        return []
    
    data = []
    decoder = json.JSONDecoder()
    pos = 0
    length = len(content)
    
    while pos < length:
        # Skip whitespace, commas, and stray closing brackets
        while pos < length and (content[pos].isspace() or content[pos] in ',]'):
            pos += 1
            
        if pos == length:
            break
            
        try:
            # Decode directly from content at pos
            obj, end = decoder.raw_decode(content, idx=pos)
            
            if isinstance(obj, list):
                data.extend(obj)
            else:
                data.append(obj)
            pos = end
        except json.JSONDecodeError:
            # Try to recover by skipping one char (if garbage)
            pos += 1
            
    return data

def load_all_data():
    """Loads all data files once."""
    print("Loading all data files...")
    
    # Load Curriculum (Use the master merged file)
    try:
        with open('master Curiculum.json', 'r', encoding='utf-8') as f:
            curriculum_data = json.load(f)
    except FileNotFoundError:
        print("Error: master Curiculum.json not found.")
        curriculum_data = []
        
    vocab_data = load_concatenated_json('vocab_plan.json') # Changed to json ext based on file list
    homework_data = load_concatenated_json('homework_plan.json')
    
    # Load AI content
    try:
        with open('ai_dynamic_content.json', 'r', encoding='utf-8') as f:
            ai_data = json.load(f)
    except FileNotFoundError:
        ai_data = {}

    # Load Peer Check Questions
    try:
        with open('peer_check_questions.json', 'r', encoding='utf-8') as f:
            peer_data = json.load(f)
    except FileNotFoundError:
        print("Warning: peer_check_questions.json not found.")
        peer_data = []

    # Load Phrase Data
    try:
        with open('noun_or_verb_phrases_for_weekly_topics.json', 'r', encoding='utf-8') as f:
            phrase_data = json.load(f)
    except FileNotFoundError:
        print("Warning: noun_or_verb_phrases_for_weekly_topics.json not found.")
        phrase_data = []

    # Load Teacher Dynamic Content
    try:
        with open('teacher_dynamic_content.json', 'r', encoding='utf-8') as f:
            teacher_data = json.load(f)
    except FileNotFoundError:
        print("Warning: teacher_dynamic_content.json not found.")
        teacher_data = {}
        
    return curriculum_data, vocab_data, homework_data, ai_data, teacher_data, peer_data, phrase_data

def get_week_data(week_number, curriculum_data, vocab_data, homework_data):
    """Extracts data for the specific week."""
    week_curriculum = next((item for item in curriculum_data if item.get("week") == week_number), None)
    week_vocab = next((item for item in vocab_data if item.get("week") == week_number), None)
    week_homework = next((item for item in homework_data if item.get("week") == week_number), None)
    return week_curriculum, week_vocab, week_homework

def process_cover_page(soup, week_number, week_data):
    """Updates the cover page with week number and theme."""
    # Update Title Tag
    if soup.title:
        soup.title.string = f"Week {week_number} Master Lesson Pack"

    # INJECT CSS OVERRIDES
    css_overrides = """
    /* OVERRIDES FOR COVER PAGE (Page 1) */
    @page:first {
        background-image: url('https://res.cloudinary.com/daujjfaqg/image/upload/v1771567490/Textbook_Cover_usinxj.jpg');
        background-size: cover;
        background-position: center;
        margin: 0;
    }
    .cover-page {
        background: url('https://res.cloudinary.com/daujjfaqg/image/upload/v1771567490/Textbook_Cover_usinxj.jpg') no-repeat center center !important; 
        background-size: cover !important;
        position: relative;
        width: 210mm; /* A4 Width */
        height: 296mm; /* A4 Height */
        color: black; 
        padding: 0 !important;
        display: flex;
        flex-direction: column;
        justify-content: flex-end; /* Text at bottom */
        align-items: flex-end; /* Text at right */
        text-align: right;
        padding-bottom: 2cm !important; /* Spacing from bottom */
    }
    .cover-content {
        margin-right: 2cm;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0px; /* Compact lines */
    }
    .cover-title-large {
        font-size: 6em;
        font-weight: 900;
        line-height: 0.9;
        color: black;
        -webkit-text-stroke: 2px white; /* Thin white border */
        text-shadow: 2px 2px 0 #fff;
        margin: 0;
        text-transform: uppercase;
    }
    .cover-subtitle {
        font-size: 1.8em;
        font-weight: 700;
        color: black;
        background: transparent; /* Changed from white to transparent to show image */
        padding: 5px 0; /* Adjusted padding */
        margin: 10px 0 0 0;
        text-transform: uppercase;
        letter-spacing: 2px;
        display: inline-block;
        -webkit-text-stroke: 1px white; /* Thin white border */
        text-shadow: 1px 1px 0 #fff;
        box-shadow: none; /* Removed shadow box */
    }
    .cover-top-label {
        font-size: 1.5em;
        font-weight: 800;
        color: black;
        text-transform: uppercase;
        letter-spacing: 4px;
        margin-bottom: 0;
        -webkit-text-stroke: 1px white; /* Thin white border */
        text-shadow: 1px 1px 0 #fff;
    }
    .cover-week {
        font-size: 5em;
        font-weight: 900;
        color: black;
        margin: 0;
        line-height: 1;
        -webkit-text-stroke: 2px white; /* Thin white border */
        text-shadow: 2px 2px 0 #fff;
    }
    .cover-footer {
        position: absolute;
        bottom: 1cm;
        right: 2cm;
        font-size: 0.8em;
        color: black;
        font-weight: 600;
        -webkit-text-stroke: 0.5px white; /* Very thin border */
        text-shadow: 0.5px 0.5px 0 #fff;
        opacity: 1;
    }
    /* Hide default elements we don't need */
    .cover-box { display: none; } 
    """
    
    # Clean up ANY existing cover overrides (duplicates or old versions)
    if soup.head:
        for tag in soup.head.find_all('style'):
            if tag.string and "OVERRIDES FOR COVER PAGE" in tag.string:
                tag.decompose()
    
    # Add fresh style tag
    style_tag = soup.new_tag('style', id='cover-overrides')
    style_tag.string = css_overrides
    if soup.head:
        soup.head.append(style_tag)

    # REBUILD COVER PAGE HTML
    cover_div = soup.find('div', class_='cover-page')
    if cover_div:
        cover_div.clear()
        
        # Container
        content_div = soup.new_tag('div', attrs={'class': 'cover-content'})
        
        # 1. Top Label
        top_label = soup.new_tag('div', attrs={'class': 'cover-top-label'})
        top_label.string = "IELTS SPEAKING MASTERCLASS"
        content_div.append(top_label)
        
        # 2. Week Number
        week_h1 = soup.new_tag('h1', attrs={'class': 'cover-week'})
        week_h1.string = f"WEEK {week_number}"
        content_div.append(week_h1)
        
        # 3. Large Title (Theme)
        theme = week_data.get('theme', 'General')
        title_h2 = soup.new_tag('h2', attrs={'class': 'cover-title-large'})
        title_h2.string = theme
        content_div.append(title_h2)
        
        # 4. Subtitle (Topic)
        topic = week_data.get('topic', 'Discussion')
        sub_div = soup.new_tag('div', attrs={'class': 'cover-subtitle'})
        sub_div.string = topic
        content_div.append(sub_div)
        
        cover_div.append(content_div)
        
        # Footer
        footer_div = soup.new_tag('div', attrs={'class': 'cover-footer'})
        footer_div.string = "© Jinhua New Oriental Academy English Department Curriculum"
        cover_div.append(footer_div)

def process_teacher_plan(soup, week_number, week_data, teacher_content, phrase_data):
    """Updates Teacher Lesson Plan pages using pre-generated dynamic content."""
    topic = week_data.get('topic', '')
    
    # Get grammar phrase for this week
    target_phrase = topic  # Default fallback
    week_phrase_data = next((item for item in phrase_data if item.get("week") == week_number), None)
    if week_phrase_data:
        target_phrase = week_phrase_data.get('grammar_target_phrase', topic)

    # Update Header Bars (Teacher L1, Student L1, Student Practice, Teacher L2, Student L2, Deep Dive, Rapid Fire)
    headers = soup.find_all('span', class_='week-tag')
    for header in headers:
        if 'Lesson 1' in header.string:
            header.string = f"Week {week_number} • Lesson 1 • {topic}"
        elif 'Lesson 2' in header.string:
            header.string = f"Week {week_number} • Lesson 2 • {topic} (Part 3)"
        elif 'Self-Study' in header.string:
            header.string = f"Week {week_number} • Self-Study"

    # --- Lesson 1 Teacher Plan ---
    l1_data = teacher_content.get('lesson_1', {})
    l1_page = soup.find('div', class_='l1')
    if l1_page:
        # Learning Objectives
        lo_card = l1_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                ul.clear()
                # Update Grammar Objective dynamically
                objs = l1_data.get('learning_objectives', [])
                new_objs = []
                for obj in objs:
                    if "Grammar:" in obj:
                        new_objs.append(f"<strong>Grammar:</strong> Use narrative tenses or relevant grammar for {target_phrase}.")
                    else:
                        new_objs.append(obj)

                for obj_html in new_objs:
                    ul.append(BeautifulSoup(f"<li>{obj_html}</li>", 'html.parser'))
        
        # Criteria
        criteria_h2 = l1_page.find('h2', string=re.compile(r'Criteria'))
        if criteria_h2:
            criteria_div = criteria_h2.find_next_sibling('div')
            if criteria_div:
                criteria_div.clear()
                criteria_div.append(BeautifulSoup(l1_data.get('success_criteria', ''), 'html.parser'))

        # Differentiation
        diff_card = l1_page.find('h2', string=re.compile(r'Differentiation')).parent
        if diff_card:
            b5_data = l1_data.get('differentiation', {}).get('band_5', {})
            b6_data = l1_data.get('differentiation', {}).get('band_6', {})

            # Band 5 Box
            band5_div = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if band5_div:
                band5_div.clear()
                band5_div.append(BeautifulSoup(f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: '{b5_data.get('starter', '')}'<br>• Peer Check: Specific personal questions", 'html.parser'))

            # Band 6 Box
            band6_div = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if band6_div:
                band6_div.clear()
                band6_div.append(BeautifulSoup(f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: {b6_data.get('transitions', '')}<br>• Peer Check: {b6_data.get('peer_check', '')}", 'html.parser'))

        # Lead-in (Table)
        l1_table = l1_page.find('table', class_='lp-table')
        if l1_table:
            rows = l1_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 1:
                    cell_text = cells[1].get_text()

                    if "Lead-in" in cell_text:
                        lead_in_info = l1_data.get('lead_in', {})
                        new_html = f"<strong>Lead-in:</strong> Click Bilibili icon on Student Handout (Banner) to show 5-min warmup video (Search: {lead_in_info.get('search_term')}). Ask: '{lead_in_info.get('question')}'"
                        cells[1].clear()
                        cells[1].append(BeautifulSoup(new_html, 'html.parser'))

                    elif "Input" in cell_text:
                        # Extract first vocab word from learning objectives or data
                        # We used a sample word in LOs, let's grab it again or use a placeholder
                        target_word = "Target Word"
                        # Parse from existing LOs if available, or just rely on vocab injection logic?
                        # Better: access the raw vocab data passed to this function?
                        # Wait, process_teacher_plan doesn't receive vocab_data directly, only week_teacher_content.
                        # But week_teacher_content["lesson_1"]["learning_objectives"][1] has the word: "Use 7 target words (e.g., <em>Diligent</em>)..."

                        try:
                            lo_html = l1_data.get('learning_objectives', [])[1]
                            match = re.search(r'<em>(.*?)</em>', lo_html)
                            if match:
                                target_word = match.group(1)
                        except:
                            pass

                        content = cells[1].decode_contents()
                        # Replace 'Highlight "Reliable"'
                        new_content = re.sub(r'Highlight "(.*?)"', f'Highlight "{target_word}"', content)
                        cells[1].clear()
                        cells[1].append(BeautifulSoup(new_content, 'html.parser'))

                    # Vocab Drill Update (Static fix)
                    elif "Vocab Drill" in cell_text:
                        content = cells[1].decode_contents()
                        if '"Thick and thin"' in content:
                            new_content = content.replace('"Thick and thin"', '"idioms"')
                            cells[1].clear()
                            cells[1].append(BeautifulSoup(new_content, 'html.parser'))

    # --- Lesson 2 Teacher Plan ---
    l2_data = teacher_content.get('lesson_2', {})
    l2_pages = soup.find_all('div', class_='l2')
    if l2_pages:
        l2_teacher_page = l2_pages[0] # Assuming first is Teacher Plan

        # Learning Objectives
        lo_card = l2_teacher_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                ul.clear()
                # Update Speaking Objective dynamically
                objs = l2_data.get('learning_objectives', [])
                new_objs = []
                for obj in objs:
                    if "Speaking:" in obj:
                        new_objs.append(f"<strong>Speaking:</strong> Discuss abstract ideas about {target_phrase}.")
                    else:
                        new_objs.append(obj)

                for obj_html in new_objs:
                    ul.append(BeautifulSoup(f"<li>{obj_html}</li>", 'html.parser'))

        # Criteria
        criteria_h2 = l2_teacher_page.find('h2', string=re.compile(r'Criteria'))
        if criteria_h2:
            criteria_div = criteria_h2.find_next_sibling('div')
            if criteria_div:
                criteria_div.clear()
                criteria_div.append(BeautifulSoup(l2_data.get('success_criteria', ''), 'html.parser'))
                
        # Differentiation
        diff_card = l2_teacher_page.find('h2', string=re.compile(r'Differentiation')).parent
        if diff_card:
            b5_data = l2_data.get('differentiation', {}).get('band_5', {})
            b6_data = l2_data.get('differentiation', {}).get('band_6', {})
            
            # Band 5 Box
            band5_div = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if band5_div:
                band5_div.clear()
                band5_div.append(BeautifulSoup(f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: '{b5_data.get('starter', '')}'<br>• Peer Check: Specific personal questions", 'html.parser'))

            # Band 6 Box
            band6_div = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if band6_div:
                band6_div.clear()
                band6_div.append(BeautifulSoup(f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: {b6_data.get('transitions', '')}<br>• Peer Check: {b6_data.get('peer_check', '')}", 'html.parser'))

    # Bilibili Link (Student Handouts)
    l1_link = l1_data.get('lead_in', {}).get('search_term', 'IELTS Speaking')
    l1_url = f"https://search.bilibili.com/all?keyword={l1_link.replace(' ', '%20')}"

    # Assuming same link for L2 or specific if needed. Template usually shares one link format.
    # We will update all buttons.
    bili_btns = soup.find_all('a', class_='bili-btn')
    for btn in bili_btns:
        btn['href'] = l1_url # Using L1 search term for simplicity as requested "IELTS <Topic> Speaking"

def process_vocabulary(soup, week_number, vocab_data):
    """Injects vocabulary into L1 and L2 tables."""
    # L1 Vocabulary
    l1_vocab_list = vocab_data.get('l1_vocab', [])
    l1_idioms_list = vocab_data.get('l1_idioms', [])
    
    # Find L1 Vocab Table (Page 2)
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
                
                word_raw = word_item.get('word', '')
                word = word_raw.split('(')[0].strip()

                # Try to get POS from the word field if present e.g. "Diligent (Adj)"
                pos = word_raw.split('(')[1].replace(')', '') if '(' in word_raw else ''

                forms = word_item.get('forms', word_item.get('Word Forms', ''))
                meaning = word_item.get('meaning', '')
                recycled = word_item.get('recycled', False)
                
                # If POS missing, infer from 'forms' if it's a simple label
                if not pos:
                    forms_lower = forms.lower()
                    if forms_lower == "adjective" or forms_lower == "adj":
                        pos = "Adj"
                    elif forms_lower == "noun" or forms_lower == "n":
                        pos = "N"
                    elif forms_lower == "verb" or forms_lower == "v":
                        pos = "V"
                    elif forms_lower == "adverb" or forms_lower == "adv":
                        pos = "Adv"
                    elif "noun phrase" in forms_lower:
                        pos = "Noun Phrase"

                row_html = f"<td><strong>{word}</strong>"
                if pos:
                    row_html += f" <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>({pos})</span>"

                if recycled and week_number > 1:
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
                meaning = idiom_item.get('cn_idiom', '')
                example = idiom_item.get('example_sentence', '')
                
                # Row 1: Idiom Info
                row1_html = f"<td><strong>{idiom}</strong></td><td>({usage})</td><td><span class='vocab-cn'>{meaning}</span></td>"
                tr1 = soup.new_tag('tr')
                tr1.append(BeautifulSoup(row1_html, 'html.parser'))
                tbody.append(tr1)
                
                # Row 2: Example (if exists)
                if example:
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
            
            for word_item in l2_vocab_list:
                word_raw = word_item.get('word', '')
                word = word_raw.split('(')[0].strip()
                pos = word_raw.split('(')[1].replace(')', '') if '(' in word_raw else ''

                forms = word_item.get('forms', word_item.get('Word Forms', ''))
                meaning = word_item.get('meaning', '')
                
                if not pos:
                    forms_lower = forms.lower()
                    if forms_lower == "adjective" or forms_lower == "adj":
                        pos = "Adj"
                    elif forms_lower == "noun" or forms_lower == "n":
                        pos = "N"
                    elif forms_lower == "verb" or forms_lower == "v":
                        pos = "V"
                    elif forms_lower == "adverb" or forms_lower == "adv":
                        pos = "Adv"
                    elif "noun phrase" in forms_lower:
                        pos = "Noun Phrase"

                row_html = f"<td><strong>{word}</strong>"
                if pos:
                    row_html += f" <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>({pos})</span>"
                row_html += f"</td><td>{forms}</td><td><span class='vocab-cn'>{meaning}</span></td>"
                
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
                
                if example:
                    row2_html = f"<td colspan='3'>\"{example}\"</td>"
                    tr2 = soup.new_tag('tr', attrs={'class': 'vocab-example-row'})
                    tr2.append(BeautifulSoup(row2_html, 'html.parser'))
                    tbody.append(tr2)

def format_bullet_text(html_content):
    """Formats 'You should say:' bullets: bold first word, inline, comma separated."""
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
        # Sometimes "You should say" is its own line
        found = False
        for i, p in enumerate(parts):
            if "You should say" in p:
                main_text = " ".join(parts[:i+1]).strip()
                bullet_lines = parts[i+1:]
                found = True
                break
        if not found:
            return html_content

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

def process_student_l1(soup, week_data):
    """Updates Student Lesson 1 (Page 2) content."""
    l1_data = week_data.get('lesson_1_part_2', {})
    q1_data = l1_data.get('q1', {})
    
    # Update Banner Title (Part 2: Theme)
    banner_title = soup.find('span', class_='header-title', string=re.compile(r'Part 2:'))
    if banner_title:
        theme = week_data.get('theme', 'General')
        banner_title.string = f"Part 2: {theme}"

    # Update Cue Card
    cue_card_div = soup.find('div', style=lambda x: x and 'border-left:5px solid #fbc02d' in x)
    if cue_card_div:
        h3 = cue_card_div.find('h3')
        q1_html = q1_data.get('html', '')
        q1_soup = BeautifulSoup(q1_html, 'html.parser')
        prompt_p = q1_soup.find('p')
        
        if prompt_p:
            p_content = prompt_p.decode_contents()
            
            if "You should say:" in p_content:
                parts = p_content.split("You should say:")
                question_text = BeautifulSoup(parts[0], 'html.parser').get_text().strip()
                bullets_raw = parts[1] 
                
                if h3:
                    h3.string = f"📌 CUE CARD: {question_text}"
                
                bullet_lines = re.split(r'<br\s*/?>', bullets_raw)
                fmt_bullets = []
                for line in bullet_lines:
                    txt = BeautifulSoup(line, 'html.parser').get_text().strip()
                    if not txt: continue
                    words = txt.split(' ', 1)
                    if len(words) > 0:
                        first = words[0]
                        rest = " " + words[1] if len(words) > 1 else ""
                        fmt_bullets.append(f"<strong>{first}</strong>{rest}")
                
                final_bullets_html = "You should say: " + ", ".join(fmt_bullets)
                
                bullets_div = cue_card_div.find('div', style=lambda x: x and 'color:#444' in x)
                if bullets_div:
                    bullets_div.clear()
                    bullets_div.append(BeautifulSoup(final_bullets_html, 'html.parser'))

    # Update Model Answer
    model_div = soup.find('div', class_='model-box')
    if model_div:
        # Get answer part (usually second paragraph)
        answer_p = q1_soup.find_all('p')[1] if len(q1_soup.find_all('p')) > 1 else None
        if answer_p:
            new_content = str(answer_p).replace('<p>', '').replace('</p>', '')
            new_content = new_content.replace('highlight-yellow', 'highlight-3clause')
            model_div.clear()
            model_div.append(BeautifulSoup(new_content, 'html.parser'))

def extract_keyword(text):
    """Extracts a central keyword from the question text."""
    # Clean up text first
    text = BeautifulSoup(text, 'html.parser').get_text().strip()
    # Remove "You should say..." and everything after
    if "You should say" in text:
        text = text.split("You should say")[0]
    elif "." in text:
        text = text.split(".")[0]
    text = text.strip()

    stopwords = ['a', 'an', 'the', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by',
                 'you', 'your', 'my', 'his', 'her', 'their', 'our', 'it', 'its',
                 'who', 'that', 'which', 'where', 'when',
                 'time', 'occasion', 'situation', 'describe', 'had']

    # Pattern 1: Time/Event
    # e.g. "Describe a time when you gave advice" -> "GAVE ADVICE"
    # Matches "Describe a time you..." as well (optional when/where)
    match_time = re.search(r'Describe (?:a|an) (?:time|occasion|situation)(?:\s+(?:when|where|that))?(?:\s+(?:you|it|he|she))?\s+([A-Za-z\s]+)', text, re.IGNORECASE)
    if match_time:
        phrase = match_time.group(1).strip()
        words = [w for w in phrase.split() if w.lower() not in stopwords]
        if words:
            return "<br>".join(words[:2]).upper()

    # Pattern 2: Standard Noun "Describe a/an [Noun]..."
    match_noun = re.search(r'Describe (?:a|an|the) ([A-Za-z\s]+?)(?:\s+(?:who|that|which|where|whose)[\s\.]|$)', text, re.IGNORECASE)
    if match_noun:
        phrase = match_noun.group(1).strip()
        words = [w for w in phrase.split() if w.lower() not in stopwords]
        if words:
            return "<br>".join(words[:2]).upper()

    # Fallback
    match_simple = re.search(r'Describe ([A-Za-z\s]+)', text, re.IGNORECASE)
    if match_simple:
        phrase = match_simple.group(1).strip()
        words = [w for w in phrase.split() if w.lower() not in stopwords]
        if words:
            return "<br>".join(words[:2]).upper()

    return "TOPIC"

def format_mind_maps(soup, week_data, ai_content):
    """Updates Mind Maps on Page 3."""
    l1_data = week_data.get('lesson_1_part_2', {})
    q1 = l1_data.get('q1', {})
    q2 = l1_data.get('q2', {})
    q3 = l1_data.get('q3', {})
    
    # 1. Main Brainstorming Map
    q1_html = q1.get('html', '')
    q1_soup = BeautifulSoup(q1_html, 'html.parser')

    # Extract keyword from Q1 if possible, or use Topic
    central_text = extract_keyword(q1_soup.get_text())
    
    # Update Center
    spider_centers = soup.find_all('div', class_='spider-center')
    if len(spider_centers) > 0:
        spider_centers[0].clear()
        spider_centers[0].append(BeautifulSoup(central_text, 'html.parser'))
        
    # Update Q1 Prompt
    l1_practice_page = soup.find_all('div', class_='l1')[2]
    if l1_practice_page:
        brainstorm_card = l1_practice_page.find('div', class_='card')
        if brainstorm_card:
            prompt_div = brainstorm_card.find('div', style=lambda x: x and 'color:#444' in x)
            if prompt_div:
                q1_prompt_p = q1_soup.find('p')
                if q1_prompt_p:
                    fmt_html = format_bullet_text(q1_prompt_p.decode_contents())
                    prompt_div.clear()
                    prompt_div.append(BeautifulSoup(fmt_html, 'html.parser'))

    # Update Legs
    hints = q1.get('spider_diagram_hints', ["", "", "", ""])
    spider_legs = soup.find_all('div', class_='spider-legs')
    if len(spider_legs) > 0:
        legs = spider_legs[0].find_all('div', class_='spider-leg')
        for i, leg in enumerate(legs):
            if i < len(hints):
                # We need to preserve the bolding structure if possible, or just replace content
                # Template: <strong>1. WHO:</strong><br/><span style="color:#777;">Older sister</span>
                # We update the span.
                span = leg.find('span')
                if span:
                    span.string = hints[i]

    # 2. Topic A (Q2) -> Part 2: Q2
    topic_a_card = soup.find('h3', string=re.compile(r'Part 2: Q2'))
    if topic_a_card:
        q2_html = q2.get('html', '')
        q2_soup = BeautifulSoup(q2_html, 'html.parser')
        q2_text = q2_soup.get_text()
        
        prompt_div = topic_a_card.find_next_sibling('div')
        if prompt_div:
            q2_prompt_p = q2_soup.find('p')
            if q2_prompt_p:
                fmt_html = format_bullet_text(q2_prompt_p.decode_contents())
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(fmt_html, 'html.parser'))
            
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
                # These legs are simpler: Text<div class="lines"></div>
                if i < len(q2_hints):
                    leg.contents[0].replace_with(q2_hints[i])

    # 3. Topic B (Q3) -> Part 2: Q3
    topic_b_card = soup.find('h3', string=re.compile(r'Part 2: Q3'))
    if topic_b_card:
        q3_html = q3.get('html', '')
        q3_soup = BeautifulSoup(q3_html, 'html.parser')
        q3_text = q3_soup.get_text()
        
        prompt_div = topic_b_card.find_next_sibling('div')
        if prompt_div:
            q3_prompt_p = q3_soup.find('p')
            if q3_prompt_p:
                fmt_html = format_bullet_text(q3_prompt_p.decode_contents())
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(fmt_html, 'html.parser'))
            
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
                    leg.contents[0].replace_with(q3_hints[i])

def process_student_l2(soup, week_data, ai_content, week_peer_data):
    """Updates Student Lesson 2 (Part 3) Q1-Q6."""
    l2_data = week_data.get('lesson_2_part_3', {})
    
    # week_peer_data is a dictionary for the current week, e.g. {"lesson_2_part_3": {"q1": { ... }, ...}}
    peer_questions = week_peer_data.get('lesson_2_part_3', {}) if week_peer_data else {}

    def update_q(q_id, q_key, container_id=None, container_elem=None):
        data = l2_data.get(q_key, {})
        html = data.get('html', '')
        soup_frag = BeautifulSoup(html, 'html.parser')
        
        q_tag = soup_frag.find('strong')
        q_text = q_tag.get_text() if q_tag else ""
        
        ps = soup_frag.find_all('p')
        answer_html = ""
        if len(ps) > 1:
            answer_html = ''.join(map(str, ps[1].contents))
            answer_html = answer_html.replace('highlight-yellow', 'highlight-3clause')
        
        if container_id:
            card = soup.find('div', id=container_id)
        else:
            card = container_elem
            
        if card:
            h3 = card.find('h3')
            if h3: h3.string = q_text
            
            mbox = card.find('div', class_='model-box')
            if mbox:
                mbox.clear()
                if answer_html:
                    mbox.append(BeautifulSoup(answer_html, 'html.parser'))
                
            hints = data.get('ore_hints', [])
            scaffold = card.find('ul', class_='scaffold-text')
            if scaffold:
                scaffold.clear()
                for hint in hints:
                    li = soup.new_tag('li')
                    li.string = hint
                    scaffold.append(li)

            # Inject Peer Check Questions
            # Look for the peer check section at the bottom of the writing area
            # In template it is: <div style="margin-top:1px; ..."> <div>...</div> </div>

            # Get specific questions for this Q
            q_peer_data = peer_questions.get(q_key, {})
            band_5_q = q_peer_data.get('band_5_peer_question', 'Why?')
            band_6_q = q_peer_data.get('band_6_plus_peer_question', 'Can you expand?')

            # Find the peer check container. It usually follows the writing lines.
            # In the template, it's inside the writing box container.
            # We can find it by looking for "Band 5 Peer Check" text

            # Locate writing box
            writing_box = None
            if container_id:
                # For Q1, Q2, Q3 (if on page 6)
                writing_box = card.find('div', style=lambda x: x and 'border:1px solid #ddd' in x)
                # Q3 on page 6 has dashed border style sometimes or similar structure
                if not writing_box:
                     writing_box = card.find('div', style=lambda x: x and 'border-top:1px dashed' in x)
            else:
                # For Q4-Q6 compact cards
                writing_box = card.find('div', style=lambda x: x and 'border-top:1px dashed' in x)

            if writing_box:
                # Find the container for peer checks
                peer_div = writing_box.find('div', style=lambda x: x and 'border-top:1px dotted' in x)
                if peer_div:
                    peer_div.clear()
                    # Rebuild HTML
                    html_content = f"""
                    <div style="font-size:0.7em; color:#7f8c8d; margin-bottom:0;">📉 <strong>Band 5 Peer Check:</strong> Ask: '{band_5_q}'</div>
                    <div style="font-size:0.7em; color:#7f8c8d; margin-bottom:0;">📈 <strong>Band 6 Peer Check:</strong> Ask: '{band_6_q}'</div>
                    """
                    peer_div.append(BeautifulSoup(html_content, 'html.parser'))

    # Q1 (Page 5)
    update_q(1, 'q1', container_id='p5-q1')
    # Q2 (Page 6)
    update_q(2, 'q2', container_id='p6-q2')
    # Q3 (Page 6)
    update_q(3, 'q3', container_id='p6-q3')
    
    # Q4, Q5, Q6 (Page 7)
    l2_pages = soup.find_all('div', class_='l2')
    if len(l2_pages) >= 4:
        page7 = l2_pages[3]
        compact_cards = page7.find_all('div', class_='card compact')
        if len(compact_cards) >= 3:
            update_q(4, 'q4', container_elem=compact_cards[0])
            update_q(5, 'q5', container_elem=compact_cards[1])
            update_q(6, 'q6', container_elem=compact_cards[2])

def process_homework(soup, week_number, homework_data):
    """Updates Homework page."""
    
    # 1. Vocab Review
    vocab_review = homework_data.get('vocab_review', [])
    hw_page = soup.find('div', class_='page hw')
    vocab_table = hw_page.find('table', class_='vocab-table')
    if vocab_table:
        tbody = vocab_table.find('tbody')
        if tbody:
            tbody.clear()

            # SHUFFLE LOGIC
            # Separate Words from Synonyms
            words_list = []
            synonyms_list = []

            for item in vocab_review:
                words_list.append(item.get('word', ''))
                synonyms_list.append({
                    "option": item.get('option', ''),
                    "synonym": item.get('synonym', '')
                })

            # Shuffle the Synonyms independently
            random.shuffle(synonyms_list)

            # Combine them back for display
            for i in range(len(words_list)):
                word = words_list[i]

                # If we have fewer synonyms than words (shouldn't happen), handle gracefully
                if i < len(synonyms_list):
                    option = synonyms_list[i]['option']
                    synonym = synonyms_list[i]['synonym']
                else:
                    option = "?"
                    synonym = "?"
                
                # Added padding style to TD for increased spacing
                row_html = f"<td style='padding: 10px 5px;'>{i+1}. {word}</td><td style='border-bottom:1px solid #eee;'></td><td style='padding: 10px 5px;'>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {option}. {synonym}</td>"
                tr = soup.new_tag('tr')
                tr.append(BeautifulSoup(row_html, 'html.parser'))
                tbody.append(tr)

    # 2. Grammar Clinic
    grammar_data = homework_data.get('grammar_clinic', [])
    grammar_box = hw_page.find('div', style=lambda x: x and 'display:flex; flex-direction:column; gap:5px;' in x)
    if grammar_box:
        grammar_box.clear()
        for i, item in enumerate(grammar_data):
            error = item.get('error', '')
            div = soup.new_tag('div', attrs={'class': 'grammar-sent'})
            div.string = f"{i+1}. {error}"
            grammar_box.append(div)

    # 3. Writing Task
    writing_task = homework_data.get('writing_task', '')
    writing_card = hw_page.find('h3', string=re.compile(r'Writing Task'))
    if writing_card:
        writing_card.string = f"3. Writing Task: {writing_task} (10 minutes)"

    # 5. Answer Key
    answer_key = homework_data.get('answer_key', '')
    key_div = hw_page.find('div', style=lambda x: x and 'transform:rotate(180deg)' in x)
    if key_div:
        key_div.string = answer_key

def main():
    print("Generating all 40 lesson plans...")
    os.makedirs('lessons', exist_ok=True)
    
    # Load all data
    curriculum_data, vocab_data, homework_data, ai_data, teacher_data, peer_data, phrase_data = load_all_data()
    
    if not curriculum_data:
        print("Failed to load curriculum data. Exiting.")
        return

    # Load Template (Week_1_Lesson_Plan.html)
    with open('Week_1_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        template_html = f.read()

    success_count = 0
    errors = []

    for week_number in range(1, 41):
        try:
            print(f"--- Generating Week {week_number} ---")
            
            # Get data
            week_curriculum, week_vocab, week_homework = get_week_data(week_number, curriculum_data, vocab_data, homework_data)
            week_teacher_content = teacher_data.get(str(week_number), {})
            
            # Get Peer Data for this week
            week_peer_data = next((item for item in peer_data if item.get("week") == week_number), None)

            if not week_curriculum:
                print(f"Skipping Week {week_number}: No curriculum data found.")
                errors.append(week_number)
                continue

            # Reset soup
            soup = BeautifulSoup(template_html, 'html.parser')
            
            # AI Content (Legacy/Fallback)
            ai_content = ai_data.get(str(week_number), {})
            
            process_cover_page(soup, week_number, week_curriculum)
            process_teacher_plan(soup, week_number, week_curriculum, week_teacher_content, phrase_data)
            process_vocabulary(soup, week_number, week_vocab)
            process_student_l1(soup, week_curriculum)
            format_mind_maps(soup, week_curriculum, ai_content)
            process_student_l2(soup, week_curriculum, ai_content, week_peer_data)
            process_homework(soup, week_number, week_homework)
            
            # Save
            output_filename = f'lessons/Week_{week_number}_Lesson_Plan.html'
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(str(soup))
                
            print(f"Successfully generated {output_filename}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ Error generating Week {week_number}: {e}")
            import traceback
            traceback.print_exc()
            errors.append(week_number)

    print("\n" + "="*30)
    print(f"Build Complete.")
    print(f"Success: {success_count}/40")
    if errors:
        print(f"Failed Weeks: {errors}")
    else:
        print("🎉 All weeks generated successfully!")
    print("="*30)

if __name__ == "__main__":
    main()