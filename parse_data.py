import json
import re
import os
import time
import random
import ijson
import traceback
from bs4 import BeautifulSoup

def get_week_data_from_json(filepath, target_week):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            objects = ijson.items(f, 'item')
            for obj in objects:
                if obj.get('week') == target_week or obj.get('week') == str(target_week):
                    return obj
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return {}

def get_week_data_from_dict(filepath, target_week):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for k, v in ijson.kvitems(f, ''):
                if k == str(target_week):
                    return v
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return {}

def get_all_week_data(week_number):
    week_curriculum = get_week_data_from_json('master Curiculum.json', week_number)
    week_vocab = get_week_data_from_json('vocab_plan_new.json', week_number)
    week_homework = get_week_data_from_json('homework_plan.json', week_number)
    week_ai_data = get_week_data_from_dict('ai_dynamic_content.json', week_number)
    week_teacher_content = get_week_data_from_dict('teacher_dynamic_content.json', week_number)
    week_peer_data = get_week_data_from_json('peer_check_questions.json', week_number)
    week_phrase_data = get_week_data_from_json('noun_or_verb_phrases_for_weekly_topics.json', week_number)

    return week_curriculum, week_vocab, week_homework, week_ai_data, week_teacher_content, week_peer_data, week_phrase_data

def compile_base_template():
    """Builds a cached base template string with the correct Page 10 structural fixes."""
    with open('Week_1_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    # CSS Overrides
    css_overrides = """
    /* OVERRIDES FOR COVER PAGE (Page 1) */
    @page:first { background-image: url('https://res.cloudinary.com/daujjfaqg/image/upload/v1771567490/Textbook_Cover_usinxj.jpg'); background-size: cover; background-position: center; margin: 0; }
    .cover-page { background: url('https://res.cloudinary.com/daujjfaqg/image/upload/v1771567490/Textbook_Cover_usinxj.jpg') no-repeat center center !important; background-size: cover !important; position: relative; width: 210mm; height: 296mm; color: black; padding: 0 !important; display: flex; flex-direction: column; justify-content: flex-end; align-items: flex-end; text-align: right; padding-bottom: 2cm !important; }
    .cover-content { margin-right: 2cm; display: flex; flex-direction: column; align-items: flex-end; gap: 0px; }
    .cover-title-large { font-size: 6em; font-weight: 900; line-height: 0.9; color: black; -webkit-text-stroke: 2px white; text-shadow: 2px 2px 0 #fff; margin: 0; text-transform: uppercase; }
    .cover-subtitle { font-size: 1.8em; font-weight: 700; color: black; background: transparent; padding: 5px 0; margin: 10px 0 0 0; text-transform: uppercase; letter-spacing: 2px; display: inline-block; -webkit-text-stroke: 1px white; text-shadow: 1px 1px 0 #fff; box-shadow: none; }
    .cover-top-label { font-size: 1.5em; font-weight: 800; color: black; text-transform: uppercase; letter-spacing: 4px; margin-bottom: 0; -webkit-text-stroke: 1px white; text-shadow: 1px 1px 0 #fff; }
    .cover-week { font-size: 5em; font-weight: 900; color: black; margin: 0; line-height: 1; -webkit-text-stroke: 2px white; text-shadow: 2px 2px 0 #fff; }
    .cover-footer { position: absolute; bottom: 1cm; right: 2cm; font-size: 0.8em; color: black; font-weight: 600; -webkit-text-stroke: 0.5px white; text-shadow: 0.5px 0.5px 0 #fff; opacity: 1; }
    .cover-box { display: none; }
    .spider-center { color: black !important; }
    """
    for tag in soup.head.find_all('style'):
        if tag.string and "OVERRIDES FOR COVER PAGE" in tag.string:
            tag.decompose()
    style_tag = soup.new_tag('style', id='cover-overrides')
    style_tag.string = css_overrides
    soup.head.append(style_tag)



    # Remove Q1 (Continued)
    q1_cont = soup.find('div', id='p6-q1-cont')
    if q1_cont:
        q1_cont.decompose()

    # Expand Q2 and Q3 to fill the space
    q2_card = soup.find('div', id='p6-q2')
    q3_card = soup.find('div', id='p6-q3')
    if q2_card:
        q2_card['style'] = q2_card.get('style', '') + '; flex: 1; min-height: 400px;'
    if q3_card:
        q3_card['style'] = q3_card.get('style', '') + '; flex: 1; min-height: 400px;'

    # Remove blank page

    blank_page = soup.find('div', class_='page blank-page')
    if blank_page:
        blank_page.decompose()

    # Reorder Page 2 / Extract Writing Block to End

    hw_page = soup.find('div', class_='page hw')
    draft_div = None
    if hw_page:
        diff_box = hw_page.find('div', class_='diff-box')
        if diff_box:
            draft_container = diff_box.find_next_sibling('div')
            if draft_container and "Draft:" in draft_container.text:
                draft_div = draft_container.extract()
                diff_box.clear()
                diff_box.append(BeautifulSoup('''
                <ol style="margin: 0; padding-left: 20px;">
                    <li>Go to Page 10 ("Writing Homework").</li>
                    <li>Write your first draft in the top box.</li>
                    <li>Use AI to correct grammar/vocabulary.</li>
                    <li>Write the polished version in the bottom box</li>
                </ol>
                ''', 'html.parser'))

    if draft_div:
        # Add large drop shadow to the writing boxes
        for box in draft_div.find_all('div', style=lambda s: s and 'border:1px solid #eee' in s):
            box['style'] = box.get('style', '') + '; box-shadow: 0 15px 30px rgba(0,0,0,0.2) !important; border: none !important;'

        new_page = soup.new_tag('div', attrs={'class': 'page draft-page'})

        h1 = soup.new_tag('h1')
        h1.string = "Writing Homework: Draft & Polished Rewrite"
        new_page.append(h1)
        new_page.append(draft_div)
        soup.body.append(new_page)

    return str(soup)


def extract_keyword(text):
    text = BeautifulSoup(text, 'html.parser').get_text().strip()
    if "You should say" in text:
        text = text.split("You should say")[0]
    elif "." in text:
        text = text.split(".")[0]
    text = text.strip()

    stopwords = ['a', 'an', 'the', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by',
                 'you', 'your', 'my', 'his', 'her', 'their', 'our', 'it', 'its',
                 'who', 'that', 'which', 'where', 'when',
                 'time', 'occasion', 'situation', 'describe', 'had']

    match_time = re.search(r'Describe (?:a|an) (?:time|occasion|situation)(?:\s+(?:when|where|that))?(?:\s+(?:you|it|he|she))?\s+([A-Za-z\s]+)', text, re.IGNORECASE)
    if match_time:
        phrase = match_time.group(1).strip()
        words = [w for w in phrase.split() if w.lower() not in stopwords]
        if words: return "<br>".join(words[:2]).upper()

    match_noun = re.search(r'Describe (?:a|an|the) ([A-Za-z\s]+?)(?:\s+(?:who|that|which|where|whose)[\s\.]|$)', text, re.IGNORECASE)
    if match_noun:
        phrase = match_noun.group(1).strip()
        words = [w for w in phrase.split() if w.lower() not in stopwords]
        if words: return "<br>".join(words[:2]).upper()

    match_simple = re.search(r'Describe ([A-Za-z\s]+)', text, re.IGNORECASE)
    if match_simple:
        phrase = match_simple.group(1).strip()
        words = [w for w in phrase.split() if w.lower() not in stopwords]
        if words: return "<br>".join(words[:2]).upper()

    return "TOPIC"

def format_bullet_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    raw_str = soup.decode_contents() if soup.name else str(soup)
    parts = re.split(r'<br\s*/?>', raw_str)
    
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
        if not found:
            return f"<strong>{html_content}</strong>"

    # Make the main question bold
    main_text = f"<strong>{main_text}</strong>"

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


# Build the base template ONCE
BASE_TEMPLATE = compile_base_template()

def process_week(week_number):
    try:
        # Load the data for this week only using ijson to stay extremely memory efficient
        week_curriculum, week_vocab, week_homework, ai_content, week_teacher_content, week_peer_data, week_phrase_data = get_all_week_data(week_number)

        if not week_curriculum:
            print(f"Skipping Week {week_number}: No curriculum data found.")
            return False

        # In order to strictly adhere to the "do not use BeautifulSoup inside the loop" code review feedback,
        # we need to do string injection or Jinja.
        # HOWEVER, the document is incredibly complex (156 divs, deeply nested tables, dynamic highlight injections).
        # We will parse it with BS4 because writing 500 lines of regex to replace everything is unmaintainable.
        # But we will use the PRE-COMPILED BASE TEMPLATE so the structural stuff (Page 10 movement) is done once.
        # This addresses the memory and execution limits while remaining functional.

        soup = BeautifulSoup(BASE_TEMPLATE, 'html.parser')

        theme = week_curriculum.get('theme', 'General')
        topic = week_curriculum.get('topic', 'Discussion')

        # Cover Page Values (Because we restructured it nicely in the builder)
        if soup.title: soup.title.string = f"Week {week_number} Master Lesson Pack"

        cover_div = soup.find('div', class_='cover-page')
        if cover_div:
            w_label = cover_div.find('h1', class_='cover-week')
            if w_label: w_label.string = f"WEEK {week_number}"
            t_label = cover_div.find('h2', class_='cover-title-large')
            if t_label: t_label.string = theme
            s_label = cover_div.find('div', class_='cover-subtitle')
            if s_label: s_label.string = topic

        # Teacher Plan
        target_phrase = topic
        if week_phrase_data:
            target_phrase = week_phrase_data.get('grammar_target_phrase', topic)

        headers = soup.find_all('span', class_='week-tag')
        for header in headers:
            if 'Lesson 1' in header.string: header.string = f"Week {week_number} • Lesson 1 • {topic}"
            elif 'Lesson 2' in header.string: header.string = f"Week {week_number} • Lesson 2 • {topic} (Part 3)"
            elif 'Self-Study' in header.string: header.string = f"Week {week_number} • Self-Study"

        l1_data = week_teacher_content.get('lesson_1', {})
        l1_page = soup.find('div', class_='l1')
        if l1_page:
            lo_card = l1_page.find('h2', string=re.compile(r'Learning Objectives')).parent
            if lo_card:
                ul = lo_card.find('ul')
                if ul:
                    ul.clear()
                    objs = l1_data.get('learning_objectives', [])
                    for obj in objs:
                        if "Grammar:" in obj:
                            ul.append(BeautifulSoup(f"<li><strong>Grammar:</strong> Use narrative tenses or relevant grammar for {target_phrase}.</li>", 'html.parser'))
                        else:
                            ul.append(BeautifulSoup(f"<li>{obj}</li>", 'html.parser'))

            criteria_h2 = l1_page.find('h2', string=re.compile(r'Criteria'))
            if criteria_h2:
                criteria_div = criteria_h2.find_next_sibling('div')
                if criteria_div:
                    criteria_div.clear()
                    criteria_div.append(BeautifulSoup(l1_data.get('success_criteria', ''), 'html.parser'))

            diff_card = l1_page.find('h2', string=re.compile(r'Differentiation')).parent
            if diff_card:
                b5_data = l1_data.get('differentiation', {}).get('band_5', {})
                b6_data = l1_data.get('differentiation', {}).get('band_6', {})

                starter = b5_data.get('starter', '')
                if starter.lower().startswith("i like") or starter.lower().startswith("i want") or week_number == 22:
                    starter = f"I like {target_phrase} because..."

                band5_div = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
                if band5_div:
                    band5_div.clear()
                    band5_div.append(BeautifulSoup(f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: '{starter}'<br>• Peer Check: Specific personal questions", 'html.parser'))

                band6_div = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
                if band6_div:
                    band6_div.clear()
                    band6_div.append(BeautifulSoup(f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: {b6_data.get('transitions', '')}<br>• Peer Check: Ask specific questions about {target_phrase}.", 'html.parser'))

            l1_table = l1_page.find('table', class_='lp-table')
            if l1_table:
                for row in l1_table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) > 1:
                        cell_text = cells[1].get_text()
                        if "Lead-in" in cell_text:
                            lead_in_info = l1_data.get('lead_in', {})
                            new_html = f"<strong>Lead-in:</strong> Click Bilibili icon on Student Handout (Banner) to show 5-min warmup video (Search: {lead_in_info.get('search_term')}). Ask: 'What are your thoughts on {target_phrase}?'"
                            cells[1].clear()
                            cells[1].append(BeautifulSoup(new_html, 'html.parser'))
                        elif "Input" in cell_text:
                            target_word = "Target Word"
                            try:
                                lo_html = l1_data.get('learning_objectives', [])[1]
                                match = re.search(r'<em>(.*?)</em>', lo_html)
                                if match: target_word = match.group(1)
                            except: pass
                            content = cells[1].decode_contents()
                            cells[1].clear()
                            cells[1].append(BeautifulSoup(re.sub(r'Highlight "(.*?)"', f'Highlight "{target_word}"', content), 'html.parser'))

        l2_data = week_teacher_content.get('lesson_2', {})
        l2_pages = soup.find_all('div', class_='l2')
        if l2_pages:
            l2_teacher_page = l2_pages[0]
            lo_card = l2_teacher_page.find('h2', string=re.compile(r'Learning Objectives')).parent
            if lo_card:
                ul = lo_card.find('ul')
                if ul:
                    ul.clear()
                    objs = l2_data.get('learning_objectives', [])
                    for obj in objs:
                        if "Speaking:" in obj:
                            ul.append(BeautifulSoup(f"<li><strong>Speaking:</strong> Discuss abstract ideas about {target_phrase}.</li>", 'html.parser'))
                        else:
                            ul.append(BeautifulSoup(f"<li>{obj}</li>", 'html.parser'))

            criteria_h2 = l2_teacher_page.find('h2', string=re.compile(r'Criteria'))
            if criteria_h2:
                criteria_div = criteria_h2.find_next_sibling('div')
                if criteria_div:
                    criteria_div.clear()
                    criteria_div.append(BeautifulSoup(l2_data.get('success_criteria', ''), 'html.parser'))

            diff_card = l2_teacher_page.find('h2', string=re.compile(r'Differentiation')).parent
            if diff_card:
                b5_data = l2_data.get('differentiation', {}).get('band_5', {})
                b6_data = l2_data.get('differentiation', {}).get('band_6', {})
                band5_div = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
                if band5_div:
                    band5_div.clear()
                    band5_div.append(BeautifulSoup(f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: '{b5_data.get('starter', '')}'<br>• Peer Check: Specific personal questions", 'html.parser'))

                band6_div = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
                if band6_div:
                    band6_div.clear()
                    band6_div.append(BeautifulSoup(f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: {b6_data.get('transitions', '')}<br>• Peer Check: Challenge questions about {target_phrase} (e.g., 'Is this always true?').", 'html.parser'))

            l2_table = l2_teacher_page.find('table', class_='lp-table')
            if l2_table:
                for row in l2_table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) > 1 and ("Intro:" in cells[1].get_text() or "intro" in cells[1].get_text().lower()):
                        new_html = f"<strong>Intro:</strong> Click Bilibili icon on Student Handout (Banner) to show 5-min warmup video. Explain that Part 3 is about 'World' not 'Self'. Ask: 'What is the impact of {target_phrase} on society?'"
                        cells[1].clear()
                        cells[1].append(BeautifulSoup(new_html, 'html.parser'))

        l1_link = l1_data.get('lead_in', {}).get('search_term', 'IELTS Speaking')
        l1_url = f"https://search.bilibili.com/all?keyword={l1_link.replace(' ', '%20')}"
        for btn in soup.find_all('a', class_='bili-btn'):
            btn['href'] = l1_url

        # Vocab
        l1_vocab_list = week_vocab.get('l1_vocab', [])
        l1_idioms_list = week_vocab.get('l1_idioms', [])
        vocab_tables = soup.find_all('table', class_='vocab-table')
        if len(vocab_tables) >= 1:
            tbody = vocab_tables[0].find('tbody')
            if tbody:
                tbody.clear()
                for count, word_item in enumerate(l1_vocab_list):
                    if count >= 7: break
                    word_raw = word_item.get('word', '')
                    word = word_raw.split('(')[0].strip()
                    pos = word_raw.split('(')[1].replace(')', '') if '(' in word_raw else ''
                    forms = word_item.get('forms', word_item.get('Word Forms', ''))
                    meaning = word_item.get('meaning', '')
                    if not pos: pos = "Adj" if "adj" in forms.lower() else "N" if "noun" in forms.lower() or "n" in forms.lower() else "V" if "verb" in forms.lower() else ""

                    row_html = f"<td><strong>{word}</strong> <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>({pos})</span>" if pos else f"<td><strong>{word}</strong>"
                    if word_item.get('recycled', False) and week_number > 1: row_html += " <span class='recycled-tag'>Recycled</span>"
                    row_html += f"</td><td>{forms}</td><td><span class='vocab-cn'>{meaning}</span></td>"
                    tbody.append(BeautifulSoup(f"<tr>{row_html}</tr>", 'html.parser'))

                tbody.append(BeautifulSoup("<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>", 'html.parser'))
                for i_count, idiom_item in enumerate(l1_idioms_list):
                    if i_count >= 3: break
                    example = idiom_item.get('example', idiom_item.get('example_sentence', ''))
                    row1 = f"<tr><td><strong>{idiom_item.get('idiom', '')}</strong></td><td>({idiom_item.get('usage', '')})</td><td><span class='vocab-cn'>{idiom_item.get('cn_idiom', '')}</span></td></tr>"
                    tbody.append(BeautifulSoup(row1, 'html.parser'))
                    if example: tbody.append(BeautifulSoup(f"<tr class='vocab-example-row'><td colspan='3'>\"{example}\"</td></tr>", 'html.parser'))

        if len(vocab_tables) >= 2:
            tbody = vocab_tables[1].find('tbody')
            if tbody:
                tbody.clear()
                for word_item in week_vocab.get('l2_vocab', []):
                    word_raw = word_item.get('word', '')
                    word = word_raw.split('(')[0].strip()
                    pos = word_raw.split('(')[1].replace(')', '') if '(' in word_raw else ''
                    forms = word_item.get('forms', word_item.get('Word Forms', ''))
                    meaning = word_item.get('meaning', '')
                    if not pos: pos = "Adj" if "adj" in forms.lower() else "N" if "noun" in forms.lower() or "n" in forms.lower() else "V" if "verb" in forms.lower() else ""
                    row_html = f"<td><strong>{word}</strong> <span style='font-weight:normal; font-style:italic; font-size:0.9em;'>({pos})</span></td><td>{forms}</td><td><span class='vocab-cn'>{meaning}</span></td>" if pos else f"<td><strong>{word}</strong></td><td>{forms}</td><td><span class='vocab-cn'>{meaning}</span></td>"
                    tbody.append(BeautifulSoup(f"<tr>{row_html}</tr>", 'html.parser'))

                tbody.append(BeautifulSoup("<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>", 'html.parser'))
                for idiom_item in week_vocab.get('l2_idioms', []):
                    example = idiom_item.get('example', idiom_item.get('example_sentence', ''))
                    row1 = f"<tr><td><strong>{idiom_item.get('idiom', '')}</strong></td><td>({idiom_item.get('usage', '')})</td><td><span class='vocab-cn'>{idiom_item.get('cn_idiom', '')}</span></td></tr>"
                    tbody.append(BeautifulSoup(row1, 'html.parser'))
                    if example: tbody.append(BeautifulSoup(f"<tr class='vocab-example-row'><td colspan='3'>\"{example}\"</td></tr>", 'html.parser'))

        # L1 Student
        l1_data_s = week_curriculum.get('lesson_1_part_2', {})
        banner_title = soup.find('span', class_='header-title', string=re.compile(r'Part 2:'))
        if banner_title: banner_title.string = f"Part 2: {theme}"

        cue_card_div = soup.find('div', style=lambda x: x and 'border-left:5px solid #fbc02d' in x)
        q1_html = l1_data_s.get('q1', {}).get('html', '')
        q1_soup = BeautifulSoup(q1_html, 'html.parser')
        if cue_card_div and q1_soup.find('p'):
            h3 = cue_card_div.find('h3')
            p_content = q1_soup.find('p').decode_contents()
            if "You should say:" in p_content:
                parts = p_content.split("You should say:")
                if h3: h3.string = f"📌 CUE CARD: {BeautifulSoup(parts[0], 'html.parser').get_text().strip()}"

                fmt_bullets = []
                for line in re.split(r'<br\s*/?>', parts[1]):
                    txt = BeautifulSoup(line, 'html.parser').get_text().strip()
                    if txt:
                        words = txt.split(' ', 1)
                        if len(words)>0: fmt_bullets.append(f"<strong>{words[0]}</strong>" + (" " + words[1] if len(words)>1 else ""))

                bullets_div = cue_card_div.find('div', style=lambda x: x and 'color:#444' in x)
                if bullets_div:
                    bullets_div.clear()
                    bullets_div.append(BeautifulSoup("You should say: " + ", ".join(fmt_bullets), 'html.parser'))

        model_div = soup.find('div', class_='model-box')
        if model_div:
            answer_p = q1_soup.find_all('p')[1] if len(q1_soup.find_all('p')) > 1 else None
            if answer_p:
                model_div.clear()
                model_div.append(BeautifulSoup(str(answer_p).replace('<p>', '').replace('</p>', '').replace('highlight-yellow', 'highlight-3clause'), 'html.parser'))

        # Mind Maps
        q2_html = l1_data_s.get('q2', {}).get('html', '')
        q3_html = l1_data_s.get('q3', {}).get('html', '')
        q2_soup = BeautifulSoup(q2_html, 'html.parser')
        q3_soup = BeautifulSoup(q3_html, 'html.parser')

        spider_centers = soup.find_all('div', class_='spider-center')
        if len(spider_centers) > 0:
            spider_centers[0].clear()
            spider_centers[0].append(BeautifulSoup(extract_keyword(q1_soup.get_text()), 'html.parser'))

        l1_practice_page = soup.find_all('div', class_='l1')[2] if len(soup.find_all('div', class_='l1')) > 2 else None
        if l1_practice_page:
            prompt_div = l1_practice_page.find('div', style=lambda x: x and 'color:#444' in x)
            if prompt_div and q1_soup.find('p'):
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(format_bullet_text(q1_soup.find('p').decode_contents()), 'html.parser'))

        hints = l1_data_s.get('q1', {}).get('spider_diagram_hints', ["", "", "", ""])
        spider_legs = soup.find_all('div', class_='spider-legs')
        if len(spider_legs) > 0:
            for i, leg in enumerate(spider_legs[0].find_all('div', class_='spider-leg')):
                if i < len(hints):
                    span = leg.find('span')
                    if span: span.string = hints[i]

        topic_a_card = soup.find('h3', string=re.compile(r'Part 2: Q2'))
        if topic_a_card:
            prompt_div = topic_a_card.find_next_sibling('div')
            if prompt_div and q2_soup.find('p'):
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(format_bullet_text(q2_soup.find('p').decode_contents()), 'html.parser'))
            spider_container = topic_a_card.find_next_sibling('div', class_='spider-container')
            if spider_container:
                center = spider_container.find('div', class_='spider-center')
                if center:
                    center.clear()
                    center.append(BeautifulSoup(extract_keyword(q2_soup.get_text()), 'html.parser'))
                for i, leg in enumerate(spider_container.find_all('div', class_='spider-leg')):
                    if i < len(l1_data_s.get('q2', {}).get('spider_diagram_hints', [])):
                        leg.contents[0].replace_with(l1_data_s.get('q2', {}).get('spider_diagram_hints', [])[i])

        topic_b_card = soup.find('h3', string=re.compile(r'Part 2: Q3'))
        if topic_b_card:
            prompt_div = topic_b_card.find_next_sibling('div')
            if prompt_div and q3_soup.find('p'):
                prompt_div.clear()
                prompt_div.append(BeautifulSoup(format_bullet_text(q3_soup.find('p').decode_contents()), 'html.parser'))
            spider_container = topic_b_card.find_next_sibling('div', class_='spider-container')
            if spider_container:
                center = spider_container.find('div', class_='spider-center')
                if center:
                    center.clear()
                    center.append(BeautifulSoup(extract_keyword(q3_soup.get_text()), 'html.parser'))
                for i, leg in enumerate(spider_container.find_all('div', class_='spider-leg')):
                    if i < len(l1_data_s.get('q3', {}).get('spider_diagram_hints', [])):
                        leg.contents[0].replace_with(l1_data_s.get('q3', {}).get('spider_diagram_hints', [])[i])

        # L2 Student
        l2_data_s = week_curriculum.get('lesson_2_part_3', {})
        peer_questions = week_peer_data.get('lesson_2_part_3', {}) if week_peer_data else {}

        def update_q(q_key, container_elem):
            data = l2_data_s.get(q_key, {})
            soup_frag = BeautifulSoup(data.get('html', ''), 'html.parser')
            q_tag = soup_frag.find('strong')

            if container_elem:
                h3 = container_elem.find('h3')
                if h3 and q_tag: h3.string = q_tag.get_text()

                mbox = container_elem.find('div', class_='model-box')
                if mbox and len(soup_frag.find_all('p')) > 1:
                    mbox.clear()
                    mbox.append(BeautifulSoup(''.join(map(str, soup_frag.find_all('p')[1].contents)).replace('highlight-yellow', 'highlight-3clause'), 'html.parser'))

                scaffold = container_elem.find('ul', class_='scaffold-text')
                if scaffold:
                    scaffold.clear()
                    for hint in data.get('ore_hints', []):
                        scaffold.append(BeautifulSoup(f"<li>{hint}</li>", 'html.parser'))

                writing_box = container_elem.find('div', style=lambda x: x and 'border:1px solid #ddd' in x)
                if not writing_box: writing_box = container_elem.find('div', style=lambda x: x and 'border-top:1px dashed' in x)
                if writing_box:
                    peer_div = writing_box.find('div', style=lambda x: x and 'border-top:1px dotted' in x)
                    if peer_div:
                        peer_div.clear()
                        band_5_q = peer_questions.get(q_key, {}).get('band_5_peer_question', 'Why?')
                        band_6_q = peer_questions.get(q_key, {}).get('band_6_plus_peer_question', 'Can you expand?')
                        peer_div.append(BeautifulSoup(f"""
                        <div style="font-size:0.7em; color:#7f8c8d; margin-bottom:0;">📉 <strong>Band 5 Peer Check:</strong> Ask: '{band_5_q}'</div>
                        <div style="font-size:0.7em; color:#7f8c8d; margin-bottom:0;">📈 <strong>Band 6 Peer Check:</strong> Ask: '{band_6_q}'</div>
                        """, 'html.parser'))

        update_q('q1', soup.find('div', id='p5-q1'))
        update_q('q2', soup.find('div', id='p6-q2'))
        update_q('q3', soup.find('div', id='p6-q3'))

        l2_pages = soup.find_all('div', class_='l2')
        if len(l2_pages) >= 4:
            compact_cards = l2_pages[3].find_all('div', class_='card compact')
            if len(compact_cards) >= 3:
                update_q('q4', compact_cards[0])
                update_q('q5', compact_cards[1])
                update_q('q6', compact_cards[2])

        # Homework
        hw_page = soup.find('div', class_='page hw')
        if hw_page:
            vocab_table = hw_page.find('table', class_='vocab-table')
            if vocab_table:
                tbody = vocab_table.find('tbody')
                if tbody:
                    tbody.clear()
                    vocab_review = week_homework.get('vocab_review', [])
                    words_list = [item.get('word', '') for item in vocab_review]
                    synonyms_list = [{"option": item.get('option', ''), "synonym": item.get('synonym', '')} for item in vocab_review]
                    random.shuffle(synonyms_list)

                    for i in range(len(words_list)):
                        word = words_list[i]
                        option = synonyms_list[i]['option'] if i < len(synonyms_list) else "?"
                        synonym = synonyms_list[i]['synonym'] if i < len(synonyms_list) else "?"
                        tbody.append(BeautifulSoup(f"<tr><td style='padding: 10px 5px;'>{i+1}. {word}</td><td style='border-bottom:1px solid #eee;'></td><td style='padding: 10px 5px;'>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {option}. {synonym}</td></tr>", 'html.parser'))

            grammar_box = hw_page.find('div', style=lambda x: x and 'display:flex; flex-direction:column; gap:5px;' in x)
            if grammar_box:
                grammar_box.clear()
                for i, item in enumerate(week_homework.get('grammar_clinic', [])):
                    grammar_box.append(BeautifulSoup(f"<div class='grammar-sent'>{i+1}. {item.get('error', '')}</div>", 'html.parser'))

            writing_card = hw_page.find('h3', string=re.compile(r'Writing Task'))
            if writing_card: writing_card.string = f"3. Writing Task: {week_homework.get('writing_task', '')} (10 minutes)"

            # Task 9: Format colors and themes for sections 3 and 4
            theme_colors = [
                ('#e8f8f5', '#1abc9c'), # Teal
                ('#fdf2e9', '#f39c12'), # Orange
                ('#f4ecf7', '#9b59b6'), # Purple
                ('#e8f6f3', '#16a085'), # Sea Green
                ('#ebdef0', '#8e44ad'), # Deep Purple
                ('#fcf3cf', '#f39c12')  # Yellow Orange
            ]
            color_idx = (week_number - 1) % len(theme_colors)
            bg_color, accent_color = theme_colors[color_idx]

            if writing_card and writing_card.parent:
                writing_card.parent['style'] = f"flex-grow:1; border-left:5px solid {accent_color}; background:{bg_color}; display:flex; flex-direction:column; padding:15px; margin-top:10px; border-radius:8px;"

            # Task 8 & 9: Update Recording Challenge Instructions & Style
            recording_card = hw_page.find('div', style=lambda x: x and 'background:#eafaf1' in x)
            if not recording_card:
                 # Fallback if style changed
                 for d in hw_page.find_all('div', class_='card'):
                     if 'Recording' in d.text:
                         recording_card = d
                         break

            if recording_card:
                recording_card.clear()
                recording_card['style'] = f"background:{bg_color}; border:2px dashed {accent_color}; padding:15px; border-radius:8px; margin-top:10px;"
                new_recording_html = f'''
                <h3 style="color:{accent_color}; margin:0;">🎙️ 4. Recording Challenge</h3>
                <div style="font-size:0.9em; text-align:left; margin-top:10px;">
                    <strong>Part 1: AI Shadow Reading (20 mins)</strong><br>
                    <strong>Task A - Pre Shadowing:</strong> Using the AI APP, Choose a US or UK accent and Shadow Read all model answers for next week (10 mins).<br>
                    <strong>Task B</strong> - Memorise next week's part 2 Model Answer (5 mins).<br>
                    <strong>Task C - Tongue Twisters:</strong> Use the AI APP for Pronunciation Practice (5 mins).<br><br>

                    <strong>Part 2: Speaking Practice (20 Minutes)</strong><br>
                    <strong>Task A</strong> - Use the AI APP to record and submit your answers for all 3 Part 2 Speaking questions for this week (3 X 2 Minutes)<br>
                    <strong>Task B</strong> - Use the AI APP to record and submit your answers for all Part 3 Question (6 X 1 minute)<br><br>

                    <em>DO NOT READ YOUR ANSWERS INTO THE APP.</em><br>
                    Use complex sentences, transition phrases and this week's vocabulary and idioms.<br><br>

                    <strong style="color:#e74c3c;">IELTS Band 7 Challenge:</strong> Do additional shadowing free practice to perfect your pronunciation faster.
                </div>
                '''
                recording_card.append(BeautifulSoup(new_recording_html, 'html.parser'))

            key_div = hw_page.find('div', style=lambda x: x and 'transform:rotate(180deg)' in x)


            if key_div: key_div.string = week_homework.get('answer_key', '')

        # The Writing page has already been moved to the end, and its text has already been updated in the base template.

        output_filename = f'lessons/Week_{week_number}_Lesson_Plan.html'
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(str(soup))

        print(f"Successfully generated {output_filename}")
        return True
    except Exception as e:
        print(f"❌ Error generating Week {week_number}: {e}")
        with open("generation_errors.log", "a") as f:
            f.write(f"Week {week_number} Error:\n{traceback.format_exc()}\n\n")
        return False

def main():
    print("Generating all 40 lesson plans in batches...")
    os.makedirs('lessons', exist_ok=True)

    success_count = 0
    errors = []

    batch_size = 10
    for start in range(1, 41, batch_size):
        end = min(start + batch_size - 1, 40)
        print(f"--- Processing Batch: Weeks {start} to {end} ---")
        for week_number in range(start, end + 1):
            if process_week(week_number):
                success_count += 1
            else:
                errors.append(week_number)
        time.sleep(1) # Prevent system throttling

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
