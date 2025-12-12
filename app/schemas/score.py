from pydantic import BaseModel

class ScoreResponse(BaseModel):
    student_test_id: str
    github_url: str
