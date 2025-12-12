import logging
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.security import verify_token, TokenData
from app.core.config import settings
from app.core.supabase import db
from app.services.score_service import score_service
from app.schemas.score import ScoreResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Use a separate scheme for optional auth, allowing auto_error=False
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)

def get_current_user_conditional(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[TokenData]:
    """
    Returns current user if authentication is enabled and token is valid.
    If authentication is disabled via settings, returns None.
    If authentication is enabled but token is invalid/missing, raises HTTPException.
    """
    if not settings.ENABLE_AUTH:
        return None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(token)

@router.post(
    "/{student_test_id}/calculate",
    response_model=ScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Student Test Score",
)
async def calculate_student_test_score(
    student_test_id: str,
    current_user: Optional[TokenData] = Depends(get_current_user_conditional),
) -> ScoreResponse:
    """
    Calculate scores for a student test and push results to GitHub.

    - **student_test_id**: The UUID of the student test to calculate.
    - **current_user**: The authenticated user (inferred from token), if auth is enabled.

    Returns:
    - **student_test_id**: The ID of the processed test.
    - **github_url**: The URL of the generated score file on GitHub.
    """
    # Use service client to bypass RLS if configured
    supabase = await db.get_service_client()

    # 1. Fetch student_tests row
    try:
        response = await supabase.table("student_tests").select("*").eq("id", student_test_id).execute()
    except Exception as e:
        logger.error(f"Error fetching student test: {e}")
        raise HTTPException(status_code=500, detail="Error fetching student test")

    student_test = response.data
    if not student_test:
        logger.warning(f"Student test {student_test_id} not found. Check if ID is correct and if RLS allows access.")
        raise HTTPException(status_code=404, detail="Student test not found")
    student_test = student_test[0]

    # 2. Verify user ownership (only if auth is enabled)
    if settings.ENABLE_AUTH:
        # Should not happen if get_current_user_conditional works correctly,
        # but for type safety and double check:
        if not current_user:
             raise HTTPException(status_code=401, detail="Authentication required")

        if student_test.get("user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this test")

    # Check if result_url is already present
    existing_result_url = student_test.get("result_url")
    if existing_result_url:
        logger.info(f"Score already calculated for {student_test_id}. Returning existing URL.")
        return ScoreResponse(student_test_id=student_test_id, github_url=existing_result_url)

    test_id = student_test.get("test_id")
    answers = student_test.get("answers")

    if not test_id:
        raise HTTPException(status_code=400, detail="Test ID missing in student test record")

    # 3. Fetch tests row
    try:
        test_response = await supabase.table("tests").select("*").eq("testID", test_id).execute()
    except Exception as e:
        logger.error(f"Error fetching test definition: {e}")
        raise HTTPException(status_code=500, detail="Error fetching test definition")

    test_record = test_response.data
    if not test_record:
        raise HTTPException(status_code=404, detail="Test definition not found")
    test_record = test_record[0]

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
        filename = f"{student_test_id}.json"
        github_url = await score_service.push_to_github(result, filename)
    except Exception as e:
        logger.error(f"Error pushing results to GitHub: {e}")
        raise HTTPException(status_code=502, detail=f"Error pushing results to GitHub: {str(e)}")

    # 7. Update student_tests with result_url
    try:
        await supabase.table("student_tests").update({"result_url": github_url}).eq("id", student_test_id).execute()
    except Exception as e:
        logger.error(f"Error updating student_tests with result URL: {e}")
        # Not raising 500 here because the file was successfully pushed.
        # But we should probably alert the user or at least log it.
        # Returning the URL anyway.

    return ScoreResponse(student_test_id=student_test_id, github_url=github_url)
