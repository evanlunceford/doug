from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import os

load_dotenv()

canvas_auth = {
    "base_url": os.getenv("CANVAS_BASE_URL"),
    "api_token": os.getenv("CANVAS_API_KEY")
}


class CanvasAPI():
    def __init__(self):
        self.per_page = 100
    
    def _headers(self, canvas_auth: dict) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {canvas_auth['api_token']}",
        }
    
    def _request(self, method: str, endpoint: str, canvas_auth: dict, **kwargs):
        url = f"{canvas_auth['base_url']}{endpoint}"
        try:
            r = requests.request(method, url, headers=self._headers(canvas_auth), timeout=15, **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"Canvas API error at {url}: {e}")
            raise

    def _paginated(self, method: str, endpoint: str, canvas_auth: dict, params=None):
        all_results, page = [], 1
        while True:
            merged_params = {**(params or {}), "page": page, "per_page": self.per_page}
            resp = self._request(method, endpoint, canvas_auth, params=merged_params)
            if not resp:
                break
            all_results.extend(resp)
            if len(resp) < self.per_page:
                break
            page += 1
        return all_results

    @staticmethod
    def _iso_to_dt(iso_str: str):
        # Canvas returns ISO8601, often with trailing 'Z'
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

    def get_all_courses(self, canvas_auth: dict):
        states = ["active", "completed", "invited_or_pending", "inactive"]
        all_courses = []
        for state in states:
            try:
                courses = self._paginated(
                    "GET", "/courses", canvas_auth,
                    params={
                        "enrollment_state": state,
                        "enrollment_type": "student",
                        "include[]": ["term", "enrollments", "total_scores", "sections"]
                    }
                )
                all_courses.extend(courses)
            except Exception as e:
                print(f"Failed to fetch courses for state {state}: {e}")

        return list({c["id"]: c for c in all_courses}.values())

    def get_all_assignments(
        self,
        canvas_auth: dict,
        only_upcoming: bool = True,
        course_id: int | None = None,
        include_submissions: bool = False
    ):
        if course_id:
            course = self._request("GET", f"/courses/{course_id}", canvas_auth)
            courses = [{"id": course_id, "name": course.get("name", f"Course {course_id}")}]
        else:
            courses = self.get_all_courses(canvas_auth)

        results = []
        now_utc_date = datetime.now(timezone.utc).date()

        for course in courses:
            cid = course["id"]
            cname = course.get("name", f"Course {cid}")

            params = {}
            if only_upcoming:
                params["bucket"] = "upcoming"

            includes = ["overrides"]
            if include_submissions:
                includes.append("submission")
            params["include[]"] = includes

            assignments = self._paginated(
                "GET", f"/courses/{cid}/assignments", canvas_auth, params=params
            )

            filtered = []
            if only_upcoming:
                for a in assignments:
                    due_at = a.get("due_at")
                    if not due_at:
                        continue
                    try:
                        due_date = self._iso_to_dt(due_at).date()
                        if due_date >= now_utc_date:
                            filtered.append(a)
                    except Exception:
                        continue
            else:
                filtered = assignments

            for a in filtered:
                item = {
                    "courseId": cid,
                    "courseName": cname,
                    "assignmentId": a["id"],
                    "name": a.get("name"),
                    "due_at": a.get("due_at"),
                    "html_url": a.get("html_url"),
                    "points_possible": a.get("points_possible"),
                }
                if include_submissions:
                    sub = a.get("submission") or {}
                    item["has_submitted"] = bool(sub.get("submitted_at"))
                    item["submission"] = sub
                results.append(item)

        def _key(x):
            d = x.get("due_at")
            try:
                return (0, self._iso_to_dt(d)) if d else (1, datetime.max.replace(tzinfo=timezone.utc))
            except Exception:
                return (1, datetime.max.replace(tzinfo=timezone.utc))

        results.sort(key=_key)
        return results

    def get_course_syllabus(self, canvas_auth, course_id):
        data = self._request("GET", f"/courses/{course_id}", canvas_auth, params={"include[]": "syllabus_body"})
        return {"name": data.get("name"), "syllabus": data.get("syllabus_body")}

    def get_course_syllabus_if_exists(self, canvas_auth, course_id):
        try:
            info = self.get_course_syllabus(canvas_auth, course_id)
            name, syllabus = info["name"], info["syllabus"]

            text, prereqs = "", []
            if syllabus and syllabus.strip():
                soup = BeautifulSoup(syllabus, "lxml")
                text = soup.get_text(" ", strip=True)

            if not text or len(text) < 100:
                fallback = self.fetch_catalog_syllabus(name)
                if fallback:
                    text = fallback["description"]
                    prereqs = fallback.get("prerequisites", [])

            if text and len(text) >= 100:
                return {
                    "courseId": course_id,
                    "courseName": name,
                    "syllabus": text,
                    "prerequisites": prereqs
                }
        except Exception as e:
            print(f"Error getting syllabus for {course_id}: {e}")
        return None
    

    def get_assignments_next_week(
        self,
        canvas_auth: dict,
        course_id: int | None = None,
        tz_str: str = "America/Phoenix",
        include_submissions: bool = True,
    ):
        """
        Return assignments due in the next 7 days (inclusive of 'now'), either across all courses
        or for a single course. Returns the FULL assignment objects from Canvas, plus:
        - courseId, courseName
        - description_html (raw HTML from Canvas)
        - description_text (clean text using BeautifulSoup)

        Window: [now, now + 7 days). Uses the provided timezone for date comparisons.
        """
        # Figure out time window in the chosen timezone
        tz = ZoneInfo(tz_str)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)
        end_utc = (now_local + timedelta(days=7)).astimezone(timezone.utc)

        # Determine which courses to inspect
        if course_id:
            course = self._request("GET", f"/courses/{course_id}", canvas_auth)
            courses = [{"id": course_id, "name": course.get("name", f"Course {course_id}")}]
        else:
            courses = self.get_all_courses(canvas_auth)

        # Canvas "include" options to get as much as possible in one pass
        includes = [
            "submission" if include_submissions else None,
            "overrides",
            "rubric",
            "assignment_visibility",
            "all_dates",
            "score_statistics",
            "can_submit",
            "needs_grading_count",
            "locked_for_user",
        ]
        includes = [i for i in includes if i]

        results = []

        for c in courses:
            cid = c["id"]
            cname = c.get("name", f"Course {cid}")

            # Start with server-side narrowing via 'bucket=upcoming'
            params = {"bucket": "upcoming", "include[]": includes}

            assignments = self._paginated(
                "GET", f"/courses/{cid}/assignments", canvas_auth, params=params
            )

            for a in assignments:
                due_at = a.get("due_at")
                if not due_at:
                    # No due date; skip for a "due next week" list
                    continue

                try:
                    due_dt = self._iso_to_dt(due_at)  # this is an aware datetime in UTC or with offset
                    due_dt_utc = due_dt.astimezone(timezone.utc)
                except Exception:
                    continue

                # Keep only items in [now_utc, end_utc)
                if not (now_utc <= due_dt_utc < end_utc):
                    continue

                # Extract description (HTML + text)
                description_html = a.get("description")  # Canvas returns HTML here
                description_text = ""
                if description_html:
                    try:
                        description_text = BeautifulSoup(description_html, "lxml").get_text(" ", strip=True)
                    except Exception:
                        description_text = ""

                # Build a rich record: course info + the full assignment payload
                record = {
                    "courseId": cid,
                    "courseName": cname,
                    "assignmentId": a.get("id"),
                    "due_at": a.get("due_at"),
                    "html_url": a.get("html_url"),
                    # Keep full raw assignment for maximum detail:
                    "assignment": a,
                    # Convenience fields:
                    "description_html": description_html,
                    "description_text": description_text,
                }
                results.append(record)

        # Sort by due date ascending
        def _key(x):
            try:
                return self._iso_to_dt(x.get("due_at") or "9999-12-31T23:59:59+00:00")
            except Exception:
                return datetime.max.replace(tzinfo=timezone.utc)

        results.sort(key=_key)
        return results

if __name__ == "__main__":

    api = CanvasAPI()
    items = api.get_assignments_next_week(canvas_auth,course_id=52461)
