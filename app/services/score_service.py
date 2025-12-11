import json
import logging
from github import Github, GithubException
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

        return output

    def push_to_github(self, data: dict, filename: str) -> str:
        """
        Pushes the data to a GitHub repository.
        Returns the URL of the pushed file.
        """
        if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
            raise ValueError("GITHUB_TOKEN and GITHUB_REPO must be set in configuration")

        g = Github(settings.GITHUB_TOKEN)

        try:
            repo = g.get_repo(settings.GITHUB_REPO)

            content = json.dumps(data, indent=4)
            message = f"Add score results for {filename}"

            try:
                # Check if file exists to update
                contents = repo.get_contents(filename)
                repo.update_file(contents.path, message, content, contents.sha)
                logger.info(f"Updated existing file {filename} in GitHub repo {settings.GITHUB_REPO}")
            except Exception:
                # Create new file
                repo.create_file(filename, message, content)
                logger.info(f"Created new file {filename} in GitHub repo {settings.GITHUB_REPO}")

            # Construct the URL (assuming public repo or accessible via raw)
            # Or return the blob URL
            return f"https://github.com/{settings.GITHUB_REPO}/blob/main/{filename}"

        except Exception as e:
            logger.error(f"Failed to push to GitHub: {e}")
            raise e

score_service = ScoreService()
