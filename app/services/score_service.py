import json
import logging
import base64
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class ScoreService:
    def calculate_score(self, ppt_data: dict, response_data: dict) -> dict:
        """
        Calculates scores based on the provided PPT data and user response data.
        Refactored from calculate_scores.py.
        """

        # Process sections to get marking scheme
        sections_config = {}
        for section in ppt_data.get('sections', []):
            name = section.get('name')
            positive_marks = section.get('marksPerQuestion', 0)
            # Handle typo in key as seen in original script
            negative_marks = section.get('negagiveMarksPerQuestion', 0)

            sections_config[name] = {
                'positive': positive_marks,
                'negative': negative_marks
            }

        attempt_comparison = []
        section_scores = {}
        chapter_scores = {}

        # Initialize score aggregators
        for sec_name in sections_config:
            section_scores[sec_name] = {
                'score': 0,
                'correct': 0,
                'incorrect': 0,
                'unattempted': 0,
                'total_questions': 0
            }

        questions = ppt_data.get('questions', [])

        # Total stats aggregators
        total_score = 0
        total_correct = 0
        total_incorrect = 0
        total_unattempted = 0
        total_questions_count = 0

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
            total_questions_count += 1

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

            # Aggregate section stats
            if section_name in section_scores:
                section_scores[section_name]['score'] += marks
                if status == 'Correct':
                    section_scores[section_name]['correct'] += 1
                elif status == 'Incorrect':
                    section_scores[section_name]['incorrect'] += 1
                else:
                    section_scores[section_name]['unattempted'] += 1

            # Aggregate chapter stats
            chapter_scores[chapter_tag]['score'] += marks
            if status == 'Correct':
                chapter_scores[chapter_tag]['correct'] += 1
            elif status == 'Incorrect':
                chapter_scores[chapter_tag]['incorrect'] += 1
            else:
                chapter_scores[chapter_tag]['unattempted'] += 1

            # Aggregate total stats
            total_score += marks
            if status == 'Correct':
                total_correct += 1
            elif status == 'Incorrect':
                total_incorrect += 1
            else:
                total_unattempted += 1

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

        # Construct output with desired order
        output = {}

        # 1. Test details (everything from ppt_data except questions)
        for key, value in ppt_data.items():
            if key != 'questions':
                output[key] = value

        # 2. Existing score data
        output["attempt_comparison"] = attempt_comparison
        output["section_scores"] = section_scores
        output["chapter_scores"] = chapter_scores

        # 3. Total stats at the end
        output["total_stats"] = {
            "total_score": total_score,
            "total_questions": total_questions_count,
            "total_attempted": total_correct + total_incorrect,
            "total_correct": total_correct,
            "total_wrong": total_incorrect, # Using "total_wrong" as requested "total wrong"
            "total_unattempted": total_unattempted
        }

        return output

    async def push_to_github(self, data: dict, filename: str) -> str:
        """
        Pushes the data to a GitHub repository using the async HTTP client.
        Returns the URL of the pushed file.
        """
        if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
            raise ValueError("GITHUB_TOKEN and GITHUB_REPO must be set in configuration")

        base_url = f"https://api.github.com/repos/{settings.GITHUB_REPO}/contents/{filename}"
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        content_str = json.dumps(data, indent=4)
        content_encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

        message = f"Add score results for {filename}"

        async with httpx.AsyncClient() as client:
            # Check if file exists to get SHA (for update)
            sha = None
            try:
                get_response = await client.get(base_url, headers=headers)
                if get_response.status_code == 200:
                    sha = get_response.json().get("sha")
            except Exception as e:
                logger.warning(f"Failed to check if file exists: {e}")

            payload = {
                "message": message,
                "content": content_encoded
            }
            if sha:
                payload["sha"] = sha

            response = await client.put(base_url, headers=headers, json=payload)
            response.raise_for_status()

            resp_data = response.json()
            # Return the download_url from the content object in the response
            return resp_data.get("content", {}).get("download_url")

score_service = ScoreService()
