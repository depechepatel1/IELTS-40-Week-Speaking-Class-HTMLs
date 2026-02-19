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
    },
    22: {
        "entrepreneurial": "有创业精神的", "diligent": "勤奋的", "authentic": "正宗的", "prosperous": "繁荣的",
        "reputable": "声誉好的", "dedicated": "敬业的", "exceptional": "杰出的 (service)",
        "run the show": "掌管", "pass the torch": "薪火相传", "mom and pop store": "夫妻店",
        "corporation": "大公司", "competition": "竞争", "monopoly": "垄断", "economy": "经济",
        "startup": "初创公司", "innate": "固有的 (risk)", "potential": "潜力", "cut-throat": "残酷的 (竞争)",
        "go out of business": "破产", "big fish eat little fish": "大鱼吃小鱼"
    },
    23: {
        "nostalgic": "怀旧的", "imaginative": "富于想象的", "durable": "耐用的", "precious": "珍贵的",
        "educational": "有教育意义的", "authentic": "真实的 (memories)", "prosperous": "富裕的 (childhood)",
        "child's play": "小儿科", "trip down memory lane": "追忆往昔", "pride and joy": "掌上明珠",
        "creativity": "创造力", "development": "发展", "socialization": "社会化", "cognitive": "认知的",
        "interaction": "互动", "competition": "竞争", "economy": "经济 (cost of toys)",
        "spoiled brat": "被宠坏的孩子", "wrap someone in cotton wool": "过分保护", "play by the rules": "遵守规则"
    },
    24: {
        "frustrated": "沮丧的", "helpless": "无助的", "unexpected": "意想不到的", "inconvenient": "不便的",
        "urgent": "紧急的", "durable": "耐用的 (not durable)", "precious": "宝贵的 (time)",
        "in the dark": "蒙在鼓里", "out of order": "故障", "save the day": "挽救局面",
        "dependency": "依赖", "obsolescence": "废弃", "reliability": "可靠性", "manufacturing": "制造业",
        "sustainability": "可持续性", "development": "发展", "creativity": "创造力 (solving problems)",
        "throwaway culture": "用完即弃的文化", "wear and tear": "磨损", "don't fix what isn't broken": "没坏就别修 (多一事不如少一事)"
    },
    25: {
        "persuasive": "有说服力的", "reluctant": "不情愿的", "supportive": "支持的", "appreciative": "感激的",
        "wise": "明智的", "frustrated": "沮丧的", "urgent": "紧急的", "talk someone into something": "说服某人做某事",
        "give it a shot": "试一试", "two heads are better than one": "三个臭皮匠顶个诸葛亮",
        "guidance": "指导", "mentorship": "导师制度", "motivation": "动力", "criticism": "批评",
        "leadership": "领导力", "reliability": "可靠性", "dependency": "依赖", "peer pressure": "同伴压力",
        "lead by example": "以身作则", "constructive criticism": "建设性批评"
    },
    26: {
        "attentive": "体贴的", "impeccable": "无懈可击的", "satisfied": "满意的", "courteous": "礼貌的",
        "efficient": "高效的", "persuasive": "有说服力的 (sales)", "appreciative": "感激的",
        "go above and beyond": "超越期望", "with a smile": "面带微笑", "treat someone like royalty": "奉若上宾",
        "automation": "自动化", "transaction": "交易", "budgeting": "预算", "consumption": "消费",
        "hospitality": "好客", "guidance": "指导", "motivation": "动机 (to buy)",
        "the customer is always right": "顾客就是上帝", "human touch": "人情味", "bang for your buck": "物超所值"
    },
    27: {
        "entertaining": "有趣的", "informative": "信息量大的", "addictive": "令人上瘾的", "viral": "病毒式传播的",
        "engaging": "引人入胜的", "attentive": "专注的", "impeccable": "完美的", "binge-watch": "刷剧",
        "scroll through": "浏览", "blow up": "突然爆红", "censorship": "审查", "misinformation": "错误信息",
        "algorithm": "算法", "connectivity": "连接性", "mainstream": "主流的", "consumption": "消费 (media)",
        "automation": "自动化", "fake news": "假新闻", "go viral": "疯传", "couch potato": "电视迷 (懒惰的人)"
    },
    28: {
        "lively": "热闹的", "delicious": "美味的", "memorable": "难忘的", "sociable": "善于交际的",
        "awkward": "尴尬的", "entertaining": "有趣的", "engaging": "吸引人的", "break the ice": "打破僵局",
        "life of the party": "聚会的灵魂人物", "have a blast": "玩得很开心", "tradition": "传统",
        "community": "社区", "celebration": "庆祝", "isolation": "孤立", "etiquette": "礼节",
        "connectivity": "联系", "mainstream": "主流的", "let one's hair down": "放松",
        "quality time": "珍贵的相处时光", "the more the merrier": "人越多越好"
    },
    29: {
        "sincere": "真诚的", "regretful": "后悔的", "honest": "诚实的", "forgiving": "宽容的",
        "courageous": "勇敢的", "awkward": "尴尬的", "sociable": "善交际的", "swallow one's pride": "放下自尊",
        "clear the air": "消除误会", "get something off one's chest": "吐露心声", "integrity": "正直",
        "deception": "欺骗", "morality": "道德", "conflict": "冲突", "resolution": "解决",
        "etiquette": "礼节", "community": "社区", "white lie": "善意的谎言",
        "honesty is the best policy": "诚实是上策", "bury the hatchet": "言归于好"
    },
    30: {
        "fascinating": "迷人的", "endangered": "濒危的", "wild": "野生的", "majestic": "雄伟的",
        "unique": "独特的", "courageous": "勇敢的 (to approach)", "sincere": "真诚的 (interest)",
        "face to face": "面对面", "in the wild": "在野外", "king of the jungle": "丛林之王 (狮子)",
        "ecosystem": "生态系统", "extinction": "灭绝", "captivity": "圈养", "biodiversity": "生物多样性",
        "conservation": "保护", "morality": "道德", "conflict": "冲突 (human-animal)",
        "survival of the fittest": "适者生存", "crocodile tears": "鳄鱼的眼泪 (假慈悲)",
        "let sleeping dogs lie": "莫惹是非"
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
        21: 'batch21_week21.json',
        22: 'batch22_week22.json',
        23: 'batch23_week23.json',
        24: 'batch24_week24.json',
        25: 'batch25_week25.json',
        26: 'batch26_week26.json',
        27: 'batch27_week27.json',
        28: 'batch28_week28.json',
        29: 'batch29_week29.json',
        30: 'batch30_week30.json'
    }

    for week, fname in files_map.items():
        process_file(fname, week)
