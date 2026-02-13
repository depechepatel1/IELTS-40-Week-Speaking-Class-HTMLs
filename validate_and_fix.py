4. audit_vocab.py
import json
import re

def load_data(filename):
    with open(f"ielts_content_generation/{filename}", "r", encoding="utf-8") as f:
        return json.load(f)

def audit_word_families(vocab_list, lesson_name):
    print(f"\n--- Auditing {lesson_name} ---")
    issues_found = False

    for item in vocab_list:
        word = item["word"]
        forms = item["Word Forms"]
        pos = re.search(r'\((.*?)\)', word)
        pos_tag = pos.group(1) if pos else "Unknown"

        # Check for Adjective families
        if "Adj" in pos_tag:
            # Expect Noun (N) or Adverb (Adv) or Verb (V)
            # This is a heuristic. Not all adjectives have adverbs, but most do.
            if "(Adv)" not in forms and "ly" not in word: # Skip if word itself ends in ly like 'friendly'
                 # Some adjectives don't have common adverbs (e.g. 'Difficult' -> 'Difficultly' is rare/awkward).
                 # But for 'Generous', 'Generously' is required.
                 pass

            if "(N)" not in forms and "ness" not in forms and "ity" not in forms:
                 # Check if the word itself is Noun/Adj usage?
                 pass

        # STRICT CHECK: Check for empty or very short word forms
        if len(forms) < 5:
            print(f"❌ {word}: Word Forms list is suspiciously short: '{forms}'")
            issues_found = True

        # Check specific known missing forms (Hardcoded based on user feedback)
        if "Generous" in word and "Generously" not in forms:
             print(f"❌ {word}: Missing Adverb form 'Generously'")
             issues_found = True

        if "Inspiring" in word and "Inspiration" not in forms:
             print(f"❌ {word}: Missing Noun form 'Inspiration'")
             issues_found = True

    if not issues_found:
        print("✅ Word families look reasonably complete.")

def audit_idiom_examples(idiom_list, lesson_name):
    print(f"\n--- Auditing {lesson_name} Idioms ---")
    issues = False
    for item in idiom_list:
        if "example" not in item or len(item["example"]) < 10:
            print(f"❌ {item['idiom']}: Missing or too short example sentence.")
            issues = True

    if not issues:
        print("✅ All idioms have example sentences.")

def main():
    data = load_data("vocab_plan.txt")
    week1 = [w for w in data if w["week"] == 1][0]

    audit_word_families(week1["l1_vocab"], "Week 1 Lesson 1 Vocab")
    audit_idiom_examples(week1["l1_idioms"], "Week 1 Lesson 1 Idioms")

    audit_word_families(week1["l2_vocab"], "Week 1 Lesson 2 Vocab")
    audit_idiom_examples(week1["l2_idioms"], "Week 1 Lesson 2 Idioms")

if __name__ == "__main__":
    main()
Displayed audit_vocab.py.

5. vocab_plan.txt (Week 1 Snippet)
(Full file is long, showing the Week 1 structure which includes the new example fields and updated word forms)

[
  {
    "week": 1,
    "l1_vocab": [
      {
        "word": "Diligent (Adj)",
        "Word Forms": "Diligence (N) - Diligently (Adv)",
        "meaning": "勤奋的",
        "recycled": false
      },
      {
        "word": "Inspiring (Adj)",
        "Word Forms": "Inspire (V1) - Inspired (V2/V3) - Inspiration (N) - Inspiringly (Adv)",
        "meaning": "鼓舞人心的",
        "recycled": false
      },
      {
        "word": "Selfless (Adj)",
        "Word Forms": "Selflessly (Adv) - Selflessness (N)",
        "meaning": "无私的",
        "recycled": false
      },
      {
        "word": "Accomplished (Adj)",
        "Word Forms": "Accomplish (V1) - Accomplished (V2/V3) - Accomplishment (N)",
        "meaning": "有造诣的 / 成功的",
        "recycled": false
      },
      {
        "word": "Considerate (Adj)",
        "Word Forms": "Consider (V1) - Considered (V2/V3) - Consideration (N) - Considerately (Adv)",
        "meaning": "体贴的",
        "recycled": false
      },
      {
        "word": "Generous (Adj)",
        "Word Forms": "Generosity (N) - Generously (Adv)",
        "meaning": "慷慨的",
        "recycled": true
      },
      {
        "word": "Devoted (Adj)",
        "Word Forms": "Devote (V1) - Devoted (V2/V3) - Devotion (N) - Devotedly (Adv)",
        "meaning": "挚爱的 / 忠诚的",
        "recycled": true
      }
    ],
    "l1_idioms": [
      {
        "idiom": "Go the extra mile",
        "usage": "Go (V1) - Went (V2) - Gone (V3)",
        "meaning": "加倍努力",
        "cn_idiom": "再接再厉",
        "example": "To get a high band score, I am willing to go the extra mile in my studies."
      },
      {
        "idiom": "Look up to",
        "usage": "Look (V1) - Looked (V2/V3)",
        "meaning": "敬仰",
        "cn_idiom": "仰视",
        "example": "I really look up to my father because he works so hard for our family."
      },
      {
        "idiom": "A heart of gold",
        "usage": "Fixed Phrase",
        "meaning": "心地善良",
        "cn_idiom": "菩萨心肠",
        "example": "My grandmother has a heart of gold; she always helps everyone in the village."
      }
    ],
    "l2_vocab": [
      {
        "word": "Generation gap (N)",
        "Word Forms": "Generational (Adj)",
        "meaning": "代沟",
        "recycled": false
      },
      {
        "word": "Instill (V)",
        "Word Forms": "Instill (V1) - Instilled (V2/V3) - Instillation (N)",
        "meaning": "灌输 (价值观)",
        "recycled": false
      },
      {
        "word": "Perspective (N)",
        "Word Forms": "Perspectives (Pl)",
        "meaning": "观点 / 视角",
        "recycled": false
      },
      {
        "word": "Breadwinner (N)",
        "Word Forms": "Breadwinners (Pl)",
        "meaning": "养家糊口的人",
        "recycled": false
      },
      {
        "word": "Harmony (N)",
        "Word Forms": "Harmonious (Adj) - Harmoniously (Adv)",
        "meaning": "和谐",
        "recycled": false
      },
      {
        "word": "Appreciate (V)",
        "Word Forms": "Appreciate (V1) - Appreciated (V2/V3) - Appreciation (N) - Appreciative (Adj)",
        "meaning": "感激 / 欣赏",
        "recycled": true
      },
      {
        "word": "Guidance (N)",
        "Word Forms": "Guide (V1) - Guided (V2/V3)",
        "meaning": "指导",
        "recycled": true
      }
    ],
    "l2_idioms": [
      {
        "idiom": "Follow in someone's footsteps",
        "usage": "Follow (V1) - Followed (V2/V3)",
        "meaning": "继承衣钵 / 效法",
        "cn_idiom": "步人后尘 (neutral sense)",
        "example": "I plan to follow in my father's footsteps and become a doctor."
      },
      {
        "idiom": "The apple doesn't fall far from the tree",
        "usage": "Proverb",
        "meaning": "有其父必有其子",
        "cn_idiom": "有其父必有其子",
        "example": "He is just as stubborn as his dad; the apple doesn't fall far from the tree."
      },
      {
        "idiom": "Flesh and blood",
        "usage": "Noun Phrase",
        "meaning": "骨肉 / 亲人",
        "cn_idiom": "骨肉至亲",
        "example": "I must help him because he is my own flesh and blood."
      }
    ]
  }
]