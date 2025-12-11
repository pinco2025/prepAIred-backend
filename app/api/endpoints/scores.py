import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, TokenData
from app.core.supabase import db
from app.services.score_service import score_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{student_test_id}/calculate", status_code=status.HTTP_200_OK)
async def calculate_student_test_score(
    student_test_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Calculate scores for a student test and push results to GitHub.
    """
    supabase = await db.get_client()

    # 1. Fetch student_tests row
    try:
        response = await supabase.table("student_tests").select("*").eq("id", student_test_id).execute()
        student_test = response.data
        if not student_test:
            raise HTTPException(status_code=404, detail="Student test not found")
        student_test = student_test[0]
    except Exception as e:
        logger.error(f"Error fetching student test: {e}")
        raise HTTPException(status_code=500, detail="Error fetching student test")

    # 2. Verify user ownership
    if student_test.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this test")

    test_id = student_test.get("test_id")
    answers = student_test.get("answers")

    if not test_id:
        raise HTTPException(status_code=400, detail="Test ID missing in student test record")

    # 3. Fetch tests row
    try:
        test_response = await supabase.table("tests").select("*").eq("testID", test_id).execute()
        test_record = test_response.data
        if not test_record:
            raise HTTPException(status_code=404, detail="Test definition not found")
        test_record = test_record[0]
    except Exception as e:
        logger.error(f"Error fetching test definition: {e}")
        raise HTTPException(status_code=500, detail="Error fetching test definition")

    test_url = test_record.get("url")
    if not test_url:
        raise HTTPException(status_code=400, detail="Test URL missing in test record")

    # 4. Fetch test JSON from GitHub raw URL
    ppt_data = {}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(test_url)
            resp.raise_for_status()
            ppt_data = resp.json()
    except Exception as e:
        logger.error(f"Error fetching test JSON from {test_url}: {e}")
        raise HTTPException(status_code=502, detail="Error fetching test definition from external source")

    # 5. Calculate scores
    try:
        result = score_service.calculate_score(ppt_data, answers or {})
    except Exception as e:
        logger.error(f"Error calculating score: {e}")
        raise HTTPException(status_code=500, detail="Error calculating score")

    # 6. Push to GitHub
    github_url = ""
    try:
        # Create a filename based on student_test_id
        filename = f"score_results_{student_test_id}.json"
        github_url = score_service.push_to_github(result, filename)
    except Exception as e:
        logger.error(f"Error pushing results to GitHub: {e}")
        raise HTTPException(status_code=502, detail=f"Error pushing results to GitHub: {str(e)}")

    return {
        "student_test_id": student_test_id,
        "github_url": github_url
    }
