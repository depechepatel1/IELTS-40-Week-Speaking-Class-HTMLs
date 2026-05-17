
import json
import random
import re

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def clean_article(text):
    """Removes leading 'a ' or 'an ' from text to avoid double articles."""
    return re.sub(r'^(a|an)\s+', '', text, flags=re.IGNORECASE)

def generate_l1_content(week_data, vocab_data, week_num):
    topic = week_data.get('topic', 'General Topic')
    theme = week_data.get('theme', 'General Theme')
    
    # Extract first vocab word for example
    l1_vocab = vocab_data.get('l1_vocab', [])
    target_word = l1_vocab[0]['word'] if l1_vocab else "Target Word"
    
    clean_topic = clean_article(topic)
    topic_lower = clean_topic.lower()

    # Contextualized Lead-in
    lead_in_q = f"What comes to mind when you think about {topic_lower}?" # Default
    if "Family" in topic or "Person" in topic or "Friend" in topic:
        lead_in_q = f"Do you think {topic_lower} is important in your life?"
    elif "Place" in topic or "Country" in topic or "City" in topic:
        lead_in_q = f"Have you ever visited {clean_article(topic)}?" # e.g. Have you ever visited a foreign country? -> Have you ever visited foreign country? (wait, keep article if needed or rely on topic having it)
        # Actually topic usually is "A Foreign Country". clean_topic is "Foreign Country".
        # So "Have you ever visited Foreign Country" is weird. "Have you ever visited a Foreign Country" is better.
        # But if topic is "Shopping Mall", "Have you ever visited Shopping Mall" is bad.
        # Let's use specific logic.
        lead_in_q = f"Have you ever visited a place related to '{topic_lower}'?"
    elif "Book" in topic or "Movie" in topic or "Story" in topic:
        lead_in_q = f"Do you enjoy {topic_lower}?"
    elif "Toy" in topic or "App" in topic or "Object" in topic or "Technology" in topic:
        lead_in_q = f"Do you use or own {topic_lower}?"
    elif "Event" in topic or "Festival" in topic or "Party" in topic:
        lead_in_q = f"When was the last time you experienced {topic_lower}?"

    # Contextualized Differentiation
    b5_starter = f"I like {topic_lower} because..."
    if "Person" in topic or "Family" in topic:
        b5_starter = "This person is special because..."
    elif "Place" in topic:
        b5_starter = "I want to go there because..."
    elif "Event" in topic:
        b5_starter = "It was a memorable time because..."
    
    b6_peer = f"Ask specific questions about {topic_lower}."

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
                "transitions": "'Additionally...', 'Furthermore...'",
                "peer_check": b6_peer
            }
        },
        "lead_in": {
            "search_term": f"IELTS {topic} Speaking",
            "question": lead_in_q
        }
    }

def generate_l2_content(week_data, vocab_data, week_num):
    topic = week_data.get('topic', 'General Topic')
    clean_topic = clean_article(topic)
    topic_lower = clean_topic.lower()
    
    # Extract abstract noun
    l2_vocab = vocab_data.get('l2_vocab', [])
    abstract_word = l2_vocab[0]['word'] if l2_vocab else "Abstract Noun"
    
    # Contextualized Lead-in
    lead_in_q = f"How does {topic_lower} impact society?"
    if "Child" in topic or "Toy" in topic:
        lead_in_q = f"Do you think {topic_lower} affects how children grow up?"
    elif "Job" in topic or "Work" in topic:
        lead_in_q = f"How is {topic_lower} changing in the modern world?"
    elif "Environment" in topic or "Nature" in topic:
        lead_in_q = f"Why is {topic_lower} a critical issue today?"

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
                "peer_check": f"Challenge questions about {topic_lower} (e.g., 'Is this always true?')."
            }
        },
        "lead_in": {
            "search_term": f"IELTS {topic} Part 3",
            "question": lead_in_q
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
