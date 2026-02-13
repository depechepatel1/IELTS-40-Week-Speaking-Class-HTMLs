import json
import sys
import re

def load_concatenated_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Try simple load first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # If simple load fails, try to parse multiple JSON arrays
        print(f"Warning: {filename} contains multiple JSON objects. Attempting to parse...")

        objects = []
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(content):
            try:
                # Skip whitespace
                while pos < len(content) and content[pos].isspace():
                    pos += 1
                if pos >= len(content):
                    break

                obj, end = decoder.raw_decode(content, pos)
                if isinstance(obj, list):
                    objects.extend(obj)
                else:
                    objects.append(obj)
                pos = end
            except json.JSONDecodeError:
                print(f"Error parsing JSON at position {pos}")
                break
        return objects

def extract_week_data(data, week_num):
    for item in data:
        if item.get('week') == week_num:
            return item
    return None

def main():
    week_num = 1

    print(f"Extracting data for Week {week_num}...")

    try:
        curriculum_data = load_concatenated_json('Curriculum 0 final.txt')
        vocab_data = load_concatenated_json('vocab_plan.txt')
        homework_data = load_concatenated_json('homework_plan.json')
    except Exception as e:
        print(f"Critical error loading data: {e}")
        sys.exit(1)

    week_curriculum = extract_week_data(curriculum_data, week_num)
    week_vocab = extract_week_data(vocab_data, week_num)
    week_homework = extract_week_data(homework_data, week_num)

    if not week_curriculum:
        print(f"Week {week_num} not found in Curriculum data.")
    if not week_vocab:
        print(f"Week {week_num} not found in Vocab data.")
    if not week_homework:
        print(f"Week {week_num} not found in Homework data.")

    combined_data = {
        'curriculum': week_curriculum,
        'vocab': week_vocab,
        'homework': week_homework
    }

    output_file = 'week_1_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully extracted Week {week_num} data to {output_file}")

if __name__ == "__main__":
    main()
