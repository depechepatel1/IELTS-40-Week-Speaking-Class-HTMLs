import json
import re
import sys

# Update the dictionary to include new "difficult" words found in Weeks 6-9 drafts
# if they are not covered by the vocabulary list itself (which is already glossed in the drafts).
# The drafts ALREADY have glosses for target vocab (e.g. "Tranquil [宁静的]").
# We need to gloss OTHER difficult words like "absolutely", "located", "atmosphere", "navigate", "invents", "ancestors", etc.

GLOSS_DICT = {
    # Week 1-5 Refined list (keep existing)
    "commence": "开始",
    "undoubtedly": "毫无疑问地",
    "devoted": "忠诚的/致力于",
    "considerate": "体贴的",
    "selfless": "无私的",
    "generous": "慷慨的",
    "strove": "努力",
    "harmony": "和谐",
    "breadwinner": "养家糊口的人",
    "perspective": "观点/视角",
    "optimism": "乐观",
    "appreciate": "感激/欣赏",
    "bridged": "弥合/消除",
    "generation gap": "代沟",
    "inherently": "天生地/固有地",
    "reputation": "名声",
    "contemporary": "当代的",
    "status": "地位",
    "flesh and blood": "骨肉/亲人",
    "guidance": "指导",
    "instill": "灌输",
    "cosmopolitan": "世界性的",
    "lucrative": "利润丰厚的",
    "immerse": "沉浸",
    "barrier": "障碍",
    "adaptable": "适应性强的",
    "culture shock": "水土不服",
    "diligent": "勤奋的",
    "start from scratch": "白手起家",
    "broaden one's horizons": "开阔眼界",
    "globalization": "全球化",
    "integration": "融合",
    "prosperous": "繁荣的",
    "discrimination": "歧视",
    "insurmountable": "不可逾越的",
    "melting pot": "大熔炉",
    "brain drain": "人才流失",
    "expatriates": "外籍人士",
    "prestigious": "有声望的",
    "fulfilling": "令人满足的",
    "qualified": "有资格的",
    "challenging": "充满挑战的",
    "demanding": "要求高的",
    "climb the career ladder": "在职业阶梯上攀升",
    "make a living": "谋生",
    "dream job": "理想工作",
    "job security": "工作保障",
    "unemployment": "失业",
    "work-life balance": "工作与生活的平衡",
    "motivation": "动力",
    "automation": "自动化",
    "bring home the bacon": "养家糊口",
    "dead-end job": "没前途的工作",
    "think outside the box": "跳出框框思考",
    "burnout": "职业倦怠",
    "venture": "冒险/风险项目",
    "skeptical": "怀疑的",
    "overrated": "被高估的",
    "anticipated": "预期的",
    "hype up": "炒作",
    "predictable": "可预测的",
    "mediocre": "平庸的",
    "confusing": "令人困惑的",
    "let-down": "令人失望",
    "a let-down": "令人失望",
    "waste of time": "浪费时间",
    "cinematography": "摄影",
    "genre": "类型",
    "influence": "影响力",
    "blockbuster": "大片",
    "censorship": "审查",
    "box office hit": "票房大卖",
    "star-studded cast": "全明星阵容",
    "on the edge of one's seat": "扣人心弦",
    "resonate": "共鸣",
    "epics": "史诗电影",
    "heritage": "遗产",
    "conscientious": "认真的/尽责的",
    "eco-friendly": "环保的",
    "passionate": "充满激情的",
    "advocate": "拥护者/提倡",
    "inspiring": "鼓舞人心的",
    "sustainable": "可持续的",
    "biodiversity": "生物多样性",
    "conservation": "保护",
    "pollution": "污染",
    "renewable": "可再生的",
    "extinction": "灭绝",
    "wreak havoc": "造成严重破坏",
    "tip of the iceberg": "冰山一角",
    "a drop in the ocean": "沧海一粟",
    "do one's bit": "尽一份力",
    "practice what you preach": "言行一致",
    "nature lover": "自然爱好者",
    "ecosystem": "生态系统",
    "carbon footprint": "碳足迹",
    
    # Week 6-9 Additions (General academic/descriptive words)
    "absolutely": "绝对地",
    "located": "位于",
    "scenery": "风景",
    "hiking": "徒步旅行",
    "atmosphere": "气氛",
    "virtually": "虚拟地",
    "navigate": "导航",
    "scroll": "滚动",
    "recommend": "推荐",
    "revolutionized": "彻底改变",
    "supervision": "监督",
    "resume": "简历",
    "biased": "有偏见的",
    "incompetent": "无能的",
    "invades": "侵犯",
    "portraits": "肖像",
    "landscapes": "风景画",
    "invents": "发明/创造",
    "well-rounded": "全面发展的",
    "ancestors": "祖先",
    "essential": "基本的/必要的",
    "crucial": "至关重要的",
    "countless": "无数的",
    "prioritize": "优先考虑",
    "timber": "木材",
    "platform": "平台",
    "filters": "滤镜",
    "hackers": "黑客",
    "neutral": "中立的",
    "supplies": "用品",
    "techniques": "技巧",
    "observers": "观察者"
}

SORTED_KEYS = sorted(GLOSS_DICT.keys(), key=len, reverse=True)

def inject_gloss(text):
    if not text:
        return text
    
    for word_key in SORTED_KEYS:
        gloss = GLOSS_DICT[word_key]
        # Regex to match word not followed by existing gloss
        # Also avoid double glossing if word is part of a phrase already glossed (simple heuristic)
        # We look for word boundary, word, boundary, NOT followed by optional space then '['
        pattern = r'\b' + re.escape(word_key) + r'\b(?!\s*\[)'
        
        def replacer(match):
            original_word = match.group(0)
            return f"{original_word} [{gloss}]"
            
        text = re.sub(pattern, replacer, text, flags=re.IGNORECASE)
        
    return text

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        updated = False
        
        for item in data:
            if 'l1_part2_questions' in item:
                for q in item['l1_part2_questions']:
                    if 'model_answer' in q:
                        new_ans = inject_gloss(q['model_answer'])
                        if new_ans != q['model_answer']:
                            q['model_answer'] = new_ans
                            updated = True
                            
            if 'l2_part3_questions' in item:
                for q in item['l2_part3_questions']:
                    if 'model_answer' in q:
                        new_ans = inject_gloss(q['model_answer'])
                        if new_ans != q['model_answer']:
                            q['model_answer'] = new_ans
                            updated = True
                            
                    if 'idea_suggestions' in q:
                        new_suggestions = []
                        for sug in q['idea_suggestions']:
                            new_sug = inject_gloss(sug)
                            if new_sug != sug:
                                updated = True
                            new_suggestions.append(new_sug)
                        q['idea_suggestions'] = new_suggestions

        if updated:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Processed and updated {filepath}")
        else:
            print(f"No changes needed for {filepath}")
            
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    files = [
        'batch10_week10.json',
        'batch11_week11.json',
        'batch12_week12.json',
        'batch13_week13.json'
    ]
    for f in files:
        process_file(f)
