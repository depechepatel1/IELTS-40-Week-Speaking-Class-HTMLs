import json
import re
import os
import time
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
    
    # Load Curriculum (Standard JSON now)
    with open('curriculum.json', 'r', encoding='utf-8') as f:
        curriculum_data = json.load(f)
        
    vocab_data = load_concatenated_json('vocab_plan.txt')
    homework_data = load_concatenated_json('homework_plan.json')
    
    # Load AI content
    try:
        with open('ai_dynamic_content.json', 'r', encoding='utf-8') as f:
            ai_data = json.load(f)
    except FileNotFoundError:
        ai_data = {}
        
    return curriculum_data, vocab_data, homework_data, ai_data

def get_week_data(week_number, curriculum_data, vocab_data, homework_data):
    """Extracts data for the specific week."""
    week_curriculum = next((item for item in curriculum_data if item.get("week") == week_number), None)
    week_vocab = next((item for item in vocab_data if item.get("week") == week_number), None)
    week_homework = next((item for item in homework_data if item.get("week") == week_number), None)
    return week_curriculum, week_vocab, week_homework

# ... [Include all processing functions from parse_data.py] ...
# To ensure all logic is included, I will copy-paste the functions directly.

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
        font-size: 8em;
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

def process_teacher_plan(soup, week_number, week_data, week_vocab):
    """Updates Teacher Lesson Plan pages."""
    topic = week_data.get('topic', '')
    theme = week_data.get('theme', 'General')
    
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
    # L1 Learning Objectives (Page 1)
    l1_page = soup.find('div', class_='l1') 
    if l1_page:
        lo_card = l1_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                ul.clear()
                # Dynamic LOs
                sample_word = "Target Word"
                if week_vocab and 'l1_vocab' in week_vocab and len(week_vocab['l1_vocab']) > 0:
                    first_word = week_vocab['l1_vocab'][0].get('word', '').split('(')[0].strip()
                    sample_word = first_word
                
                ul.append(BeautifulSoup(f"<li><strong>Speaking:</strong> Speak fluently about {topic} using Part 2 structure.</li>", 'html.parser'))
                ul.append(BeautifulSoup(f"<li><strong>Vocab:</strong> Use 7 target words (e.g., <em>{sample_word}</em>) in context.</li>", 'html.parser'))
                ul.append(BeautifulSoup(f"<li><strong>Grammar:</strong> Use narrative tenses or relevant grammar for {theme}.</li>", 'html.parser'))
        
        # L1 Criteria
        criteria_h2 = l1_page.find('h2', string=re.compile(r'Criteria'))
        if criteria_h2:
            criteria_div = criteria_h2.find_next_sibling('div')
            if criteria_div:
                criteria_div.clear()
                criteria_div.append(BeautifulSoup(f"\"I can speak for 2 mins about {topic} using 2 idioms.\"", 'html.parser'))

    # L2 Learning Objectives (Page 4)
    l2_pages = soup.find_all('div', class_='l2')
    if l2_pages:
        l2_teacher_page = l2_pages[0] # Assuming first is Teacher Plan
        lo_card = l2_teacher_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                ul.clear()
                # Dynamic LOs
                sample_word_l2 = "Abstract Noun"
                if week_vocab and 'l2_vocab' in week_vocab and len(week_vocab['l2_vocab']) > 0:
                    first_word = week_vocab['l2_vocab'][0].get('word', '').split('(')[0].strip()
                    sample_word_l2 = first_word
                
                ul.append(BeautifulSoup(f"<li><strong>Logic:</strong> Use O.R.E. logic to answer Part 3 questions.</li>", 'html.parser'))
                ul.append(BeautifulSoup(f"<li><strong>Vocab:</strong> Use Abstract Nouns (e.g., <em>{sample_word_l2}</em>).</li>", 'html.parser'))
                ul.append(BeautifulSoup(f"<li><strong>Speaking:</strong> Discuss abstract ideas about {topic}.</li>", 'html.parser'))

        # L2 Criteria
        criteria_h2 = l2_teacher_page.find('h2', string=re.compile(r'Criteria'))
        if criteria_h2:
            criteria_div = criteria_h2.find_next_sibling('div')
            if criteria_div:
                criteria_div.clear()
                criteria_div.append(BeautifulSoup(f"\"I can answer 3 abstract questions about {topic} using O.R.E.\"", 'html.parser'))

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
            
            # Vocab Drill Update
            if len(cells) > 1 and "Vocab Drill" in cells[1].get_text():
                content = cells[1].decode_contents()
                if '"Thick and thin"' in content:
                    new_content = content.replace('"Thick and thin"', '"idioms"')
                    cells[1].clear()
                    cells[1].append(BeautifulSoup(new_content, 'html.parser'))

    # Dynamic Differentiation (All Differentiation Boxes)
    diff_cards = soup.find_all('div', class_='card')
    for card in diff_cards:
        h2 = card.find('h2')
        if h2 and "Differentiation" in h2.get_text():
            # Found a differentiation card. Update content.
            
            # L1 & L2 Strategy Update
            # Band 5 Box (Support)
            band5_div = card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if band5_div:
                # Dynamic sentence starter logic
                starter = f"I enjoy {topic} because..."
                if "Family" in topic: starter = "My family is important because..."
                elif "Place" in topic or "Country" in topic: starter = "I would love to visit..."
                
                band5_div.clear()
                band5_div.append(BeautifulSoup(f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: '{starter}'<br>• Peer Check: Simple generic prompts (e.g., 'Why?').", 'html.parser'))

            # Band 6 Box (Stretch)
            band6_div = card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if band6_div:
                band6_div.clear()
                band6_div.append(BeautifulSoup(f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: 'Admittedly...', 'Conversely...'<br>• Peer Check: Topic-specific extension questions.", 'html.parser'))

def process_vocabulary(soup, week_number, vocab_data):
    """Injects vocabulary into L1 and L2 tables."""
    # Week 1 Logic: 7 New words, 0 Recycled, 3 Idioms for L1
    
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

def format_bullet_text(html_content):
    """Formats 'You should say:' bullets: bold first word, inline, comma separated."""
    # 1. Parse content to handle <br>
    soup = BeautifulSoup(html_content, 'html.parser')
    # Get inner HTML string to preserve <br> for splitting
    # If it's a tag, decode_contents. If string, use directly.
    raw_str = soup.decode_contents() if soup.name else str(soup)
    
    # Split by <br> or <br/>
    parts = re.split(r'<br\s*/?>', raw_str)
    
    # First part might be "You should say:" or main question. 
    formatted_parts = []
    main_text = ""
    
    if "You should say" in parts[0]:
        # Split main question and "You should say" if they are in the first part
        main_text = parts[0].strip()
        bullet_lines = parts[1:]
    else:
        # Unexpected format, return as is
        return html_content

    # Process bullets
    formatted_bullets = []
    for line in bullet_lines:
        clean_line = BeautifulSoup(line, 'html.parser').get_text().strip()
        if not clean_line: continue
        
        words = clean_line.split(' ', 1)
        if len(words) > 0:
            first = words[0]
            rest = " " + words[1] if len(words) > 1 else ""
            formatted_bullets.append(f"<strong>{first}</strong>{rest}")
    
    # Reassemble: Main Text + formatted bullets joined by comma
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
    # Look for "CUE CARD: Describe..."
    cue_card_div = soup.find('div', style=lambda x: x and 'border-left:5px solid #fbc02d' in x)
    if cue_card_div:
        h3 = cue_card_div.find('h3')
        q1_html = q1_data.get('html', '')
        q1_soup = BeautifulSoup(q1_html, 'html.parser')
        prompt_p = q1_soup.find('p')
        
        if prompt_p:
            # We need to manually separate the Question title from the "You should say..." bullets
            # because the H3 takes the question, and the div takes the bullets.
            
            # Get raw HTML string of the P tag content
            p_content = prompt_p.decode_contents()
            
            # Split at "You should say:"
            if "You should say:" in p_content:
                parts = p_content.split("You should say:")
                question_text = BeautifulSoup(parts[0], 'html.parser').get_text().strip()
                
                # The bullets part starts with <br> usually
                bullets_raw = parts[1] 
                
                if h3:
                    h3.string = f"📌 CUE CARD: {question_text}"
                
                # Format bullets
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
                
                # Update bullets div
                bullets_div = cue_card_div.find('div', style=lambda x: x and 'color:#444' in x)
                if bullets_div:
                    bullets_div.clear()
                    bullets_div.append(BeautifulSoup(final_bullets_html, 'html.parser'))

    # Update Model Answer
    # Look for "Band 6.5 Model Answer"
    model_div = soup.find('div', class_='model-box') # The first model box is usually L1 Q1
    if model_div:
        # Get the answer part (usually second paragraph in source html)
        answer_p = q1_soup.find_all('p')[1] if len(q1_soup.find_all('p')) > 1 else None
        if answer_p:
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

def format_mind_maps(soup, week_data, ai_content):
    """Updates Mind Maps on Page 3."""
    l1_data = week_data.get('lesson_1_part_2', {})
    q1 = l1_data.get('q1', {})
    q2 = l1_data.get('q2', {})
    q3 = l1_data.get('q3', {})
    
    # 1. Main Brainstorming Map (Top of Page 3)
    q1_html = q1.get('html', '')
    q1_soup = BeautifulSoup(q1_html, 'html.parser')

    # Use AI Content
    central_text = ai_content.get('part_2_keyword', 'TOPIC')
    if not central_text: central_text = "TOPIC"
    
    # Update Center
    spider_centers = soup.find_all('div', class_='spider-center')
    if len(spider_centers) > 0:
        spider_centers[0].clear()
        spider_centers[0].append(BeautifulSoup(central_text, 'html.parser'))
        
    # Update Q1 Prompt (Above the map)
    # The map is usually inside a card. We need the div with "You should say:" text above it.
    # Page 3, first card.
    l1_practice_page = soup.find_all('div', class_='l1')[2] # Index 2 is Student Practice page
    if l1_practice_page:
        brainstorm_card = l1_practice_page.find('div', class_='card') # First card
        if brainstorm_card:
            prompt_div = brainstorm_card.find('div', style=lambda x: x and 'color:#444' in x)
            if prompt_div:
                q1_prompt_p = q1_soup.find('p')
                if q1_prompt_p:
                    # Format using the helper logic (Question + You should say + Bold Bullets)
                    # format_bullet_text expects the full inner HTML
                    fmt_html = format_bullet_text(q1_prompt_p.decode_contents())
                    prompt_div.clear()
                    prompt_div.append(BeautifulSoup(fmt_html, 'html.parser'))

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
            # Use formatted text
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
            # Use formatted text
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
                    if len(leg.contents) > 0:
                        leg.contents[0].replace_with(q3_hints[i])

WEEK_1_FOLLOW_UPS = {
    "q1": "Do you think parents are harder to please today compared to the past?",
    "q2": "Do you think you would do the same thing today?",
    "q3": "Have these advantages ever helped you in a difficult situation?",
    "q4": "Did you tell anyone else about this achievement?",
    "q5": "Can too much family pride ever lead to problems in society?",
    "q6": "What do you think success will look like for the next generation?"
}

def get_generic_peer_question(q_text):
    """Generates a generic peer-led question for Band 5."""
    q_text = q_text.lower()
    if "why" in q_text:
        return "Why do you think that?"
    elif "do you think" in q_text or "opinion" in q_text:
        return "Can you give an example?"
    elif "how" in q_text:
        return "Is this the only way?"
    elif "difference" in q_text or "compare" in q_text:
        return "Which one is better?"
    else:
        return "Why?"

def get_specific_peer_question(q_key):
    """Generates a specific peer-led question for Band 6+."""
    if q_key and q_key in WEEK_1_FOLLOW_UPS:
        return WEEK_1_FOLLOW_UPS[q_key]
    return "What other examples can you think of?"

def process_student_l2(soup, week_data, ai_content):
    """Updates Student Lesson 2 (Part 3) Q1-Q6."""
    l2_data = week_data.get('lesson_2_part_3', {})
    peer_qs = ai_content.get('part_3_peer_qs', [])
    
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
                if answer_html:
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
        
        # Remove Instruction Div (Task 1)
        instruction_div = page7.find('div', style=lambda x: x and 'color:#7f8c8d' in x and 'margin-bottom' in x)
        if instruction_div and "Instruction:" in instruction_div.decode_contents():
            instruction_div.decompose()

        # Apply Flex Layout to the Page Container (exclude header)
        # We need to find the container div that wraps the cards. 
        # In template: <div style="display:flex; flex-direction:column; gap:8px; flex-grow:1;">
        content_container = page7.find('div', style=lambda x: x and 'flex-direction:column' in x and 'gap:8px' in x)
        
        # Task 2: No padding between top of page banner and Q4 floating window
        # We remove the gap from the page itself
        page7['style'] = "gap:0 !important; padding-top:0 !important;"

        if content_container:
            # Force height 100% and hidden overflow to stay within page
            # Task 1: Reapply drop shadows (add padding to container to prevent clipping)
            # Reset style to avoid duplication
            # Task 2: Padding top 0 (to meet "No padding at all" request)
            content_container['style'] = "display:flex; flex-direction:column; gap:15px; flex-grow:1; height:100%; overflow:hidden; padding: 0 15px 20px 15px;"

        compact_cards = page7.find_all('div', class_='card compact')
        if len(compact_cards) >= 3:
            for card in compact_cards:
                # Force cards to share space equally
                # Reset style to avoid duplication
                card['style'] = "flex:1; display:flex; flex-direction:column; min-height:0; margin-bottom:0; overflow:visible;"
                
                # Make the writing container flex grow
                # Writing container is the div with background var(--bg-pastel-green)
                write_container = card.find('div', style=lambda x: x and 'bg-pastel-green' in x)
                if write_container:
                    # Added position:relative for absolute positioning of prompt
                    # Reset style to avoid duplication. Restoring original dashed border style.
                    write_container['style'] = "margin-top:5px; border-top:1px dashed #ccc; padding:8px; border-radius:8px; background:var(--bg-pastel-green); flex-grow:1; display:flex; flex-direction:column; min-height:0; overflow:hidden; position:relative;"
                    
                    # Make the lines grow
                    lines = write_container.find('div', class_='lines')
                    if lines:
                        lines['style'] = "height:100%;" # remove fixed height if any
                    
                    # Move 'Your Bullet Point Notes:' to top right
                    prompt = write_container.find('span', class_='write-prompt')
                    if prompt:
                        prompt['style'] = "position:absolute; top:3px; right:5px; font-size:0.7em; background:transparent;"

            update_q(4, 'q4', container_elem=compact_cards[0])
            update_q(5, 'q5', container_elem=compact_cards[1])
            update_q(6, 'q6', container_elem=compact_cards[2])

    # Inject Peer-Led Follow-up Questions (Differentiation)
    scaffold_uls = soup.find_all('ul', class_='scaffold-text')
    for idx, ul in enumerate(scaffold_uls):
        # AI Content Logic
        # peer_qs is a list of dicts: [{'b5': ..., 'b6': ...}, ...]
        # We expect 6 items. If missing, fallback.
        
        b5_q = "Why?" # Fallback
        b6_q = "What other examples can you think of?" # Fallback
        
        if idx < len(peer_qs):
            qs = peer_qs[idx]
            if isinstance(qs, dict):
                b5_q = qs.get('b5', b5_q)
                b6_q = qs.get('b6', b6_q)
            elif isinstance(qs, str): # Handle if string list
                b6_q = qs

        # Remove existing peer checks to avoid duplication
        existing_checks = ul.parent.find_all('div', style=lambda x: x and 'border-top:1px dotted #ccc' in x)
        for check in existing_checks:
            check.decompose()

        # Create Container for Peer Qs
        peer_container = soup.new_tag('div', attrs={'style': 'margin-top:1px; border-top:1px dotted #ccc; padding-top:1px; line-height:1.1;'})
        
        # Band 5 Question
        b5_div = soup.new_tag('div', attrs={'style': 'font-size:0.7em; color:#7f8c8d; margin-bottom:0;'})
        b5_div.append(BeautifulSoup(f"📉 <strong>Band 5 Peer Check:</strong> Ask: '{b5_q}'", 'html.parser'))
        
        # Band 6 Question
        b6_div = soup.new_tag('div', attrs={'style': 'font-size:0.7em; color:#7f8c8d; margin-bottom:0;'})
        b6_div.append(BeautifulSoup(f"📈 <strong>Band 6 Peer Check:</strong> Ask: '{b6_q}'", 'html.parser'))
        
        peer_container.append(b5_div)
        peer_container.append(b6_div)
        
        ul.parent.append(peer_container)

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
        # Reduce gap to 5px (Task 1)
        grammar_box['style'] = grammar_box['style'].replace('gap:15px', 'gap:5px')
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
    print("Generating all 40 lesson plans...")
    os.makedirs('lessons', exist_ok=True)
    
    # Load all data once
    curriculum_data, vocab_data, homework_data, ai_data = load_all_data()
    
    if not curriculum_data:
        print("Failed to load curriculum data. Exiting.")
        return

    # Load Template once
    with open('Week_2_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        template_html = f.read()

    success_count = 0
    errors = []

    for week_number in range(1, 41):
        try:
            print(f"--- Generating Week {week_number} ---")
            
            # Get data for the week
            week_curriculum, week_vocab, week_homework = get_week_data(week_number, curriculum_data, vocab_data, homework_data)
            
            if not week_curriculum:
                print(f"Skipping Week {week_number}: No curriculum data found.")
                errors.append(week_number)
                continue

            # Reset soup for each iteration
            soup = BeautifulSoup(template_html, 'html.parser')
            
            # Process Content
            ai_content = ai_data.get(str(week_number), {})
            
            process_cover_page(soup, week_number, week_curriculum)
            process_teacher_plan(soup, week_number, week_curriculum, week_vocab)
            process_vocabulary(soup, week_number, week_vocab)
            process_student_l1(soup, week_curriculum)
            format_mind_maps(soup, week_curriculum, ai_content)
            process_student_l2(soup, week_curriculum, ai_content)
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
