import json
import re
import os
import time
import random
import urllib.parse
from jinja2 import Template
import traceback

def load_data():
    print("Loading data files...")
    try:
        with open('master Curiculum.json', 'r', encoding='utf-8') as f:
            curriculum_data = json.load(f)
    except FileNotFoundError:
        print("Error: master Curiculum.json not found.")
        return None, None, None, None, None, None

    try:
        with open('noun_or_verb_phrases_for_weekly_topics.json', 'r', encoding='utf-8') as f:
            phrase_list = json.load(f)
            phrase_data = {item['week']: item for item in phrase_list}
    except FileNotFoundError:
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
        peer_data = {}

    try:
        with open('mindmap_labels.json', 'r', encoding='utf-8') as f:
            mindmap_labels = json.load(f).get('mindmap_labels', {})
    except FileNotFoundError:
        mindmap_labels = {}
        
    return curriculum_data, phrase_data, vocab_data, homework_data, peer_data, mindmap_labels

def format_bullet_text(html_content, bold_question=False):
    import bs4
    soup = bs4.BeautifulSoup(html_content, 'html.parser')
    if soup.p: soup.p.unwrap()

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
        if not found: return html_content

    if bold_question:
        main_text = f"<strong>{main_text}</strong>"

    formatted_bullets = []
    for line in bullet_lines:
        clean_line = bs4.BeautifulSoup(line, 'html.parser').get_text().strip()
        if not clean_line: continue
        words = clean_line.split(' ', 1)
        if len(words) > 0:
            first = words[0]
            rest = " " + words[1] if len(words) > 1 else ""
            formatted_bullets.append(f"<strong>{first}</strong>{rest}")
    
    return f"{main_text} {', '.join(formatted_bullets)}"

def build_vocab_html(vocab, idioms):
    html = ""
    for i, item in enumerate(vocab):
        if i >= 7: break
        word_raw = item.get('word', '')
        word = word_raw.split('(')[0].strip() if '(' in word_raw else word_raw.strip()
        pos = word_raw.split('(')[1].replace(')', '') if '(' in word_raw else ''
        pos_span = f" <span style='font-style:italic;font-size:0.9em;'>({pos})</span>" if pos else ""
        row = f"<td><strong>{word}</strong>{pos_span}</td><td>{item.get('forms','')}</td><td><span class='vocab-cn'>{item.get('meaning','')}</span></td>"
        html += f"<tr>{row}</tr>"
    
    html += "<tr><td colspan='3' style='background:#eee; font-weight:bold; color:#555;'>🐎 Idioms</td></tr>"
    for i, item in enumerate(idioms):
        if i >= 3: break
        idiom_text = item.get('idiom','')
        usage_text = item.get('usage','')
        cn_idiom = item.get('cn_idiom','')
        example = item.get('example') or item.get('example_sentence') or ""
        row1 = f"<td><strong>{idiom_text}</strong></td><td>({usage_text})</td><td><span class='vocab-cn'>{cn_idiom}</span></td>"
        html += f"<tr>{row1}</tr>"
        if example:
            row2 = f"<tr class='vocab-example-row'><td colspan='3' style='padding-left:15px; padding-top:2px; padding-bottom:6px; font-style:italic; color:#666; font-size:0.9em; border-bottom:1px solid #eee;'>\"{example}\"</td></tr>"
            html += row2
    return html

def build_spider_html(hints):
    legs = ""
    for i, hint in enumerate(hints):
        if i == 0 or i == 2:
            legs += f"<div class=\"spider-leg\"><strong>{i+1}. LABEL:</strong><br><span style=\"color:#777;\">{hint}</span></div>"
        else:
            legs += f"<div class=\"spider-leg\">{hint}<div class=\"lines\"></div></div>"
            
    # Normalize to simple lines style for robustness
    legs = ""
    for hint in hints:
        legs += f"<div class=\"spider-leg\">{hint}<div class=\"lines\"></div></div>"

    return f"<div class=\"spider-legs\">{legs}</div>"

def main():
    print("Generating all 40 lesson plans...")
    os.makedirs('lessons', exist_ok=True)

    curriculum, phrases, vocab, homework, peer_data, mindmap_labels = load_data()
    if not curriculum: return

    with open('template.j2', 'r', encoding='utf-8') as f:
        template_str = f.read()

    template = Template(template_str)

    success_count = 0
    errors = []

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
                
                week_vocab = vocab.get(week_num, {})
                week_homework = homework.get(week_num, {})
                week_peer = peer_data.get(week_num, {}).get('lesson_2_part_3', {})
                week_phrase = phrases.get(week_num, {}).get('grammar_target_phrase', 'this topic')
                theme = week_data.get('theme', '')
                topic = week_data.get('topic', '')

                # Context variables
                ctx = {}
                ctx['page_title'] = f"Week {week_num} Master Lesson Pack"
                ctx['cover_week'] = f"WEEK {week_num}"
                ctx['cover_theme'] = theme
                ctx['cover_topic'] = topic
                ctx['bilibili_url'] = f"https://search.bilibili.com/all?keyword={urllib.parse.quote(f'IELTS {topic} Speaking')}"
                ctx['l1_week_tag'] = f"Week {week_num} • Lesson 1 • {topic}"
                ctx['l2_week_tag'] = f"Week {week_num} • Lesson 2 • {topic} (Part 3)"

                first_word_l1 = week_vocab.get('l1_vocab', [{}])[0].get('word', 'Target Word').split('(')[0].strip()
                first_word_l2 = week_vocab.get('l2_vocab', [{}])[0].get('word', 'Abstract Noun').split('(')[0].strip()

                ctx['l1_lo_speaking'] = f"<strong>Speaking:</strong> Speak fluently about {week_phrase} using Part 2 structure."
                ctx['l1_lo_vocab'] = f"<strong>Vocab:</strong> Use 7 target words (e.g., <em>{first_word_l1}</em>) in context."
                ctx['l1_lo_grammar'] = f"Grammar: Use narrative tenses or relevant grammar for {week_phrase}."
                ctx['l1_criteria'] = f"\"I can speak for 2 mins about {week_phrase} using 2 idioms.\""
                ctx['l1_diff_b5'] = f"<strong>📉 Band 5.0 (Support)</strong><br>• Sentence Starter: 'I like {week_phrase} because...'<br>• Peer Check: Ask a personal follow up question."
                ctx['l1_diff_b6'] = f"<strong>📈 Band 6.0+ (Stretch)</strong><br>• Transitions: 'Admittedly...', 'Conversely...'<br>• Peer Check: Ask an abstract question about {week_phrase}."
                ctx['l1_leadin'] = f"<strong>Lead-in:</strong> Click Bilibili icon on Student Handout (Banner) to show 5-min warmup video (Search: IELTS {topic} Speaking). Ask: 'Do you think {week_phrase} is important in your life?'"
                ctx['l1_input'] = f"<strong>Input:</strong> Read Model. Highlight \"vocabulary list words\". Analyze 3-clause sentence structure. Check understanding of idioms."

                ctx['l2_lo_speaking'] = f"<strong>Speaking:</strong> Discuss abstract ideas about {week_phrase}."
                ctx['l2_lo_vocab'] = f"<strong>Vocab:</strong> Use Abstract Nouns (e.g., <em>{first_word_l2}</em>)."
                ctx['l2_criteria'] = f"\"I can answer 3 abstract questions about {week_phrase} using O.R.E.\""
                ctx['l2_diff_b5'] = ctx['l1_diff_b5']
                ctx['l2_diff_b6'] = ctx['l1_diff_b6']

                ctx['l1_vocab_tbody'] = build_vocab_html(week_vocab.get('l1_vocab', []), week_vocab.get('l1_idioms', []))
                ctx['l2_vocab_tbody'] = build_vocab_html(week_vocab.get('l2_vocab', []), week_vocab.get('l2_idioms', []))

                l1_data = week_data.get('lesson_1_part_2', {})
                ctx['part2_banner_title'] = f"Part 2: {theme}"

                # Part 2 Q1
                q1_html = l1_data.get('q1', {}).get('html', '')
                import bs4
                bs = bs4.BeautifulSoup(q1_html, 'html.parser')
                ps = bs.find_all('p')
                if len(ps) > 0:
                    q_text = bs4.BeautifulSoup(ps[0].decode_contents().split("You should say")[0], 'html.parser').get_text().strip()
                    ctx['l1_q1_cue_html'] = f"<h3>📌 CUE CARD: {q_text}</h3><div style=\"font-size:0.9em; color:#444;\">{format_bullet_text(str(ps[0]))}</div>"
                    ctx['l1_q1_spider_prompt'] = format_bullet_text(str(ps[0]), bold_question=True)
                else:
                    ctx['l1_q1_cue_html'] = ""
                    ctx['l1_q1_spider_prompt'] = ""

                ctx['l1_q1_model'] = "".join([str(x) for x in ps[1].contents]) if len(ps) >= 2 else "Model Answer Not Found"

                labels = mindmap_labels.get(f"week_{week_num}", {}).get('lesson_1', {})
                q1_hints = l1_data.get('q1', {}).get('spider_diagram_hints', [])
                ctx['l1_q1_spider'] = f"<div class=\"spider-center\" style=\"background: var(--bg-pastel-blue); color: black;\">{labels.get('q1', week_phrase.upper()).replace(' ', '<br>')}</div>" + build_spider_html(q1_hints)

                # Part 2 Q2
                q2_html = l1_data.get('q2', {}).get('html', '')
                bs2 = bs4.BeautifulSoup(q2_html, 'html.parser')
                p2 = bs2.find('p')
                ctx['l1_q2_prompt'] = format_bullet_text(str(p2), bold_question=True) if p2 else ""
                ctx['l1_q2_spider'] = f"<div class=\"spider-center\" style=\"background: var(--bg-pastel-blue); color: black;\">{labels.get('q2', week_phrase.upper()).replace(' ', '<br>')}</div>" + build_spider_html(l1_data.get('q2', {}).get('spider_diagram_hints', []))

                # Part 2 Q3
                q3_html = l1_data.get('q3', {}).get('html', '')
                bs3 = bs4.BeautifulSoup(q3_html, 'html.parser')
                p3 = bs3.find('p')
                ctx['l1_q3_prompt'] = format_bullet_text(str(p3), bold_question=True) if p3 else ""
                ctx['l1_q3_spider'] = f"<div class=\"spider-center\" style=\"background: var(--bg-pastel-blue); color: black;\">{labels.get('q3', week_phrase.upper()).replace(' ', '<br>')}</div>" + build_spider_html(l1_data.get('q3', {}).get('spider_diagram_hints', []))

                # Part 3 (Q1-Q6)
                l2_data = week_data.get('lesson_2_part_3', {})
                for key in ['q1', 'q2', 'q3', 'q4', 'q5', 'q6']:
                    q_info = l2_data.get(key, {})
                    html_content = q_info.get('html', '')
                    b = bs4.BeautifulSoup(html_content, 'html.parser')
                    b_ps = b.find_all('p')
                    if len(b_ps) >= 1:
                        q_text = b_ps[0].get_text().strip().replace(f"{key.upper()}: ", "").replace(f"{key.upper()}:", "")
                        ctx[f'l2_{key}_title'] = f"{key.upper()}: {q_text}"
                    else: ctx[f'l2_{key}_title'] = f"{key.upper()}: "

                    ctx[f'l2_{key}_model'] = "".join([str(x) for x in b_ps[1].contents]) if len(b_ps) >= 2 else ""

                    hints_html = ""
                    for hint in q_info.get('ore_hints', []): hints_html += f"<li>{hint}</li>"
                    ctx[f'l2_{key}_scaffold'] = hints_html

                    p_q_data = week_peer.get(key, {})
                    b5_q = p_q_data.get('band_5_peer_question', '')
                    b6_q = p_q_data.get('band_6_plus_peer_question', '')
                    ctx[f'l2_{key}_b5'] = f"📉 <strong>Band 5 Peer Check:</strong> Ask: '{b5_q}'" if b5_q else ""
                    ctx[f'l2_{key}_b6'] = f"📈 <strong>Band 6 Peer Check:</strong> Ask: '{b6_q}'" if b6_q else ""

                # Homework
                # We need a quick mock for homework vocab review table
                hw_vocab_html = ""
                words_list = []
                synonyms_list = []
                for item in week_homework.get('vocab_review', []):
                    words_list.append(item.get('word', ''))
                    synonyms_list.append({"option": item.get('option', ''), "synonym": item.get('synonym', '')})
                random.shuffle(synonyms_list)
                for i in range(len(words_list)):
                    word = words_list[i]
                    opt = synonyms_list[i]['option'] if i < len(synonyms_list) else "?"
                    syn = synonyms_list[i]['synonym'] if i < len(synonyms_list) else "?"
                    row = f"<td style='padding: 12px 5px;'>{i+1}. {word}</td><td style='border-bottom:1px solid #eee;'></td><td style='padding: 12px 5px;'>( &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ) {opt}. {syn}</td>"
                    hw_vocab_html += f"<tr>{row}</tr>"
                ctx['hw_vocab_tbody'] = hw_vocab_html

                hw_grammar_html = ""
                for i, item in enumerate(week_homework.get('grammar_clinic', [])):
                    hw_grammar_html += f"<div class='grammar-sent'>{i+1}. {item.get('error', '')}</div>"
                ctx['hw_grammar_html'] = hw_grammar_html

                # Critical Instruction Fix!
                wt_text = week_homework.get('writing_task', '')
                ctx['hw_writing_html'] = f"<h3>3. Writing Task: {wt_text} (10 minutes)</h3><div style=\"background:white; border-radius:8px; padding:12px; margin-top:5px; box-shadow:0 2px 4px rgba(0,0,0,0.05);\"><div style=\"font-weight:bold; color:#444; margin-bottom:5px;\">📝 Instructions:</div><ol style=\"margin:0; padding-left:20px; font-size:0.9em; color:#555;\"><li>Go to the next Page (that woul be page 10)</li><li>Write your first draft in the top box.</li><li>Use AI to correct grammar/vocabulary.</li><li>Write the polished version in the bottom box.</li></ol></div>"

                ctx['hw_recording_html'] = """<h3 style="color:var(--hw-accent); margin:0 0 10px 0; border-bottom:1px solid #ddd; padding-bottom:5px;">🎙️ 4. Recording Challenge</h3>
        <div style="font-size:0.85em; line-height:1.5; color:#333; display:flex; flex-direction:column; gap:10px;">
            <div>
                <strong>Part 1: AI Shadow Reading (20 mins)</strong>
                <div style="margin-top:5px; padding-left:10px; border-left:3px solid #3498db;">
                    <strong>Task A - Pre Shadowing:</strong> Using the AI APP, Choose a US or UK accent and Shadow Read all model answers for next week (10 mins).<br>
                    <strong>Task B - Memorise</strong> all next weeks vocabulary and idioms (5 mins).<br>
                    <strong>Task C - Tongue Twisters:</strong> Use the AI APP for Pronunciation Practice (5 mins).
                </div>
            </div>
            <div>
                <strong>Part 2: Speaking Practice (20 Minutes)</strong>
                <div style="margin-top:5px; padding-left:10px; border-left:3px solid #e74c3c;">
                    <strong>Task A -</strong> Use the AI APP to record and submit your answers for all 3 Part 2 Speaking questions for this week (3 X 2 Minutes)<br>
                    <strong>Task B -</strong> Use the AI APP to record and submit your answers for all Part 3 Question (6 X 1 minute)<br>
                    <div style="margin-top:5px; font-weight:bold; color:#c0392b;">DO NOT READ YOUR ANSWERS INTO THE APP.</div>
                    <div style="font-style:italic;">Use complex sentences, transition phrases and this weeks vocabulary and idioms.</div>
                </div>
            </div>
        </div>"""
                ctx['hw_answer_key'] = week_homework.get('answer_key', '')

                # Render HTML
                html_out = template.render(**ctx)

                # Final pass string replacements for things jinja couldn't easily catch without a complex template
                # But Jinja replaces everything we mapped.

                # Write to file
                with open(f'lessons/Week_{week_num}_Lesson_Plan.html', 'w', encoding='utf-8') as f:
                    f.write(html_out)

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