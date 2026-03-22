import pytest
from app.services.score_service import ScoreService


def test_calculate_score_sets_blunder_for_easy_incorrect():
    service = ScoreService()

    ppt_data = {
        "sections": [
            {"name": "Section1", "marksPerQuestion": 4, "negativeMarksPerQuestion": -1}
        ],
        "questions": [
            {
                "uuid": "q1",
                "id": "1",
                "section": "Section1",
                "correctAnswer": "A",
                "difficulty": "E",
                "chapterCode": "C1"
            },
            {
                "uuid": "q2",
                "id": "2",
                "section": "Section1",
                "correctAnswer": "B",
                "difficulty": "M",
                "chapterCode": "C1"
            },
            {
                "uuid": "q3",
                "id": "3",
                "section": "Section1",
                "correctAnswer": "C",
                "difficulty": "E",
                "chapterCode": "C1"
            }
        ]
    }

    response_data = {
        "q1": "B",  # incorrect easy
        "q2": "B",  # correct medium
        "q3": None   # unattempted easy
    }

    result = service.calculate_score(ppt_data, response_data)

    # validate attempt_comparison is generated
    attempts = result.get("attempt_comparison")
    assert isinstance(attempts, list)
    assert len(attempts) == 3

    q1 = next(item for item in attempts if item["question_uuid"] == "q1")
    q2 = next(item for item in attempts if item["question_uuid"] == "q2")
    q3 = next(item for item in attempts if item["question_uuid"] == "q3")

    assert q1["status"] == "Incorrect"
    assert q1["blunder"] is True

    assert q2["status"] == "Correct"
    assert q2["blunder"] is False

    assert q3["status"] == "Unattempted"
    assert q3["blunder"] is False
