from bs4 import BeautifulSoup
import re

def build_template():
    with open('Week_1_Lesson_Plan.html', 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # ==========================================
    # Structural Layout Fixes (Do once here)
    # ==========================================

    # Move Writing Page to end
    blank_page = soup.find('div', class_='blank-page')
    if blank_page:
        blank_page['class'] = ['page', 'hw']
        blank_page.clear()
        header_html = '<div class="header-bar"><span class="header-title">✍️ Writing Homework</span><span class="week-tag">Draft & Polished Rewrite</span></div>'
        blank_page.append(BeautifulSoup(header_html, 'html.parser'))
        title = soup.new_tag('h2')
        title.string = "Writing Homework"
        title['style'] = "text-align:center; margin-top:10px; color:var(--primary-color);"
        blank_page.append(title)
        content_html = '<div style="display:flex; flex-direction:column; gap:20px; flex-grow:1; height:100%; padding-bottom:10px;"><div class="card" style="flex:1; display:flex; flex-direction:column; background:var(--bg-pastel-green); border:1px solid #ccc;"><h3 style="margin:0 0 5px 0; color:#555;">Draft Written Homework</h3><div class="lines" style="flex-grow:1; height:auto; width:100%;"></div></div><div class="card" style="flex:1; display:flex; flex-direction:column; background:var(--bg-pastel-green); border:1px solid #ccc;"><h3 style="margin:0 0 5px 0; color:#555;">Polished Rewrite</h3><div class="lines" style="flex-grow:1; height:auto; width:100%;"></div></div></div>'
        blank_page.append(BeautifulSoup(content_html, 'html.parser'))
        blank_page.extract()
        soup.body.append(blank_page)

    # Page 6 Adjustments
    page6 = soup.find('div', id='page6')
    if page6:
        q1_cont = page6.find('div', id='p6-q1-cont')
        if q1_cont: q1_cont.decompose()
        q2 = page6.find('div', id='p6-q2')
        q3 = page6.find('div', id='p6-q3')
        if q2: q2['style'] = "flex:1; display:flex; flex-direction:column;"
        if q3: q3['style'] = "flex:1; display:flex; flex-direction:column;"

    # Page 7 Adjustments
    l2_pages = soup.find_all('div', class_='l2')
    if len(l2_pages) >= 2:
        page9 = l2_pages[-1]
        banner = page9.find('div', class_='header-bar')
        if banner: banner['style'] = "margin-top: 5mm; margin-bottom: 0px;"
        cards = page9.find_all('div', class_='card')
        for card in cards:
            card['style'] = (card.get('style', '') or '') + "; margin-bottom: 5px;"
        stack = page9.find('div', style=lambda x: x and 'display:flex' in x and 'gap:15px' in x)
        if stack: stack['style'] = stack['style'].replace('gap:15px', 'gap:5px').replace('padding: 0 15px 20px 15px', 'padding: 0;')

    # ==========================================
    # Inject Jinja Placeholders
    # ==========================================

    if soup.title: soup.title.string = "{{ page_title }}"

    # Cover
    cover_week = soup.find('h1', class_='cover-week')
    if cover_week: cover_week.string = "{{ cover_week }}"
    cover_title = soup.find('h2', class_='cover-title-large')
    if cover_title:
        cover_title.string = "{{ cover_theme }}"
        cover_title['style'] = "font-size: 5em; text-decoration: none; border-bottom: none;"
    cover_sub = soup.find('div', class_='cover-subtitle')
    if cover_sub: cover_sub.string = "{{ cover_topic }}"

    # Replace Bilibili Links
    for a in soup.find_all('a', class_='bili-btn'):
        a['href'] = "{{ bilibili_url }}"

    # Replace Header Tags
    for tag in soup.find_all('span', class_='week-tag'):
        if 'Lesson 1' in tag.text: tag.string = "{{ l1_week_tag }}"
        elif 'Lesson 2' in tag.text: tag.string = "{{ l2_week_tag }}"

    # Lesson 1 Teacher Plan
    l1_page = soup.find('div', class_='l1')
    if l1_page:
        lo_card = l1_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                lis = ul.find_all('li')
                if len(lis) >= 3:
                    lis[0].string = "{{ l1_lo_speaking }}"
                    lis[1].string = "{{ l1_lo_vocab }}"
                    lis[2].string = "{{ l1_lo_grammar }}"

        crit_card = l1_page.find('h2', string=re.compile(r'Criteria')).parent
        if crit_card: crit_card.find('div').string = "{{ l1_criteria }}"

        diff_card = l1_page.find('h2', string=re.compile(r'Differentiation')).parent
        if diff_card:
            b5 = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if b5: b5.string = "{{ l1_diff_b5 }}"
            b6 = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if b6: b6.string = "{{ l1_diff_b6 }}"

        lp_table = l1_page.find('table', class_='lp-table')
        if lp_table:
            rows = lp_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 1:
                    if "Lead-in" in cells[1].text: cells[1].string = "{{ l1_leadin }}"
                    elif "Input" in cells[1].text: cells[1].string = "{{ l1_input }}"

    # Lesson 2 Teacher Plan
    l2_teacher_page = l2_pages[0] if l2_pages else None
    if l2_teacher_page:
        lo_card = l2_teacher_page.find('h2', string=re.compile(r'Learning Objectives')).parent
        if lo_card:
            ul = lo_card.find('ul')
            if ul:
                lis = ul.find_all('li')
                if len(lis) >= 3:
                    lis[2].string = "{{ l2_lo_speaking }}"
                    lis[1].string = "{{ l2_lo_vocab }}"

        crit_card = l2_teacher_page.find('h2', string=re.compile(r'Criteria')).parent
        if crit_card: crit_card.find('div').string = "{{ l2_criteria }}"

        diff_card = l2_teacher_page.find('h2', string=re.compile(r'Differentiation')).parent
        if diff_card:
            b5 = diff_card.find('div', style=lambda x: x and 'background:#e8f8f5' in x)
            if b5: b5.string = "{{ l2_diff_b5 }}"
            b6 = diff_card.find('div', style=lambda x: x and 'background:#fef9e7' in x)
            if b6: b6.string = "{{ l2_diff_b6 }}"

    # Vocab Tables
    tables = soup.find_all('table', class_='vocab-table')
    if len(tables) >= 1: tables[0].find('tbody').string = "{{ l1_vocab_tbody }}"
    if len(tables) >= 2: tables[1].find('tbody').string = "{{ l2_vocab_tbody }}"
    if len(tables) >= 3: tables[2].find('tbody').string = "{{ hw_vocab_tbody }}" # Homework

    # Student L1 (Part 2)
    part2_banner = soup.find('span', class_='header-title', string=re.compile(r'Part 2:'))
    if part2_banner: part2_banner.string = "{{ part2_banner_title }}"

    cue = soup.find('div', style=lambda x: x and 'border-left:5px solid #fbc02d' in x)
    if cue: cue.string = "{{ l1_q1_cue_html }}"

    # We will replace the entire card contents for Q1, Q2, Q3 models to keep it simple.
    # Actually, let's just replace the prompt div and model box.
    def inject_l1_card(card, q_num):
        if not card: return
        model_box = card.find('div', class_='model-box')
        if model_box: model_box.string = f"{{{{ l1_q{q_num}_model }}}}"

    q1_model_card = soup.find('div', class_='l1').find_next_sibling('div', class_='l1') # Get student L1 page
    if q1_model_card:
        model_box = q1_model_card.find('div', class_='model-box')
        if model_box: model_box.string = "{{ l1_q1_model }}"

    q2_card = soup.find('h3', string=re.compile(r'Part 2: Q2')).parent
    if q2_card:
        prompt_div = q2_card.find('div', style=lambda x: x and 'color:#444' in x)
        if prompt_div: prompt_div.string = "{{ l1_q2_prompt }}"
        spider = q2_card.find('div', class_='spider-container')
        if spider: spider.string = "{{ l1_q2_spider }}"

    q3_card = soup.find('h3', string=re.compile(r'Part 2: Q3')).parent
    if q3_card:
        prompt_div = q3_card.find('div', style=lambda x: x and 'color:#444' in x)
        if prompt_div: prompt_div.string = "{{ l1_q3_prompt }}"
        spider = q3_card.find('div', class_='spider-container')
        if spider: spider.string = "{{ l1_q3_spider }}"

    # Q1 Spider
    q1_spider_card = soup.find('h2', string=re.compile(r'Brainstorming Map')).parent
    if q1_spider_card:
        prompt_div = q1_spider_card.find('div', style=lambda x: x and 'color:#444' in x)
        if prompt_div: prompt_div.string = "{{ l1_q1_spider_prompt }}"
        spider = q1_spider_card.find('div', class_='spider-container')
        if spider: spider.string = "{{ l1_q1_spider }}"

    # Student L2 (Part 3)
    for q_key in ['q1', 'q2', 'q3', 'q4', 'q5', 'q6']:
        card = soup.find('div', id=f'p5-{q_key}') or soup.find('div', id=f'p6-{q_key}')
        if not card:
            # Try finding by h3
            h3 = soup.find('h3', string=re.compile(f'{q_key.upper()}:'))
            if h3: card = h3.parent

        if card:
            h3 = card.find('h3')
            if h3: h3.string = f"{{{{ l2_{q_key}_title }}}}"

            model = card.find('div', class_='model-box')
            if model: model.string = f"{{{{ l2_{q_key}_model }}}}"

            scaffold = card.find('ul', class_='scaffold-text')
            if scaffold: scaffold.string = f"{{{{ l2_{q_key}_scaffold }}}}"

            b5 = card.find('strong', string=re.compile(r'Band 5 Peer Check'))
            if b5 and b5.parent: b5.parent.string = f"{{{{ l2_{q_key}_b5 }}}}"

            b6 = card.find('strong', string=re.compile(r'Band 6 Peer Check'))
            if b6 and b6.parent: b6.parent.string = f"{{{{ l2_{q_key}_b6 }}}}"

    # Homework Page
    hw_page = soup.find('div', class_='hw')
    if hw_page:
        sec1 = hw_page.find('h3', string=re.compile(r'Vocabulary Review')).parent
        if sec1: sec1['style'] = "flex:1; border-left:5px solid var(--hw-accent); background: var(--bg-pastel-green);"

        sec2 = hw_page.find('h3', string=re.compile(r'Error Correction')).parent
        if sec2:
            sec2['style'] = "flex:1; border-left:5px solid var(--hw-accent); background: var(--bg-pastel-green);"
            sec2.find('div', style=lambda x: x and 'display:flex' in x).string = "{{ hw_grammar_html }}"

        sec3 = hw_page.find('h3', string=re.compile(r'Writing Task')).parent
        if sec3:
            sec3.string = "{{ hw_writing_html }}"
            sec3['style'] = "flex-grow:1; border-left:5px solid var(--hw-accent); background: var(--bg-pastel-green); display:flex; flex-direction:column; justify-content:center;"

        sec4 = hw_page.find('h3', string=re.compile(r'Recording Challenge')).parent
        if sec4:
            sec4.string = "{{ hw_recording_html }}"
            sec4['style'] = "flex-grow:1; border-left:5px solid var(--hw-accent); background: var(--bg-pastel-green); border-radius:12px; padding:10px; display:flex; flex-direction:column; justify-content:center;"

        key_div = hw_page.find('div', style=lambda x: x and 'transform:rotate(180deg)' in x)
        if key_div: key_div.string = "{{ hw_answer_key }}"

    # Save Template
    # We must unescape the jinja brackets since BeautifulSoup escapes them
    html_str = str(soup)
    html_str = html_str.replace('&lt;td&gt;', '<td>').replace('&lt;/td&gt;', '</td>')
    html_str = html_str.replace('&lt;tr&gt;', '<tr>').replace('&lt;/tr&gt;', '</tr>')
    html_str = re.sub(r'&lt;\{\{\s*', '{{ ', html_str)
    html_str = re.sub(r'\s*\}\}&gt;', ' }}', html_str)
    # Actually BS just escapes < and >, but we set .string which escapes.
    # Let's just do a blanket unescape for Jinja tags
    import html
    html_str = html.unescape(html_str)

    with open('template.j2', 'w', encoding='utf-8') as f:
        f.write(html_str)
    print("Template generated successfully.")

if __name__ == '__main__':
    build_template()