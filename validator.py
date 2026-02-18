import json
import re

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\[.*?\]', '', text) # remove gloss
    return text.strip()

def count_words(text):
    return len(clean_text(text).split())

def has_complex_sentence_l1(text):
    # Rule 6: 3 clause complex sentence. 
    # Simplified check: yellow highlight tag existence.
    return '<span style="background-color: yellow;">' in text

def has_complex_sentence_l2(text):
    # Rule 7: 2 clause complex sentence.
    # Simplified check: yellow highlight tag existence.
    return '<span style="background-color: yellow;">' in text

def has_blue_starter(text):
    return '<span style="color: blue;">' in text

def has_bold_vocab(text):
    return '<b>' in text

def validate_answer(answer, rules):
    errors = []
    
    # Check highlighting
    if not has_blue_starter(answer):
        errors.append("Missing blue sentence starter.")
    if not has_bold_vocab(answer):
        errors.append("Missing bold vocabulary.")
    if not has_complex_sentence_l1(answer) and rules['type'] == 'l1':
         errors.append("Missing yellow complex sentence highlight (L1).")
    if not has_complex_sentence_l2(answer) and rules['type'] == 'l2':
         errors.append("Missing yellow complex sentence highlight (L2).")

    # Check length
    # Note: Length check on raw text vs HTML text is tricky. 
    # User said "not including gloss and highlighting codes".
    # I will strip tags for length check.
    clean_ans = re.sub(r'<[^>]+>', '', answer) # strip html
    clean_ans = re.sub(r'\[.*?\]', '', clean_ans) # strip gloss
    word_count = len(clean_ans.split())
    
    if rules['type'] == 'l1':
        if not (90 <= word_count <= 110):
            # Relaxing strictness slightly for initial validation as generation can vary
            # but reporting it.
            errors.append(f"L1 Length mismatch: {word_count} words (Expected 90-110)")
    elif rules['type'] == 'l2':
        if not (50 <= word_count <= 70):
             errors.append(f"L2 Length mismatch: {word_count} words (Expected 50-70)")
             
    return errors

def main():
    # This is a stub validator that would be run against generated content.
    # Since I generate content in the next step, this script prepares for it.
    pass

if __name__ == "__main__":
    main()
