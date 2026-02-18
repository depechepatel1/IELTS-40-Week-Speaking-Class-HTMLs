import json
import re

# Define the manual, correct bullet points for Weeks 10-13
# based on the questions in Origional Curriculum.txt
NEW_BULLETS = {
    10: [
        [
            "Where: Sydney / Harbor",
            "Look: Sails / White",
            "Use: Music / Opera",
            "Why: Unique / Famous"
        ],
        [
            "Place: Castle / Temple",
            "Use: Museum / Park",
            "Look: Old / Stone",
            "Like: History / View"
        ],
        [
            "Building: Library / Office",
            "Look: Glass / Steel",
            "Use: Read / Work",
            "Like: Clean / Light"
        ]
    ],
    11: [
        [
            "Tech: Laptop / Phone",
            "Cost: Expensive / High",
            "Do: Work / Play",
            "Why: Fast / New"
        ],
        [
            "Device: Robot vacuum / Dishwasher",
            "Use: Daily / Weekly",
            "Works: Automatic / Sensors",
            "Why: Saves chores"
        ],
        [
            "What: Internet / Smartphone",
            "When: 1990s / 2000s",
            "Impact: Connection / Speed",
            "Opinion: Good / Bad"
        ]
    ],
    12: [
        [
            "Place: Tokyo / Forest",
            "Happened: Wrong turn / No map",
            "Felt: Scared / Tired",
            "Found: Asked local / Police"
        ],
        [
            "Event: Exam / Wedding",
            "Why: Traffic / Overslept",
            "Result: Missed start / Scolded",
            "Felt: Stress / Regret"
        ],
        [
            "Where: Street / Station",
            "Who: Tourist / Old lady",
            "Action: Showed map / Guided",
            "Felt: Helpful / Kind"
        ]
    ],
    13: [
        [
            "Who: Elon Musk / Taylor Swift",
            "Know: News / Music",
            "Meet: Coffee / Backstage",
            "Why: Inspiration / Fan"
        ],
        [
            "Who: Messi / Ronaldo",
            "Sport: Football / Soccer",
            "Achievements: Goals / Cups",
            "Admire: Skill / Hard work"
        ],
        [
            "Who: Jackie Chan / Yao Ming",
            "Field: Acting / Sports",
            "Why famous: Movies / NBA",
            "Pride: Yes / Very"
        ]
    ]
}

def update_curriculum():
    filepath = 'Origional curriculum.txt'
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        week = item.get('week')
        if week in NEW_BULLETS:
            questions = item.get('l1_part2_questions', [])
            bullets = NEW_BULLETS[week]
            
            for i, q in enumerate(questions):
                # 1. Update/Inject Bullet Points
                if i < len(bullets):
                    q['Spider Diagram "bullet_points"'] = bullets[i]
                
                # 2. Reorder ID to top (by creating a new dict order)
                new_q = {'id': q['id']}
                for k, v in q.items():
                    if k != 'id':
                        new_q[k] = v
                
                # Replace the question object
                questions[i] = new_q

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Successfully updated Weeks 10-13 in Origional curriculum.txt")

if __name__ == "__main__":
    update_curriculum()
