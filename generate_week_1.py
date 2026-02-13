import json
import re
import sys
from bs4 import BeautifulSoup, NavigableString

# ==========================================
# 1. LOAD DATA
# ==========================================
def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_html(soup, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(str(soup))

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

def create_transition_span(soup, text):
    span = soup.new_tag("span", attrs={"class": "highlight-transition"})
    span.string = text
    return span

def get_part2_topic(curriculum):
    # Topic format: "People (A Family Member You Are Proud Of)"
    topic = curriculum.get('topic', 'Topic')
    if '(' in topic:
        match = re.search(r'\((.*?)\)', topic)
        if match:
            return match.group(1)
    return topic

def get_main_keyword(text):
    # Extract a main keyword from the question or topic
    # E.g., "Describe a family member" -> "FAMILY"

    # Remove Q1. prefix
    text = re.sub(r'^Q\d+\.\s*', '', text)

    ignore_words = {"describe", "a", "an", "the", "time", "when", "you", "your", "who", "what", "where", "how", "why", "q1", "q2", "q3", "q4", "q5", "q6"}
    # Remove punctuation
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    words = clean_text.split()

    candidates = [w for w in words if w not in ignore_words]
    if candidates:
        return candidates[0].upper()
    return "TOPIC"

def format_mind_map_bullets(soup, ul_element, bullets):
    # Format: You should say: Who..., What..., How..., and explain...
    # Input bullets: ["Who: ...", "What: ...", ...]
    # Output: Inline text string

    if not ul_element: return

    # Create the inline text
    # The prompt example: "You should say: Who the person is..., What their personality is like..., How they influenced/helped you..., and explain why they are important to you."
    # The data bullets: ["Who: Mother / Grandfather", "When: Last year", ...]
    # We need to reconstruct the "You should say" text based on the keys of the bullets?
    # Or just join them?
    # The data bullets are short summaries.
    # Actually, the 'question' field in part2 usually doesn't have the "You should say" bullets in the data provided in the snippet.
    # Wait, the snippet showed "bullet_points": ["Who: ...", "When: ..."].
    # It does NOT show the full "You should say" text.
    # So we have to construct it from the bullet points.

    inline_text = "You should say: "
    parts = []
    for i, b in enumerate(bullets):
        # b is like "Who: Mother / Grandfather"
        if ":" in b:
            key, val = b.split(":", 1)
            parts.append(f"{key} {val.strip().lower()}...") # "Who mother / grandfather..."
        else:
            parts.append(f"{b}...")

    if parts:
        # Join with commas, and add "and explain" for the last one if it's "Why"
        if len(parts) > 1 and "why" in parts[-1].lower():
             parts[-1] = "and explain " + parts[-1]

        inline_text += ", ".join(parts)

    # Replace the UL content with this text?
    # The template has <ul class="prompt-bullets"><li>...</li></ul>
    # The prompt says "Change format to: Inline Bullet Points".
    # So we replace the <li>s with a single <li> containing the text?
    # Or just put the text in the <ul> (which is invalid HTML strictly speaking, but browser handles it)
    # Better: <li>[Inline Text]</li>

    ul_element.clear()
    li = soup.new_tag("li")
    li.string = inline_text
    ul_element.append(li)

def update_spider_legs(soup, container, bullets):
    # Update the 4 quadrants
    if not container: return
    legs = container.find_all("div", class_="spider-leg")

    for i, leg in enumerate(legs):
        if i >= len(bullets): break
        bullet = bullets[i]
        # bullet: "Who: Mother / Grandfather"
        if ":" in bullet:
            key, val = bullet.split(":", 1)
            key = key.strip().upper()
            val = val.strip()
            # "give 2 one word suggestions" -> val is "Mother / Grandfather" -> "Mother/Grandpa"
        else:
            key = "POINT"
            val = bullet

        # Update leg content
        # <div class="spider-leg"><strong>1. WHO:</strong><br><span style="color:#777;">Name?</span></div>
        leg.clear()
        strong = soup.new_tag("strong")
        strong.string = f"{i+1}. {key}:"
        leg.append(strong)
        leg.append(soup.new_tag("br"))

        span = soup.new_tag("span", attrs={"style": "color:#777;"})
        # Truncate val if too long?
        span.string = val
        leg.append(span)

def process_model_answer(soup, html_content):
    # Convert provided HTML content to match our styles
    # <span style="color: blue;"> -> <span class="highlight-transition">
    # <span style="background-color: yellow;"> -> Keep or ignore? Prompt doesn't say.
    # But nested spans might be an issue.

    # We'll parse the fragment
    fragment = BeautifulSoup(html_content, "html.parser")

    # 1. Map Blue Text to Transition Class
    for span in fragment.find_all("span"):
        style = span.get("style", "")
        if "color: blue" in style or "color:blue" in style:
            span["class"] = span.get("class", []) + ["highlight-transition"]
            # Remove the color style but keep others?
            # Simplest is to remove style if it only had color
            # But regex replace is safer for specific property
            new_style = re.sub(r'color:\s*blue;?', '', style).strip()
            if new_style:
                span["style"] = new_style
            else:
                del span["style"]

    # 2. Map O.R.E. Badges (for Part 3)
    # Data: <span style="background-color: #e0f7fa; ..."><b>Opinion</b></span>
    # Target: <span class="badge-ore bg-o">Op</span>

    # Heuristic: check text content
    for span in fragment.find_all("span"):
        text = span.get_text().strip().lower()
        if text == "opinion":
            span.name = "span"
            span.attrs = {"class": ["badge-ore", "bg-o"]}
            span.string = "Op"
        elif text == "reason":
            span.name = "span"
            span.attrs = {"class": ["badge-ore", "bg-r"]}
            span.string = "Re"
        elif text == "example":
            span.name = "span"
            span.attrs = {"class": ["badge-ore", "bg-e"]}
            span.string = "Ex"

    # 3. Handle [Chinese] translations in brackets?
    # The data has "Diligent [勤奋的]".
    # The template vocab table handles this separately.
    # In the model answer, maybe we keep it as is.

    # 4. Inject Missing Transitions
    # Check each badge. If not followed by a highlight-transition span, inject one.
    import random
    transitions = {
        "bg-o": ["Personally,", "In my view,", "I believe that"],
        "bg-r": ["This is because", "The main reason is that", "This is due to the fact that"],
        "bg-e": ["For example,", "For instance,", "To illustrate this,"]
    }

    badges = fragment.find_all("span", class_="badge-ore")
    for badge in badges:
        # Determine type
        b_type = None
        for cls in badge["class"]:
            if cls in transitions:
                b_type = cls
                break

        if not b_type: continue

        # Check next sibling
        # Note: next_sibling might be whitespace text
        curr = badge.next_sibling
        is_transition = False
        while curr:
            if isinstance(curr, NavigableString):
                if curr.strip(): # Found text
                    break # It's text, not a span
            elif curr.name == "span" and "highlight-transition" in curr.get("class", []):
                is_transition = True
                break
            elif curr.name == "span":
                 # Check if it has color: blue (redundant if step 1 worked)
                 pass
            curr = curr.next_sibling

        if not is_transition:
            # Inject transition
            trans_text = random.choice(transitions[b_type])
            new_span = soup.new_tag("span", attrs={"class": "highlight-transition"})
            new_span.string = trans_text + " "

            # Insert after badge
            badge.insert_after(new_span)

            # Adjust following text if needed (lowercase first letter?)
            # This is hard on a soup fragment without disrupting structure.
            # We'll just insert it. "This is because Parents..." -> acceptable.

    return fragment

# ==========================================
# 3. MAIN GENERATION LOGIC
# ==========================================
def generate_week_1():
    data = load_json("week_1_data.json")
    curriculum = data.get("curriculum", {})
    vocab = data.get("vocab", {})
    homework = data.get("homework", {})

    with open("Week_1 Jules.html", "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # -------------------------------------
    # PAGE 1: COVER
    # -------------------------------------
    # Week Number is already Week 1 in template, but good to be dynamic
    cover_week = soup.find("h1", class_="cover-week")
    if cover_week: cover_week.string = f"WEEK {curriculum.get('week', 1)}"

    # Themes
    themes = soup.find_all("h2", class_="cover-theme-text")
    if len(themes) >= 1:
        themes[0].string = get_part2_topic(curriculum)
    if len(themes) >= 2:
        # Try to guess Part 3 theme or use generic
        # curriculum.part3[0].question might give a hint
        if curriculum.get("part3"):
             # "What would children do to make their parents proud?" -> "Family & Values"?
             pass
             # For now, leave the second one or set it to something generic if we can't derive it.
             # The template has "Friendship & Social Interaction".
             # If our topic is "Family", maybe "Family & Society"?
             themes[1].string = "Family & Society" # Hardcoded based on Week 1 data context

    # -------------------------------------
    # PAGE 3: TEACHER LESSON PLAN L1
    # -------------------------------------
    # Header
    headers = soup.find_all("div", class_="header-bar")
    # L1 Header is the first one after cover/blank (index 0 is cover? No cover page has no header bar class)
    # The pages are: Cover, Blank, L1 Teacher, L1 Student, ...

    # Update Topic in headers
    # Find headers with "Week 1" and update?
    for header in headers:
        tag = header.find("span", class_="week-tag")
        if tag and "Lesson 1" in tag.get_text():
            tag.string = f"Week {curriculum.get('week')} • Lesson 1 • {get_part2_topic(curriculum)}"

    # LOs
    # Find card with "Learning Objectives"
    # This is brittle, relying on text search.
    # Better: find h2 with text "Learning Objectives"

    # L1 LOs
    l1_page = soup.find_all("div", class_="page l1")[0] # First L1 page is Teacher Plan
    los_h2 = l1_page.find("h2", string=re.compile("Learning Objectives"))
    if los_h2:
        ul = los_h2.find_next("ul")
        if ul:
            lis = ul.find_all("li")
            if len(lis) >= 1: lis[0].clear(); lis[0].append(BeautifulSoup(f"<strong>Speaking:</strong> Describe {get_part2_topic(curriculum)}.", "html.parser"))

    # Differentiation
    diff_h2 = l1_page.find("h2", string=re.compile("Differentiation"))
    if diff_h2:
        # Band 5
        band5 = diff_h2.find_next("div").find("div", style=re.compile("bg-pastel-blue|#e8f8f5"))
        if band5:
            # Inject specific sentence starter?
            # "I would love to visit..." for Travel.
            # For Family: "I really admire my..."
            pass

    # Bilibili Search
    # "IELTS [Topic Name] Speaking"
    search_term = f"IELTS {get_part2_topic(curriculum)} Speaking"
    # Update text in Procedure table
    proc_table = l1_page.find("table", class_="lp-table")
    if proc_table:
        # Find cell with "Search: "
        for td in proc_table.find_all("td"):
            if "Search:" in td.get_text():
                # Replace content
                new_content = td.encode_contents().decode('utf-8')
                new_content = re.sub(r'Search:.*?(\)|<)', f'Search: {search_term})', new_content)
                # Also fix the "Ask:" part if it's generic
                # Template: Ask: "What makes a real friend?"
                # Dynamic: Ask: "What makes a good [Keyword]?"
                keyword = get_main_keyword(get_part2_topic(curriculum)).title()
                new_content = re.sub(r'Ask: ".*?"', f'Ask: "What makes a good {keyword}?"', new_content)

                td.clear()
                td.append(BeautifulSoup(new_content, "html.parser"))

    # -------------------------------------
    # PAGE 4: STUDENT HANDOUT L1 (PART 2)
    # -------------------------------------
    l1_student_page = soup.find_all("div", class_="page l1")[1]

    # Bilibili Link
    bili_btn = l1_student_page.find("a", class_="bili-btn")
    if bili_btn:
        bili_btn['href'] = f"https://search.bilibili.com/all?keyword={search_term.replace(' ', '%20')}"

    # Cue Card
    cue_card_div = l1_student_page.find("h3", string=re.compile("CUE CARD")).parent
    if cue_card_div:
        h3 = cue_card_div.find("h3")
        h3.string = f"📌 CUE CARD: {curriculum['part2'][0]['question']}"

        # Bullet points text
        bullets_div = cue_card_div.find("div", style=True) # The div below h3
        if bullets_div:
            # Construct "You should say..."
            # Using format_mind_map_bullets logic but text only
            bullets = curriculum['part2'][0]['bullet_points']
            # We can reuse the logic but output plain text
            # Or just replace the innerHTML
            # Expected: You should say: Who..., What..., ...
            pass # Use default for now, or update if critical. The prompt implies Mind Map bullets need formatting, but Cue Card text too?
            # Prompt says "Mind Map Formatting... Inline Bullet Points".
            # It doesn't explicitly say Cue Card text box. But let's assume it should match.

    # Model Answer
    model_div = l1_student_page.find("div", class_="model-box")
    if model_div:
        # Inject model answer
        model_html = curriculum['part2'][0]['model_answer']
        processed_model = process_model_answer(soup, model_html)
        model_div.clear()
        model_div.append(processed_model)

    # Vocab Table
    vocab_table = l1_student_page.find("table", class_="vocab-table")
    if vocab_table:
        tbody = vocab_table.find("tbody")
        tbody.clear()

        # Add Vocab
        for v in vocab.get('l1_vocab', []):
            tr = soup.new_tag("tr")
            # Word
            td1 = soup.new_tag("td")
            strong = soup.new_tag("strong")
            strong.string = v['word'] # "Diligent (Adj)"
            td1.append(strong)
            if v.get('recycled'):
                span = soup.new_tag("span", attrs={"class": "recycled-tag"})
                span.string = "Recycled"
                td1.append(span)
            tr.append(td1)

            # Word Forms
            td2 = soup.new_tag("td")
            td2.string = v['Word Forms']
            tr.append(td2)

            # Meaning
            td3 = soup.new_tag("td")
            span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
            span_cn.string = v['meaning']
            td3.append(span_cn)
            tr.append(td3)

            tbody.append(tr)

        # Add Idioms Header
        tr_head = soup.new_tag("tr")
        td_head = soup.new_tag("td", attrs={"colspan": "3", "style": "background:#eee; font-weight:bold; color:#555;"})
        td_head.string = "🐎 Idioms"
        tr_head.append(td_head)
        tbody.append(tr_head)

        # Add Idioms
        for idiom in vocab.get('l1_idioms', []):
            tr = soup.new_tag("tr")

            # Idiom
            td1 = soup.new_tag("td")
            strong = soup.new_tag("strong")
            strong.string = idiom['idiom']
            td1.append(strong)
            tr.append(td1)

            # Usage
            td2 = soup.new_tag("td")
            td2.string = idiom['usage']
            tr.append(td2)

            # Meaning
            td3 = soup.new_tag("td")
            span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
            span_cn.string = idiom['meaning']
            td3.append(span_cn)
            tr.append(td3)

            tbody.append(tr)

            # Example Row
            tr_ex = soup.new_tag("tr", attrs={"class": "vocab-example-row"})
            td_ex = soup.new_tag("td", attrs={"colspan": "3"})
            td_ex.string = f'"{idiom["example"]}"' if "example" in idiom else ""
            tr_ex.append(td_ex)
            tbody.append(tr_ex)

    # -------------------------------------
    # PAGE 5: STUDENT PRACTICE (MIND MAPS)
    # -------------------------------------
    l1_practice_page = soup.find_all("div", class_="page l1")[2]

    # Main Mind Map (Q1)
    # Find card with "Brainstorming Map"
    brainstorm_card = l1_practice_page.find("h2", string=re.compile("Brainstorming Map")).parent

    # Update Bullets (Inline)
    ul_bullets = brainstorm_card.find("ul", class_="prompt-bullets")
    format_mind_map_bullets(soup, ul_bullets, curriculum['part2'][0]['bullet_points'])

    # Update Central Node
    spider_center = brainstorm_card.find("div", class_="spider-center")
    if spider_center:
        # Keyword from topic
        keyword = get_main_keyword(curriculum['part2'][0]['question'])
        spider_center.clear()
        spider_center.append(keyword) # "FAMILY"

    # Update Quadrants
    spider_container = brainstorm_card.find("div", class_="spider-container")
    update_spider_legs(soup, spider_container, curriculum['part2'][0]['bullet_points'])

    # Topics A & B (Q2, Q3)
    # These are in the flex column below
    # We find cards with "Topic A" and "Topic B"
    topic_a_card = l1_practice_page.find("h3", string=re.compile("Topic A")).parent
    topic_b_card = l1_practice_page.find("h3", string=re.compile("Topic B")).parent

    # Process Q2 (Topic A)
    if len(curriculum['part2']) > 1:
        q2 = curriculum['part2'][1]
        h3 = topic_a_card.find("h3")
        h3.string = f"Topic A: {get_main_keyword(q2['question']).title()}" # "Topic A: Accomplished"

        ul = topic_a_card.find("ul", class_="prompt-bullets")
        format_mind_map_bullets(soup, ul, q2['bullet_points'])

        center = topic_a_card.find("div", class_="spider-center")
        center.string = get_main_keyword(q2['question'])

        cont = topic_a_card.find("div", class_="spider-container")
        update_spider_legs(soup, cont, q2['bullet_points'])

    # Process Q3 (Topic B)
    if len(curriculum['part2']) > 2:
        q3 = curriculum['part2'][2]
        h3 = topic_b_card.find("h3")
        h3.string = f"Topic B: {get_main_keyword(q3['question']).title()}"

        ul = topic_b_card.find("ul", class_="prompt-bullets")
        format_mind_map_bullets(soup, ul, q3['bullet_points'])

        center = topic_b_card.find("div", class_="spider-center")
        center.string = get_main_keyword(q3['question'])

        cont = topic_b_card.find("div", class_="spider-container")
        update_spider_legs(soup, cont, q3['bullet_points'])

    # -------------------------------------
    # PAGE 7: STUDENT HANDOUT L2 (PART 3)
    # -------------------------------------
    # Page index: 0=Cover, 1=Blank, 2=TL1, 3=SL1, 4=SL1_Prac, 5=TL2, 6=SL2_Q1
    l2_student_page = soup.find_all("div", class_="page l2")[1] # First is Teacher Plan

    # Vocab Table (Abstract)
    vocab_table = l2_student_page.find("table", class_="vocab-table")
    if vocab_table:
        tbody = vocab_table.find("tbody")
        tbody.clear()

        # Similar logic to L1 vocab
        for v in vocab.get('l2_vocab', []):
            tr = soup.new_tag("tr")
            td1 = soup.new_tag("td")
            strong = soup.new_tag("strong"); strong.string = v['word']; td1.append(strong)
            if v.get('recycled'):
                span = soup.new_tag("span", attrs={"class": "recycled-tag"}); span.string = "Recycled"; td1.append(span)
            tr.append(td1)

            td2 = soup.new_tag("td"); td2.string = v['Word Forms']; tr.append(td2)
            td3 = soup.new_tag("td")
            span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"}); span_cn.string = v['meaning']; td3.append(span_cn)
            tr.append(td3)
            tbody.append(tr)

        # Idioms
        tr_head = soup.new_tag("tr")
        td_head = soup.new_tag("td", attrs={"colspan": "3", "style": "background:#eee; font-weight:bold; color:#555;"})
        td_head.string = "🐎 Idioms"
        tr_head.append(td_head)
        tbody.append(tr_head)

        for idiom in vocab.get('l2_idioms', []):
            tr = soup.new_tag("tr")
            td1 = soup.new_tag("td"); strong = soup.new_tag("strong"); strong.string = idiom['idiom']; td1.append(strong); tr.append(td1)
            td2 = soup.new_tag("td"); td2.string = idiom['usage']; tr.append(td2)
            td3 = soup.new_tag("td"); span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"}); span_cn.string = idiom['meaning']; td3.append(span_cn); tr.append(td3)
            tbody.append(tr)

            tr_ex = soup.new_tag("tr", attrs={"class": "vocab-example-row"})
            td_ex = soup.new_tag("td", attrs={"colspan": "3"})
            td_ex.string = f'"{idiom["example"]}"' if "example" in idiom else ""
            tr_ex.append(td_ex)
            tbody.append(tr_ex)

    # Q1
    q1_div = l2_student_page.find("div", id="p5-q1")
    if q1_div and len(curriculum['part3']) > 0:
        q_data = curriculum['part3'][0]
        h3 = q1_div.find("h3")
        h3.string = f"Q1: {q_data['question'].replace('Q1.', '').strip()}" # Remove Q1. prefix if present

        model_div = q1_div.find("div", class_="model-box")
        model_div.clear()
        model_div.append(process_model_answer(soup, q_data['model_answer']))

        # Update scaffold?
        # The scaffold text <ul><li>...</li></ul> has bullet points.
        # Data has `bullet_points`.
        scaffold_ul = q1_div.find("ul", class_="scaffold-text")
        if scaffold_ul:
            scaffold_ul.clear()
            for b in q_data['bullet_points']:
                li = soup.new_tag("li")
                li.string = b
                scaffold_ul.append(li)

    # -------------------------------------
    # PAGE 8: PART 3 DEEP DIVE (Q2 & Q3)
    # -------------------------------------
    page_8 = soup.find("div", id="page6") # id="page6" in template

    # Q2
    q2_div = page_8.find("div", id="p6-q2")
    if q2_div and len(curriculum['part3']) > 1:
        q_data = curriculum['part3'][1]
        h3 = q2_div.find("h3")
        h3.string = f"Q2: {q_data['question'].replace('Q2.', '').strip()}"

        model_div = q2_div.find("div", class_="model-box")
        model_div.clear()
        model_div.append(process_model_answer(soup, q_data['model_answer']))

        scaffold_ul = q2_div.find("ul", class_="scaffold-text")
        if scaffold_ul:
            scaffold_ul.clear()
            for b in q_data['bullet_points']:
                li = soup.new_tag("li"); li.string = b; scaffold_ul.append(li)

    # Q3
    q3_div = page_8.find("div", id="p6-q3")
    if q3_div and len(curriculum['part3']) > 2:
        q_data = curriculum['part3'][2]
        h3 = q3_div.find("h3")
        h3.string = f"Q3: {q_data['question'].replace('Q3.', '').strip()}"

        model_div = q3_div.find("div", class_="model-box")
        model_div.clear()
        model_div.append(process_model_answer(soup, q_data['model_answer']))

        scaffold_ul = q3_div.find("ul", class_="scaffold-text")
        if scaffold_ul:
            scaffold_ul.clear()
            for b in q_data['bullet_points']:
                li = soup.new_tag("li"); li.string = b; scaffold_ul.append(li)

    # -------------------------------------
    # PAGE 9: PART 3 RAPID FIRE (Q4-Q6)
    # -------------------------------------
    # The last L2 page
    l2_rapid_page = soup.find_all("div", class_="page l2")[-1]

    # We assume there are 3 cards for Q4, Q5, Q6
    compact_cards = l2_rapid_page.find_all("div", class_="card compact")

    for i, card in enumerate(compact_cards):
        # Data index start at 3 (Q4)
        data_idx = 3 + i
        if data_idx < len(curriculum['part3']):
            q_data = curriculum['part3'][data_idx]
            h3 = card.find("h3")
            h3.string = f"Q{4+i}: {q_data['question'].replace(f'Q{4+i}.', '').strip()}"

            model_div = card.find("div", class_="model-box")
            model_div.clear()
            model_div.append(process_model_answer(soup, q_data['model_answer']))

            scaffold_ul = card.find("ul", class_="scaffold-text")
            if scaffold_ul:
                scaffold_ul.clear()
                for b in q_data['bullet_points']:
                    li = soup.new_tag("li"); li.string = b; scaffold_ul.append(li)

    # -------------------------------------
    # PAGE 10: HOMEWORK
    # -------------------------------------
    hw_page = soup.find("div", class_="page hw")

    # Vocab Review
    # Find table inside the first card (approx)
    # Better: find table with "Synonym" header
    hw_tables = hw_page.find_all("table", class_="vocab-table")
    vocab_review_table = None
    for tbl in hw_tables:
        if "Synonym" in tbl.get_text():
            vocab_review_table = tbl
            break

    if vocab_review_table and 'vocab_review' in homework:
        tbody = vocab_review_table.find("tbody")
        tbody.clear()
        for item in homework['vocab_review']:
            tr = soup.new_tag("tr")
            td1 = soup.new_tag("td"); td1.string = item['word']; tr.append(td1) # Check numbering?
            td2 = soup.new_tag("td", style="border-bottom:1px solid #eee;"); tr.append(td2)
            td3 = soup.new_tag("td")
            td3.string = f"(      ) {item['option']}. {item['synonym']}"
            tr.append(td3)
            tbody.append(tr)

    # Grammar Clinic
    # Find div with "Error Correction"
    grammar_card = hw_page.find("h3", string=re.compile("Error Correction")).parent
    grammar_container = grammar_card.find("div", style=re.compile("flex-direction:column"))

    if grammar_container and 'grammar_clinic' in homework:
        grammar_container.clear()
        for i, item in enumerate(homework['grammar_clinic']):
            div = soup.new_tag("div", attrs={"class": "grammar-sent"})
            div.string = f"{i+1}. {item['error']}"
            grammar_container.append(div)

    # Key (at bottom)
    key_div = hw_page.find("div", style=re.compile("rotate"))
    if key_div:
        # Construct key text
        # Key: 1. Word-Opt, ... | 1. correction...
        v_keys = []
        for i, item in enumerate(homework.get('vocab_review', [])):
            v_keys.append(f"{i+1}. {item['word']}-{item['option']}")

        g_keys = []
        for i, item in enumerate(homework.get('grammar_clinic', [])):
            g_keys.append(f"{i+1}. {item['key']}")

        key_text = "Key: " + ", ".join(v_keys) + " | " + ", ".join(g_keys)
        key_div.string = key_text

    # Writing Task
    # Update title: "3. Writing Task: Describe [Topic]"
    writing_h3 = hw_page.find("h3", string=re.compile("Writing Task"))
    if writing_h3:
        writing_h3.string = f"3. Writing Task: Describe {get_part2_topic(curriculum)} (17 mins)"

    # SAVE
    save_html(soup, "Week_1_Generated.html")
    print("✅ Week 1 HTML Generated successfully: Week_1_Generated.html")

if __name__ == "__main__":
    generate_week_1()
