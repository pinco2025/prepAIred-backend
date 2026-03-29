from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Any
from pydantic import BaseModel

from app.services.analytics_service import analytics_service

router = APIRouter()

class AnalyticsRequest(BaseModel):
    test_attempt_id: str

@router.post("/process-attempt", response_model=Any)
async def process_test_attempt(
    request: AnalyticsRequest,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Process a completed test attempt to update user analytics.

    - **test_attempt_id**: UUID of the student test attempt to process.

    Calculates chapter-wise performance, updates percentile rankings,
    and persists the user's analytics history to GitHub.
    """
    try:
        result = await analytics_service.process_test_attempt(request.test_attempt_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
