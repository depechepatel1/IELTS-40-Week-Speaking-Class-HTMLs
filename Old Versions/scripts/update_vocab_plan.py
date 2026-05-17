
import json
import re

def get_pos(word, forms):
    word_lower = word.lower()
    forms_lower = forms.lower()
    
    # Check if POS already exists
    if "(" in word and ")" in word:
        return word # Already tagged
        
    # Heuristics based on common suffixes
    pos = ""
    
    # Noun suffixes
    if word_lower.endswith(('tion', 'sion', 'ment', 'ness', 'ity', 'ance', 'ence', 'ism', 'ship', 'cy', 'age', 'ure', 'logy', 'dom')):
        pos = "N"
    # Adjective suffixes
    elif word_lower.endswith(('ous', 'ive', 'ent', 'ant', 'ful', 'less', 'able', 'ible', 'ic', 'al', 'y', 'ish', 'ary')):
        pos = "Adj"
    # Verb suffixes
    elif word_lower.endswith(('ate', 'ise', 'ize', 'fy')):
        pos = "V"
    # Adverb
    elif word_lower.endswith('ly'):
        pos = "Adv"
        
    # Check 'forms' field for explicit label
    if not pos:
        if "adjective" in forms_lower or "adj" in forms_lower:
            pos = "Adj"
        elif "noun" in forms_lower or " n)" in forms_lower or "(n)" in forms_lower or forms_lower.startswith("noun"):
            pos = "N"
        elif "verb" in forms_lower or " v)" in forms_lower or "(v)" in forms_lower:
            pos = "V"

    # Specific overrides for Week 1 & others
    overrides = {
        "Diligent": "Adj", "Inspiring": "Adj", "Selfless": "Adj", "Accomplished": "Adj",
        "Considerate": "Adj", "Generous": "Adj", "Devoted": "Adj",
        "Generation gap": "N", "Instill": "V", "Perspective": "N", "Breadwinner": "N",
        "Harmony": "N", "Appreciate": "V", "Guidance": "N",
        "Cosmopolitan": "Adj", "Lucrative": "Adj", "Immerse": "V", "Adaptable": "Adj",
        "Barrier": "N", "Globalization": "N", "Integration": "N", "Discrimination": "N",
        "Brain drain": "N", "Prosperous": "Adj", 
        "Fulfilling": "Adj", "Challenging": "Adj", "Prestigious": "Adj", "Demanding": "Adj",
        "Qualified": "Adj", "Automation": "N", "Job security": "N", "Unemployment": "N",
        "Motivation": "N", "Work-life balance": "N",
        "Anticipated": "Adj", "Predictable": "Adj", "Mediocre": "Adj", "Overrated": "Adj",
        "Confusing": "Adj", "Cinematography": "N", "Genre": "N", "Influence": "N",
        "Blockbuster": "N", "Censorship": "N"
    }
    
    if word in overrides:
        pos = overrides[word]
        
    if pos:
        return f"{word} ({pos})"
    return word

def update_vocab():
    with open('vocab_plan.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for week in data:
        # L1
        for item in week.get('l1_vocab', []):
            item['word'] = get_pos(item['word'], item.get('forms', ''))
            
        # L2
        for item in week.get('l2_vocab', []):
            item['word'] = get_pos(item['word'], item.get('forms', ''))
            
    with open('vocab_plan.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print("Updated vocab_plan.json with POS tags.")

if __name__ == "__main__":
    update_vocab()
