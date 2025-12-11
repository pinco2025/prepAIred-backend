import json

def calculate_scores():
    # Load files
    with open('PPT-01.json', 'r') as f:
        ppt_data = json.load(f)

    with open('response.json', 'r') as f:
        response_data = json.load(f)

    # Process sections to get marking scheme
    sections_config = {}
    for section in ppt_data.get('sections', []):
        name = section.get('name')
        positive_marks = section.get('marksPerQuestion', 0)
        # Handle typo in key
        negative_marks = section.get('negagiveMarksPerQuestion', 0)
        # Assuming negative_marks is the value to ADD to the score (e.g. -1).
        # If it is positive (e.g. 1), we might need to negate it, but usually in these JSONs
        # it's explicit. Let's look at the file content again in memory.
        # "negagiveMarksPerQuestion" : -1. So adding it works.

        sections_config[name] = {
            'positive': positive_marks,
            'negative': negative_marks
        }

    attempt_comparison = []
    section_scores = {}
    chapter_scores = {}

    # Initialize score aggregators
    # We might not know all chapters ahead of time, so we'll init on fly.
    # We know sections from the config though.
    for sec_name in sections_config:
        section_scores[sec_name] = {
            'score': 0,
            'correct': 0,
            'incorrect': 0,
            'unattempted': 0,
            'total_questions': 0
        }

    questions = ppt_data.get('questions', [])

    for q in questions:
        uuid = q.get('uuid')
        q_id = q.get('id')
        section_name = q.get('section')
        correct_ans = q.get('correctAnswer')

        # Get chapter from tag2
        tags = q.get('tags', {})
        chapter_tag = tags.get('tag2', 'Unknown')

        user_ans = response_data.get(uuid)

        status = 'Unattempted'
        marks = 0

        section_cfg = sections_config.get(section_name, {'positive': 0, 'negative': 0})

        # Initialize chapter stats if needed
        if chapter_tag not in chapter_scores:
            chapter_scores[chapter_tag] = {
                'score': 0,
                'correct': 0,
                'incorrect': 0,
                'unattempted': 0,
                'total_questions': 0
            }

        # Update totals
        if section_name in section_scores:
            section_scores[section_name]['total_questions'] += 1
        chapter_scores[chapter_tag]['total_questions'] += 1

        if user_ans is not None:
            # Check if answer is correct
            # Normalize to string just in case
            if str(user_ans).strip() == str(correct_ans).strip():
                status = 'Correct'
                marks = section_cfg['positive']
            else:
                status = 'Incorrect'
                marks = section_cfg['negative']
        else:
            status = 'Unattempted'
            marks = 0

        # Aggregate
        if section_name in section_scores:
            section_scores[section_name]['score'] += marks
            if status == 'Correct':
                section_scores[section_name]['correct'] += 1
            elif status == 'Incorrect':
                section_scores[section_name]['incorrect'] += 1
            else:
                section_scores[section_name]['unattempted'] += 1

        chapter_scores[chapter_tag]['score'] += marks
        if status == 'Correct':
            chapter_scores[chapter_tag]['correct'] += 1
        elif status == 'Incorrect':
            chapter_scores[chapter_tag]['incorrect'] += 1
        else:
            chapter_scores[chapter_tag]['unattempted'] += 1

        attempt_comparison.append({
            "question_uuid": uuid,
            "question_id": q_id,
            "section": section_name,
            "chapter_tag": chapter_tag,
            "user_response": user_ans,
            "correct_response": correct_ans,
            "status": status,
            "marks_awarded": marks
        })

    output = {
        "attempt_comparison": attempt_comparison,
        "section_scores": section_scores,
        "chapter_scores": chapter_scores
    }

    with open('output.json', 'w') as f:
        json.dump(output, f, indent=4)

    print("Processing complete. Output written to output.json")

if __name__ == "__main__":
    calculate_scores()
