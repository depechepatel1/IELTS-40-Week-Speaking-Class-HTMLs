import json
import re
import sys

# Week-specific vocab glosses
WEEK_VOCAB = {
    18: {
        "cozy": "舒适的", "spacious": "宽敞的", "decorated": "装饰过的", "modern": "现代的",
        "messy": "凌乱的", "supportive": "支持的", "intimate": "私密的",
        "home sweet home": "温馨的家", "make oneself at home": "不拘束", "make yourself at home": "不拘束",
        "peace and quiet": "宁静",
        "affordability": "可负担性", "urban": "城市的", "shortage": "短缺", "investment": "投资", "regulation": "法规",
        "lifelong": "终身的", "superficial": "表面的",
        "get on the property ladder": "买第一套房", "go through the roof": "价格飞涨", "a roof over one's head": "栖身之所"
    },
    19: {
        "consumerism": "消费主义", "materialistic": "物质主义的", "nostalgia": "怀旧",
        "sustainability": "可持续性", "accumulate": "积累", "investment": "投资", "affordability": "购买力",
        "one man's trash is another man's treasure": "变废为宝",
        "hoarder": "囤积狂", "throwaway society": "用完即弃的社会", "can't live without": "不能没有"
    },
    20: {
        "exhausting": "筋疲力尽的", "scenic": "风景优美的", "adventurous": "爱冒险的",
        "spontaneous": "随性的", "delayed": "延误的", "sentimental": "情感的", "valuable": "宝贵的",
        "hit the road": "上路", "travel light": "轻装上阵", "bumpy ride": "颠簸的旅程",
        "eco-tourism": "生态旅游", "emission": "排放", "commute": "通勤", "congestion": "拥堵",
        "preparation": "准备", "carbon footprint": "碳足迹", "hustle and bustle": "熙熙攘攘", "rush hour": "高峰期"
    },
    21: {
        "exceptional": "杰出的", "innovative": "创新的", "dedicated": "专注的", "versatile": "多才多艺的",
        "visionary": "有远见的", "adventurous": "敢于创新的", "spontaneous": "自发的",
        "born with a silver spoon": "含着金汤匙出生", "think on one's feet": "反应敏捷", "think on their feet": "反应敏捷",
        "a natural": "天生好手", "innate": "天生的", "potential": "潜力", "nurture": "培养",
        "academic": "学术的", "intelligence": "智力", "preparation": "准备", "ingenuity": "独创性",
        "practice makes perfect": "熟能生巧", "brainy": "聪明的", "jack of all trades": "万金油"
    }
}

def inject_gloss(text, week_num):
    if not text:
        return text

    vocab_map = WEEK_VOCAB.get(week_num, {})
    sorted_keys = sorted(vocab_map.keys(), key=len, reverse=True)

    for word_key in sorted_keys:
        gloss = vocab_map[word_key]
        pattern = r'\b' + re.escape(word_key) + r'\b(?!\s*\[)'

        def replacer(match):
            original_word = match.group(0)
            return f"{original_word} [{gloss}]"

        text = re.sub(pattern, replacer, text, flags=re.IGNORECASE)

    return text

def process_file(filepath, week_num):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        updated = False

        for item in data:
            # Handle Nested Structure (part2 list, part3 list)
            if 'part2' in item:
                for q in item['part2']:
                    if 'model_answer' in q:
                        original = q['model_answer']
                        new_text = inject_gloss(original, week_num)
                        if new_text != original:
                            q['model_answer'] = new_text
                            updated = True

            if 'part3' in item:
                for q in item['part3']:
                    if 'model_answer' in q:
                        original = q['model_answer']
                        new_text = inject_gloss(original, week_num)
                        if new_text != original:
                            q['model_answer'] = new_text
                            updated = True

        if updated:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Processed and updated {filepath}")
        else:
            print(f"No changes needed for {filepath}")

    except Exception as e:
        print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    files_map = {
        18: 'batch18_week18.json',
        19: 'batch19_week19.json',
        20: 'batch20_week20.json',
        21: 'batch21_week21.json'
    }

    for week, fname in files_map.items():
        process_file(fname, week)
