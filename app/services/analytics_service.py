import json
import logging
import base64
import httpx
from datetime import datetime
from typing import Dict, Any, List

from app.core.config import settings
from app.core.supabase import db

logger = logging.getLogger(__name__)

class AnalyticsService:
    async def process_test_attempt(self, test_attempt_id: str) -> Dict[str, Any]:
        """
        Processes a test attempt to update user analytics.
        """
        logger.info(f"Processing test attempt: {test_attempt_id}")

        # 1. Fetch student_test record
        supabase = await db.get_service_client()
        response = await supabase.table("student_tests").select("*").eq("id", test_attempt_id).execute()

        if not response.data:
            raise ValueError(f"Student test not found for id: {test_attempt_id}")

        student_test = response.data[0]
        result_url = student_test.get("result_url")
        user_id = student_test.get("user_id")

        if not result_url:
            raise ValueError(f"Result URL not found for test attempt: {test_attempt_id}")

        if not user_id:
             raise ValueError(f"User ID not found for test attempt: {test_attempt_id}")

        # 2. Fetch Score JSON
        async with httpx.AsyncClient() as client:
            score_response = await client.get(result_url)
            score_response.raise_for_status()
            score_data = score_response.json()

        # 3. Process Scores
        section_scores = score_data.get("section_scores", {})
        total_stats = score_data.get("total_stats", {})

        # Calculate subject-wise scores
        phy_score = 0.0
        chem_score = 0.0
        math_score = 0.0
        # Determine if Bio is needed based on sections presence or explicit requirement
        # For now, following user instruction "phy_avg, chem_avg and so on".
        # Assuming PCMB structure if sections exist.

        for section_name, stats in section_scores.items():
            score = stats.get("score", 0)
            name_lower = section_name.lower()
            if "physics" in name_lower:
                phy_score += score
            elif "chemistry" in name_lower:
                chem_score += score
            elif "math" in name_lower:
                math_score += score
            # Add bio if needed, but strictly PCMB is standard for JEE/NEET
            # The prompt implies typical subjects.

        # Calculate accuracy
        total_attempted = total_stats.get("total_attempted", 0)
        total_correct = total_stats.get("total_correct", 0)

        # Accuracy as percentage
        accuracy = (total_correct / total_attempted * 100) if total_attempted > 0 else 0.0

        # 4. Update user_analytics
        analytics_response = await supabase.table("user_analytics").select("*").eq("user_id", user_id).execute()

        current_data = {}
        if analytics_response.data:
            current_data = analytics_response.data[0]

        new_attempt_no = current_data.get("attempt_no", 0) + 1

        # Update averages (accumulate scores)
        new_phy_avg = current_data.get("phy_avg", 0.0) + phy_score
        new_chem_avg = current_data.get("chem_avg", 0.0) + chem_score
        new_math_avg = current_data.get("math_avg", 0.0) + math_score
        new_accuracy = current_data.get("accuracy", 0.0) + accuracy

        analytics_update = {
            "user_id": user_id,
            "attempt_no": new_attempt_no,
            "phy_avg": new_phy_avg,
            "chem_avg": new_chem_avg,
            "math_avg": new_math_avg,
            "accuracy": new_accuracy
            # history_url will be updated later
        }

        if not analytics_response.data:
            # Create new row
            # We insert first to ensure row exists (and get other defaults if any)
            # Actually UPSERT is better if supported, but let's stick to Insert or Update
            insert_res = await supabase.table("user_analytics").insert(analytics_update).execute()
            if not insert_res.data:
                raise ValueError("Failed to create user_analytics row")
            analytics_record = insert_res.data[0]
        else:
            # Update existing row
            update_res = await supabase.table("user_analytics").update(analytics_update).eq("user_id", user_id).execute()
            if not update_res.data:
                 raise ValueError("Failed to update user_analytics row")
            analytics_record = update_res.data[0]

        # 5. History JSON
        history_entry = {
            "test_attempt_id": test_attempt_id,
            "timestamp": datetime.utcnow().isoformat(),
            "phy_score": phy_score,
            "chem_score": chem_score,
            "math_score": math_score,
            "accuracy": accuracy,
            "cumulative_stats": {
                "phy_avg": new_phy_avg,
                "chem_avg": new_chem_avg,
                "math_avg": new_math_avg,
                "accuracy": new_accuracy,
                "attempt_no": new_attempt_no
            }
        }

        # Fetch existing history if history_url exists
        history_data = []
        current_history_url = analytics_record.get("history_url")

        # If we have a URL, try to fetch it.
        # But actually, we are supposed to "create/update a JSON for the user_id that is being handled"
        # The file location is user_analytics/{user_id}.json
        # We can try to fetch it from GitHub API directly to ensure we have the latest,
        # or relying on history_url is fine if we trust it points to the right place.
        # However, to use the GitHub API correctly for updates (handling SHA), we should fetch via API anyway.

        filename = f"user_analytics/{user_id}.json"

        # We need to fetch the existing content to append.
        # I'll use a helper method similar to ScoreService.push_to_github but one that reads first.

        new_history_url = await self._update_github_history(filename, history_entry)

        # 6. Update history_url in DB
        if new_history_url != current_history_url:
            await supabase.table("user_analytics").update({"history_url": new_history_url}).eq("user_id", user_id).execute()

        return {
            "message": "Analytics updated successfully",
            "user_id": user_id,
            "history_url": new_history_url
        }

    async def _update_github_history(self, filename: str, new_entry: Dict) -> str:
        if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
            raise ValueError("GITHUB_TOKEN and GITHUB_REPO must be set in configuration")

        base_url = f"https://api.github.com/repos/{settings.GITHUB_REPO}/contents/{filename}"
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        async with httpx.AsyncClient() as client:
            # 1. Get existing file
            sha = None
            history_list = []

            try:
                get_response = await client.get(base_url, headers=headers)
                if get_response.status_code == 200:
                    data = get_response.json()
                    sha = data.get("sha")
                    content_encoded = data.get("content")
                    if content_encoded:
                        content_str = base64.b64decode(content_encoded).decode("utf-8")
                        history_list = json.loads(content_str)
            except Exception as e:
                logger.info(f"File {filename} likely does not exist or empty: {e}")

            if not isinstance(history_list, list):
                history_list = []

            # 2. Append new entry
            history_list.append(new_entry)

            # 3. Push back
            content_str = json.dumps(history_list, indent=4)
            content_encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            message = f"Update user analytics history for {filename}"

            payload = {
                "message": message,
                "content": content_encoded
            }
            if sha:
                payload["sha"] = sha

            put_response = await client.put(base_url, headers=headers, json=payload)
            put_response.raise_for_status()

            resp_data = put_response.json()
            return resp_data.get("content", {}).get("download_url")

analytics_service = AnalyticsService()
