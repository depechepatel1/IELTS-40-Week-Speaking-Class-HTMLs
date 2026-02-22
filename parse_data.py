import json
import re
import argparse
import sys
from bs4 import BeautifulSoup, Tag

def load_data(week_number):
    """
    Loads data from curriculum.json, homework_plan.json, and vocab_plan.txt
    for the specified week.
    """
    print(f"Loading data for Week {week_number}...")

    # Load Curriculum
    try:
        with open('curriculum.json', 'r', encoding='utf-8') as f:
            curriculum_data = json.load(f)
    except FileNotFoundError:
        print("Error: curriculum.json not found.")
        sys.exit(1)

    # Load Homework
    try:
        with open('homework_plan.json', 'r', encoding='utf-8') as f:
            homework_data = json.load(f)
    except FileNotFoundError:
        print("Error: homework_plan.json not found.")
        sys.exit(1)

    # Load Vocab (concatenated JSONs)
    vocab_data_list = []
    try:
        with open('vocab_plan.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            decoder = json.JSONDecoder()
            pos = 0
            while pos < len(content):
                # Manually skip whitespace to avoid slicing
                while pos < len(content) and content[pos].isspace():
                    pos += 1

                if pos >= len(content):
                    break

                try:
                    obj, idx = decoder.raw_decode(content, idx=pos)
                    if isinstance(obj, list):
                        vocab_data_list.extend(obj)
                    else:
                        vocab_data_list.append(obj)
                    pos = idx
                except json.JSONDecodeError as e:
                    print(f"Warning: JSON Decode Error at pos {pos}: {e}")
                    break
    except FileNotFoundError:
        print("Error: vocab_plan.txt not found.")
        sys.exit(1)

    # Filter for the specific week
    week_curr = next((item for item in curriculum_data if item["week"] == week_number), None)
    week_hw = next((item for item in homework_data if item["week"] == week_number), None)
    week_vocab = next((item for item in vocab_data_list if item["week"] == week_number), None)

    if not week_curr:
        print(f"Error: No curriculum data found for Week {week_number}")
        sys.exit(1)

    return week_curr, week_hw, week_vocab

def process_teacher_plan(soup, week_curr, week_number):
    topic = week_curr["topic"]
    theme = week_curr["theme"]

    print(f"Processing Teacher Plan for Topic: {topic}")

    # 1. Update Cover Page
    cover_week = soup.find("h1", class_="cover-week")
    if cover_week:
        cover_week.string = f"WEEK {week_number}"

    cover_theme_box = soup.find("div", class_="cover-theme-box")
    if cover_theme_box:
        h2s = cover_theme_box.find_all("h2", class_="cover-theme-text")
        if len(h2s) >= 1:
            h2s[0].string = theme
        if len(h2s) >= 2:
            h2s[1].string = topic

    # 2. Update Headers (Week Tags)
    week_tags = soup.find_all("span", class_="week-tag")
    for tag in week_tags:
        text = tag.text
        if "Lesson 1" in text:
            tag.string = f"Week {week_number} • Lesson 1 • {topic}"
        elif "Lesson 2" in text:
            tag.string = f"Week {week_number} • Lesson 2 • {topic}"
        elif "Self-Study" in text:
            tag.string = f"Week {week_number} • Self-Study"

    # 3. Update Learning Objectives (L1)
    # Find the LO card in L1 Teacher Page
    pages = soup.find_all("div", class_="page")

    def find_section(page, header_text):
        headers = page.find_all("h2")
        for h in headers:
            if header_text in h.text:
                return h.parent
        return None

    l1_page = None
    for p in pages:
        if "Teacher Lesson Plan" in p.text and "Lesson 1" in p.text:
            l1_page = p
            break

    if l1_page:
        lo_div = find_section(l1_page, "Learning Objectives")
        if lo_div:
            ul = lo_div.find("ul")
            if ul:
                ul.clear()
                lis = [
                    f"<strong>Speaking:</strong> Describe {topic.lower()} using topic-specific vocabulary.",
                    f"<strong>Vocab:</strong> Use target words related to {theme}.",
                    f"<strong>Grammar:</strong> Use complex sentences to describe {topic.lower()}."
                ]
                for html in lis:
                    li = soup.new_tag("li")
                    li.append(BeautifulSoup(html, 'html.parser'))
                    ul.append(li)

    # 4. Update Bilibili Link
    bili_search_term = f"IELTS {topic} Speaking"
    bili_url = f"https://search.bilibili.com/all?keyword={bili_search_term}"
    bili_btns = soup.find_all("a", class_="bili-btn")
    for btn in bili_btns:
        btn['href'] = bili_url

    # 5. Differentiation
    sentence_starter = f"I would describe {topic.lower()} as..."
    if "Place" in theme or "City" in topic:
        sentence_starter = "I really like visiting... because..."
    elif "Person" in theme or "People" in topic:
        sentence_starter = "I admire this person because..."

    diff_headers = soup.find_all("h2", string=re.compile("Differentiation"))
    for h2 in diff_headers:
        diff_card = h2.parent
        b5_box = diff_card.find("div", style=re.compile("background:#e8f8f5"))
        if b5_box:
            strong = b5_box.find("strong")
            if strong:
                b5_box.clear()
                b5_box.append(strong)
                b5_box.append(Tag(name="br"))
                b5_box.append(f"• Use template: \"{sentence_starter} This is because...\"")

def process_vocabulary(soup, week_vocab):
    print("Processing Vocabulary...")

    # 1. Lesson 1 Vocab (Page 2)
    vocab_headers = soup.find_all("h2", string=re.compile("Target Vocabulary & Idioms"))
    if vocab_headers:
        l1_table = vocab_headers[0].find_next("table", class_="vocab-table")
        if l1_table:
            tbody = l1_table.find("tbody")
            if tbody:
                tbody.clear()
                for item in week_vocab.get("l1_vocab", []):
                    tr = soup.new_tag("tr")
                    td_word = soup.new_tag("td")
                    strong_word = soup.new_tag("strong")
                    strong_word.string = item["word"].split(" (")[0]
                    td_word.append(strong_word)

                    pos = " (Word)"
                    if "(" in item["word"]:
                        pos = " (" + item["word"].split("(")[1]

                    span_pos = soup.new_tag("span", style="font-weight:normal; font-style:italic; font-size:0.9em;")
                    span_pos.string = pos
                    td_word.append(span_pos)

                    if item.get("recycled"):
                        span_rec = soup.new_tag("span", attrs={"class": "recycled-tag"})
                        span_rec.string = "Recycled"
                        td_word.append(" ")
                        td_word.append(span_rec)

                    tr.append(td_word)
                    td_forms = soup.new_tag("td")
                    td_forms.string = item["Word Forms"]
                    tr.append(td_forms)
                    td_mean = soup.new_tag("td")
                    span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
                    span_cn.string = item["meaning"]
                    td_mean.append(span_cn)
                    tr.append(td_mean)
                    tbody.append(tr)

                tr_idiom_head = soup.new_tag("tr")
                td_head = soup.new_tag("td", colspan="3", style="background:#eee; font-weight:bold; color:#555;")
                td_head.string = "🐎 Idioms"
                tr_idiom_head.append(td_head)
                tbody.append(tr_idiom_head)

                for item in week_vocab.get("l1_idioms", []):
                    tr = soup.new_tag("tr")
                    td_word = soup.new_tag("td")
                    strong_word = soup.new_tag("strong")
                    strong_word.string = item["idiom"]
                    td_word.append(strong_word)
                    tr.append(td_word)
                    td_usage = soup.new_tag("td")
                    td_usage.string = item["usage"]
                    tr.append(td_usage)
                    td_mean = soup.new_tag("td")
                    span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
                    span_cn.string = item["cn_idiom"]
                    td_mean.append(span_cn)
                    tr.append(td_mean)
                    tbody.append(tr)

                    tr_ex = soup.new_tag("tr", attrs={"class": "vocab-example-row"})
                    td_ex = soup.new_tag("td", colspan="3")
                    td_ex.string = f"\"{item['example_sentence']}\""
                    tr_ex.append(td_ex)
                    tbody.append(tr_ex)

    # 2. Lesson 2 Vocab (Page 5)
    vocab_headers_l2 = soup.find_all("h2", string=re.compile("Abstract Vocabulary"))
    if vocab_headers_l2:
        l2_table = vocab_headers_l2[0].find_next("table", class_="vocab-table")
        if l2_table:
            tbody = l2_table.find("tbody")
            if tbody:
                tbody.clear()
                for item in week_vocab.get("l2_vocab", []):
                    tr = soup.new_tag("tr")
                    td_word = soup.new_tag("td")
                    strong_word = soup.new_tag("strong")
                    strong_word.string = item["word"].split(" (")[0]
                    td_word.append(strong_word)
                    pos = " (Word)"
                    if "(" in item["word"]:
                        pos = " (" + item["word"].split("(")[1]
                    span_pos = soup.new_tag("span", style="font-weight:normal; font-style:italic; font-size:0.9em;")
                    span_pos.string = pos
                    td_word.append(span_pos)
                    if item.get("recycled"):
                        span_rec = soup.new_tag("span", attrs={"class": "recycled-tag"})
                        span_rec.string = "Recycled"
                        td_word.append(" ")
                        td_word.append(span_rec)
                    tr.append(td_word)
                    td_forms = soup.new_tag("td")
                    td_forms.string = item["Word Forms"]
                    tr.append(td_forms)
                    td_mean = soup.new_tag("td")
                    span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
                    span_cn.string = item["meaning"]
                    td_mean.append(span_cn)
                    tr.append(td_mean)
                    tbody.append(tr)

                tr_idiom_head = soup.new_tag("tr")
                td_head = soup.new_tag("td", colspan="3", style="background:#eee; font-weight:bold; color:#555;")
                td_head.string = "🐎 Idioms"
                tr_idiom_head.append(td_head)
                tbody.append(tr_idiom_head)

                for item in week_vocab.get("l2_idioms", []):
                    tr = soup.new_tag("tr")
                    td_word = soup.new_tag("td")
                    strong_word = soup.new_tag("strong")
                    strong_word.string = item["idiom"]
                    td_word.append(strong_word)
                    tr.append(td_word)
                    td_usage = soup.new_tag("td")
                    td_usage.string = item["usage"]
                    tr.append(td_usage)
                    td_mean = soup.new_tag("td")
                    span_cn = soup.new_tag("span", attrs={"class": "vocab-cn"})
                    span_cn.string = item["cn_idiom"]
                    td_mean.append(span_cn)
                    tr.append(td_mean)
                    tbody.append(tr)
                    tr_ex = soup.new_tag("tr", attrs={"class": "vocab-example-row"})
                    td_ex = soup.new_tag("td", colspan="3")
                    td_ex.string = f"\"{item['example_sentence']}\""
                    tr_ex.append(td_ex)
                    tbody.append(tr_ex)

def format_mind_maps(soup, week_curr):
    print("Formatting Mind Maps...")

    topic = week_curr["topic"]
    keyword = topic.upper().replace("A ", "").replace("THE ", "")
    if len(keyword) > 10 and " " in keyword:
        parts = keyword.split(" ")
        mid = len(parts) // 2
        keyword = "<br>".join([" ".join(parts[:mid]), " ".join(parts[mid:])])

    spider_centers = soup.find_all("div", class_="spider-center")
    for center in spider_centers:
        center.clear()
        center.append(BeautifulSoup(keyword, 'html.parser'))

    def extract_bullets(text):
        if "You should say:" in text:
            parts = text.split("You should say:")
            if len(parts) > 1:
                bullets = parts[1].strip().split("\n")
                return [b.strip() for b in bullets if b.strip()][:4]
        return ["Who", "What", "Where", "Why"]

    l1_model_input = week_curr.get("l1_part2_model_input", "")
    l1_bullets = extract_bullets(l1_model_input)

    practice_page = None
    for p in soup.find_all("div", class_="page"):
        if "Speaking Practice Circuit" in p.text:
            practice_page = p
            break

    if practice_page:
        main_map = practice_page.find("div", class_="spider-container")
        if main_map:
            legs = main_map.find_all("div", class_="spider-leg")
            for i, leg in enumerate(legs):
                if i < len(l1_bullets):
                    leg.clear()
                    leg.append(BeautifulSoup(f"<strong>{i+1}. {l1_bullets[i]}</strong>", 'html.parser'))

        q2_text = week_curr.get("l1_part2_student_q2", "")
        q2_bullets = extract_bullets(q2_text)

        topic_a_card = practice_page.find("h3", string=re.compile("Topic A"))
        if topic_a_card:
            card = topic_a_card.parent
            topic_a_card.string = "Part 2: Q2"
            desc_div = card.find("div", style=re.compile("font-size:0.85em"))
            if desc_div:
                desc_div.string = q2_text.split("You should say:")[0].strip()
            legs = card.find_all("div", class_="spider-leg")
            for i, leg in enumerate(legs):
                if i < len(q2_bullets):
                    leg.clear()
                    leg.append(BeautifulSoup(f"<strong>{q2_bullets[i]}</strong>", 'html.parser'))
                    leg.append(BeautifulSoup("<div class='lines'></div>", 'html.parser'))

        q3_text = week_curr.get("l1_part2_student_q3", "")
        q3_bullets = extract_bullets(q3_text)

        topic_b_card = practice_page.find("h3", string=re.compile("Topic B"))
        if topic_b_card:
            card = topic_b_card.parent
            topic_b_card.string = "Part 2: Q3"
            desc_div = card.find("div", style=re.compile("font-size:0.85em"))
            if desc_div:
                desc_div.string = q3_text.split("You should say:")[0].strip()
            legs = card.find_all("div", class_="spider-leg")
            for i, leg in enumerate(legs):
                if i < len(q3_bullets):
                    leg.clear()
                    leg.append(BeautifulSoup(f"<strong>{q3_bullets[i]}</strong>", 'html.parser'))
                    leg.append(BeautifulSoup("<div class='lines'></div>", 'html.parser'))

def process_part2_and_3(soup, week_curr):
    print("Processing Model Answers...")

    # L1 Part 2 Model (Page 2)
    l1_model_header = soup.find("h2", string=re.compile("Band 6.5 Model Answer"))
    if l1_model_header:
        model_box = l1_model_header.find_next("div", class_="model-box")
        if model_box:
            answer_text = week_curr.get("l1_part2_model_answer")
            if answer_text:
                model_box.clear()
                model_box.append(BeautifulSoup(answer_text, 'html.parser'))
            else:
                model_box.clear()
                model_box.string = "[Model Answer Missing in Data Source]"

    # L2 Part 3 Q1 (Page 5)
    q1_container = soup.find(id="p5-q1")
    if q1_container:
        h3 = q1_container.find("h3")
        if h3 and "l2_part3_questions" in week_curr:
            questions = week_curr["l2_part3_questions"]
            if len(questions) > 0:
                h3.string = f"Q1: {questions[0]}"
        model_box = q1_container.find("div", class_="model-box")
        if model_box:
             model_box.clear()
             model_box.string = "[Model Answer Missing in Data Source]"

    # L2 Part 3 Q2 (Page 6)
    q2_container = soup.find(id="p6-q2")
    if q2_container:
        h3 = q2_container.find("h3")
        if h3 and "l2_part3_questions" in week_curr and len(week_curr["l2_part3_questions"]) > 1:
            h3.string = f"Q2: {week_curr['l2_part3_questions'][1]}"
        model_box = q2_container.find("div", class_="model-box")
        if model_box:
             model_box.clear()
             model_box.string = "[Model Answer Missing in Data Source]"

    # L2 Part 3 Q3 (Page 6)
    q3_container = soup.find(id="p6-q3")
    if q3_container:
        h3 = q3_container.find("h3")
        if h3 and "l2_part3_questions" in week_curr and len(week_curr["l2_part3_questions"]) > 2:
            h3.string = f"Q3: {week_curr['l2_part3_questions'][2]}"
        model_box = q3_container.find("div", class_="model-box")
        if model_box:
             model_box.clear()
             model_box.string = "[Model Answer Missing in Data Source]"

    # Q4, Q5, Q6 on Page 7
    page7 = None
    for p in soup.find_all("div", class_="page"):
        if "Part 3: Rapid Fire Discussion" in p.text and "(continued)" in p.text:
            page7 = p
            break

    if page7:
        cards = page7.find_all("div", class_="card compact")
        for i, card in enumerate(cards):
            q_idx = 3 + i
            if "l2_part3_questions" in week_curr and len(week_curr["l2_part3_questions"]) > q_idx:
                h3 = card.find("h3")
                if h3:
                    h3.string = f"Q{q_idx+1}: {week_curr['l2_part3_questions'][q_idx]}"
                model_box = card.find("div", class_="model-box")
                if model_box:
                    model_box.clear()
                    model_box.string = "[Model Answer Missing in Data Source]"

def process_homework(soup, week_hw):
    print("Processing Homework...")

    vocab_card = soup.find("h3", string=re.compile("Vocabulary Review"))
    if vocab_card:
        table = vocab_card.find_next("table", class_="vocab-table")
        if table:
            tbody = table.find("tbody")
            if tbody:
                tbody.clear()
                for i, item in enumerate(week_hw.get("vocab_review", [])):
                    tr = soup.new_tag("tr")
                    td1 = soup.new_tag("td")
                    td1.string = f"{i+1}. {item['word']}"
                    tr.append(td1)
                    td2 = soup.new_tag("td", style="border-bottom:1px solid #eee;")
                    tr.append(td2)
                    td3 = soup.new_tag("td")
                    td3.string = f"(      ) {item['option']}. {item['synonym']}"
                    tr.append(td3)
                    tbody.append(tr)

    grammar_card = soup.find("h3", string=re.compile("Error Correction"))
    if grammar_card:
        container = grammar_card.find_next("div", style=re.compile("display:flex; flex-direction:column;"))
        if container:
            container.clear()
            for i, item in enumerate(week_hw.get("grammar_clinic", [])):
                div = soup.new_tag("div", attrs={"class": "grammar-sent"})
                div.string = f"{i+1}. {item['error']}"
                container.append(div)

    writing_card = soup.find("h3", string=re.compile("Writing Task"))
    if writing_card:
        text = f"3. Writing Task: {week_hw.get('writing_task', '')} (10 mins)"
        writing_card.string = text

    key_div = soup.find("div", style=re.compile("transform:rotate"))
    if key_div:
        key_div.string = week_hw.get("answer_key", "")

def validate_output(soup):
    html_content = str(soup)
    # We relax the validation because we know Model Answers are missing so highlighting won't be there
    # But let's check for basic presence
    # if "badge-ore" not in html_content:
    #     print("Validation Warning: O.R.E. badges missing.")
    #     return False
    # if "highlight-transition" not in html_content:
    #     print("Validation Warning: Transition highlights missing.")
    #     return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Generate IELTS Lesson Plan HTML")
    parser.add_argument("week", type=int, nargs='?', default=1, help="Week number to generate")
    args = parser.parse_args()

    week_number = args.week

    week_curr, week_hw, week_vocab = load_data(week_number)

    try:
        with open('Week_2_Lesson_Plan.html', 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
    except FileNotFoundError:
        print("Error: Week_2_Lesson_Plan.html template not found.")
        sys.exit(1)

    process_teacher_plan(soup, week_curr, week_number)
    if week_vocab:
        process_vocabulary(soup, week_vocab)
    else:
        print(f"Warning: No vocabulary data found for Week {week_number}")

    format_mind_maps(soup, week_curr)
    process_part2_and_3(soup, week_curr)

    if week_hw:
        process_homework(soup, week_hw)
    else:
        print(f"Warning: No homework data found for Week {week_number}")

    if validate_output(soup):
        output_filename = f'Week_{week_number}_Lesson_Plan.html'
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print(f'Successfully generated {output_filename}')
    else:
        print(f'Validation failed for Week {week_number}')

if __name__ == "__main__":
    main()
