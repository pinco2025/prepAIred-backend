import json
import logging
import base64
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.core.supabase import db

logger = logging.getLogger(__name__)

class AnalyticsService:
    async def process_test_attempt(self, test_attempt_id: str, score_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        test_id = student_test.get("test_id")

        if not result_url:
            raise ValueError(f"Result URL not found for test attempt: {test_attempt_id}")

        if not user_id:
             raise ValueError(f"User ID not found for test attempt: {test_attempt_id}")

        # 2. Fetch Test details (for 99ile)
        tests_response = await supabase.table("tests").select("*").eq("id", test_id).execute()
        test_data = {}
        if tests_response.data:
            test_data = tests_response.data[0]

        m99 = test_data.get("99ile") or 0

        # 3. Fetch Score JSON
        if not score_data:
            async with httpx.AsyncClient() as client:
                score_response = await client.get(result_url)
                score_response.raise_for_status()
                score_data = score_response.json()

        # 4. Process Scores
        section_scores = score_data.get("section_scores", {})
        total_stats = score_data.get("total_stats", {})
        sections = score_data.get("sections", [])

        total_score = total_stats.get("total_score", 0)

        # Get ordered section names
        ordered_section_names = []
        if isinstance(sections, list):
            for s in sections:
                if isinstance(s, dict):
                    ordered_section_names.append(s.get("name"))
                elif isinstance(s, str):
                    ordered_section_names.append(s)

        # Fallback if sections list is empty or malformed
        if not ordered_section_names:
            logger.warning("No sections list found in score data, falling back to section_scores keys")
            ordered_section_names = list(section_scores.keys())

        # Calculate subject-wise scores based on positional grouping
        # First 2 -> Physics, Next 2 -> Chemistry, Next 2 -> Math
        phy_score = 0.0
        chem_score = 0.0
        math_score = 0.0

        for i, section_name in enumerate(ordered_section_names):
            score = section_scores.get(section_name, {}).get("score", 0)

            if i < 2: # Sections 0, 1 -> Physics
                phy_score += score
            elif i < 4: # Sections 2, 3 -> Chemistry
                chem_score += score
            elif i < 6: # Sections 4, 5 -> Math
                math_score += score
            # Ignore further sections as per specific requirement

        # Calculate accuracy
        total_attempted = total_stats.get("total_attempted", 0)
        total_correct = total_stats.get("total_correct", 0)

        # Accuracy as percentage
        accuracy = (total_correct / total_attempted * 100) if total_attempted > 0 else 0.0
        # Round accuracy to integer to satisfy smallint column constraints
        accuracy_int = int(round(accuracy))

        # Calculate Percentile
        # P(M) = 100 * (1 - ((M99 - M)/M99)^k) where k = 1.87
        percentile = 0.0
        if m99 > 0:
            k = 1.87
            # If student score is greater than 99ile, term becomes negative, so we cap effective score at m99
            # or we assume max percentile is 100.
            effective_score = min(total_score, m99)

            term = (m99 - effective_score) / m99
            # Avoid complex number if term is negative (handled by min above)
            # term should be between 0 and 1
            percentile = 100 * (1 - (term ** k))

        # Round percentile to integer for storage (assuming similar requirement as accuracy)
        percentile_int = int(round(percentile))

        # 5. Update user_analytics
        analytics_response = await supabase.table("user_analytics").select("*").eq("user_id", user_id).execute()

        current_data = {}
        if analytics_response.data:
            current_data = analytics_response.data[0]

        new_attempt_no = (current_data.get("attempt_no") or 0) + 1

        # Update averages (accumulate scores)
        # Handle None values safely
        current_phy_avg = current_data.get("phy_avg") or 0
        current_chem_avg = current_data.get("chem_avg") or 0
        current_math_avg = current_data.get("math_avg") or 0
        current_accuracy = current_data.get("accuracy") or 0
        current_percentile = current_data.get("percentile") or 0

        new_phy_avg = int(current_phy_avg + phy_score)
        new_chem_avg = int(current_chem_avg + chem_score)
        new_math_avg = int(current_math_avg + math_score)

        # Ensure new_accuracy is also an int
        # The logic is doing SUM as per existing pattern
        new_accuracy = int(current_accuracy + accuracy_int)

        # Update percentile accumulation
        new_percentile_sum = int(current_percentile + percentile_int)

        analytics_update = {
            "user_id": user_id,
            "attempt_no": new_attempt_no,
            "phy_avg": new_phy_avg,
            "chem_avg": new_chem_avg,
            "math_avg": new_math_avg,
            "accuracy": new_accuracy,
            "percentile": new_percentile_sum
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

        # 6. History JSON
        history_entry = {
            "test_attempt_id": test_attempt_id,
            "timestamp": datetime.utcnow().isoformat(),
            "phy_score": phy_score,
            "chem_score": chem_score,
            "math_score": math_score,
            "accuracy": accuracy,
            "percentile": percentile,
            "cumulative_stats": {
                "phy_avg": new_phy_avg,
                "chem_avg": new_chem_avg,
                "math_avg": new_math_avg,
                "accuracy": new_accuracy,
                "percentile": new_percentile_sum,
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

        # 6. Chapter Stats JSON
        chapter_scores = score_data.get("chapter_scores", {})
        current_chapter_url = analytics_record.get("chapter_url")

        new_chapter_url = await self._update_chapter_stats(user_id, chapter_scores)

        # 7. Update URLs in DB
        update_payload = {}
        if new_history_url != current_history_url:
            update_payload["history_url"] = new_history_url
        if new_chapter_url != current_chapter_url:
            update_payload["chapter_url"] = new_chapter_url

        if update_payload:
            await supabase.table("user_analytics").update(update_payload).eq("user_id", user_id).execute()

        return {
            "message": "Analytics updated successfully",
            "user_id": user_id,
            "history_url": new_history_url,
            "chapter_url": new_chapter_url
        }

    async def _update_chapter_stats(self, user_id: str, new_chapter_scores: Dict[str, Any]) -> str:
        filename = f"user_analytics/chapters/{user_id}.json"

        if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
            raise ValueError("GITHUB_TOKEN and GITHUB_REPO must be set in configuration")

        base_url = f"https://api.github.com/repos/{settings.GITHUB_REPO}/contents/{filename}"
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        async with httpx.AsyncClient() as client:
            # 1. Fetch existing stats
            stats_data = {"chapters": {}, "last_updated": ""}
            sha = None

            try:
                get_response = await client.get(base_url, headers=headers)
                if get_response.status_code == 200:
                    data = get_response.json()
                    sha = data.get("sha")
                    content_encoded = data.get("content")
                    if content_encoded:
                        content_str = base64.b64decode(content_encoded).decode("utf-8")
                        stats_data = json.loads(content_str)
            except Exception as e:
                logger.info(f"Chapter stats file {filename} likely does not exist or empty: {e}")

            chapters = stats_data.get("chapters", {})
            if not isinstance(chapters, dict):
                chapters = {}

            # 2. Update with new scores
            for chapter_code, scores in new_chapter_scores.items():
                if chapter_code not in chapters:
                    chapters[chapter_code] = {
                        "attempted": 0,
                        "unattempted": 0,
                        "correct": 0,
                        "incorrect": 0,
                        "total_questions": 0
                    }

                entry = chapters[chapter_code]

                c_correct = scores.get("correct", 0)
                c_incorrect = scores.get("incorrect", 0)
                c_unattempted = scores.get("unattempted", 0)
                c_total = scores.get("total_questions", 0)

                entry["correct"] += c_correct
                entry["incorrect"] += c_incorrect
                entry["unattempted"] += c_unattempted
                entry["total_questions"] += c_total
                entry["attempted"] += (c_correct + c_incorrect)

            # 3. Sort: least attempted at the top
            sorted_chapters = dict(sorted(chapters.items(), key=lambda item: item[1].get("attempted", 0)))

            stats_data["chapters"] = sorted_chapters
            stats_data["last_updated"] = datetime.utcnow().isoformat()

            # 4. Push to GitHub
            content_str = json.dumps(stats_data, indent=4)
            content_encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            message = f"Update chapter stats for {user_id}"

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
