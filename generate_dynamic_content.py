
import json
import random

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def generate_l1_content(week_data, vocab_data, week_num):
    topic = week_data.get('topic', 'General Topic')
    theme = week_data.get('theme', 'General Theme')

    # Extract first vocab word for example
    l1_vocab = vocab_data.get('l1_vocab', [])
    target_word = l1_vocab[0]['word'] if l1_vocab else "Target Word"

    # Differentiation Strategy
    if "People" in theme:
        b5_starter = "My favorite person is..."
        b6_trans = "'Additionally...', 'Furthermore...'"
        lead_in_q = "Do you spend much time with your family?"
    elif "Places" in theme:
        b5_starter = "I would love to visit..."
        b6_trans = "'Consequently...', 'As a result...'"
        lead_in_q = f"Have you ever visited a {topic.lower()}?"
    elif "Events" in theme:
        b5_starter = "I remember when I..."
        b6_trans = "'Subsequently...', 'Eventually...'"
        lead_in_q = f"Do you enjoy {topic.lower()}?"
    elif "Items" in theme:
        b5_starter = "This object is useful because..."
        b6_trans = "'Specifically...', 'For instance...'"
        lead_in_q = f"Do you own a {topic.lower()}?"
    else:
        b5_starter = "I think that..."
        b6_trans = "'Admittedly...', 'Conversely...'"
        lead_in_q = f"What do you know about {topic}?"

    return {
        "learning_objectives": [
            f"<strong>Speaking:</strong> Speak fluently about {topic} using Part 2 structure.",
            f"<strong>Vocab:</strong> Use 7 target words (e.g., <em>{target_word}</em>) in context.",
            f"<strong>Grammar:</strong> Use narrative tenses or relevant grammar for {theme}."
        ],
        "success_criteria": f"\"I can speak for 2 mins about {topic} using 2 idioms.\"",
        "differentiation": {
            "band_5": {
                "starter": b5_starter,
                "peer_check": "Simple generic prompts (e.g., 'Why?')."
            },
            "band_6": {
                "transitions": b6_trans,
                "peer_check": "Topic-specific extension questions."
            }
        },
        "lead_in": {
            "search_term": f"IELTS {topic} Speaking",
            "question": lead_in_q
        }
    }

def generate_l2_content(week_data, vocab_data, week_num):
    topic = week_data.get('topic', 'General Topic')

    # Extract abstract noun
    l2_vocab = vocab_data.get('l2_vocab', [])
    abstract_word = l2_vocab[0]['word'] if l2_vocab else "Abstract Noun"

    return {
        "learning_objectives": [
            "<strong>Logic:</strong> Use O.R.E. logic to answer Part 3 questions.",
            f"<strong>Vocab:</strong> Use Abstract Nouns (e.g., <em>{abstract_word}</em>).",
            f"<strong>Speaking:</strong> Discuss abstract ideas about {topic}."
        ],
        "success_criteria": f"\"I can answer 3 abstract questions about {topic} using O.R.E.\"",
        "differentiation": {
            "band_5": {
                "starter": "In my opinion...",
                "peer_check": "Simple generic prompts (e.g., 'Can you give an example?')."
            },
            "band_6": {
                "transitions": "'Undeniably...', 'It is widely acknowledged that...'",
                "peer_check": "Challenge questions (e.g., 'Is this always true?')."
            }
        },
        "lead_in": {
            "search_term": f"IELTS {topic} Part 3",
            "question": "Do you think this topic is important for society?"
        }
    }

def main():
    curriculum = load_json('master Curiculum.json')
    vocab_plan = load_json('vocab_plan.json')

    vocab_map = {item['week']: item for item in vocab_plan}

    output = {}

    for item in curriculum:
        week_num = item['week']
        vocab = vocab_map.get(week_num, {})

        output[str(week_num)] = {
            "lesson_1": generate_l1_content(item, vocab, week_num),
            "lesson_2": generate_l2_content(item, vocab, week_num)
        }

    with open('teacher_dynamic_content.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Generated dynamic content for {len(output)} weeks.")

if __name__ == "__main__":
    main()
