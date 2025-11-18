# canvas_service.py
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import os
import json

from src.backend.database.canvas_repo import CanvasRepo, CANVAS_DB_PATH

load_dotenv()

canvas_auth = {
    "base_url": os.getenv("CANVAS_BASE_URL"),
    "api_token": os.getenv("CANVAS_API_KEY")
}


class CanvasService():
    def __init__(self, db_path: str = CANVAS_DB_PATH):
        self.per_page = 100
        self.repo = CanvasRepo(db_path)

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
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

    @staticmethod
    def _dt_to_iso_z(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _extract_description(a: dict) -> tuple[str, str]:
        html = a.get("description")
        if not html:
            return "", ""
        try:
            text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        except Exception:
            text = ""
        return html or "", text

    @staticmethod
    def _make_payload_record(course_id: int, course_name: str, a: dict) -> dict:
        """Normalize a Canvas assignment to your payload record with `assignment` included."""
        description_html, description_text = CanvasService._extract_description(a)
        return {
            "courseId": course_id,
            "courseName": course_name,
            "assignmentId": a.get("id"),
            "due_at": a.get("due_at"),
            "html_url": a.get("html_url"),
            "assignment": a,  # full raw object
            "description_html": description_html,
            "description_text": description_text,
        }

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
        include_submissions: bool = False,
        persist_to_db: bool = True,
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
                record = self._make_payload_record(cid, cname, a)
                if include_submissions:
                    sub = a.get("submission") or {}
                    record["has_submitted"] = bool(sub.get("submitted_at"))
                    record["submission"] = sub
                results.append(record)

        def _key(x):
            d = x.get("due_at")
            try:
                return (0, self._iso_to_dt(d)) if d else (1, datetime.max.replace(tzinfo=timezone.utc))
            except Exception:
                return (1, datetime.max.replace(tzinfo=timezone.utc))
        results.sort(key=_key)

        if persist_to_db and results:
            self.repo.bulk_upsert_from_payload(results)


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

    def fetch_catalog_syllabus(self, course_name: str):
        return None

    def get_remaining_weekly_assignments(
        self,
        course_id: int | None = None,
        tz_str: str = "America/Phoenix",
        include_submissions: bool = False,
        prefer_cache: bool = True,
        refresh_if_empty: bool = True
    ):
        """Gets assignments due between now and upcoming Sunday 23:59 (local) [DB-first]."""

        tz = ZoneInfo(tz_str)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)

        # Upcoming Sunday 23:59 local -> UTC
        days_until_sunday = (6 - now_local.weekday()) % 7
        end_of_week_local = (now_local + timedelta(days=days_until_sunday)).replace(
            hour=23, minute=59, second=0, microsecond=0
        )
        end_utc = end_of_week_local.astimezone(timezone.utc)

        start_iso = self._dt_to_iso_z(now_utc)
        end_iso = self._dt_to_iso_z(end_utc)

        if prefer_cache:
            cached = self._get_from_db_window(start_iso, end_iso, course_id=course_id)
            if cached:
                return cached

        if not prefer_cache or (refresh_if_empty and not cached):
            fetched = self._fetch_and_filter_window(canvas_auth, start_utc=now_utc, end_utc=end_utc,
                                                   course_id=course_id, include_submissions=include_submissions)
            if fetched:
                self.repo.bulk_upsert_from_payload(fetched)
            return fetched

        return []

    def get_assignments_next_week(
        self,
        canvas_auth: dict,
        course_id: int | None = None,
        tz_str: str = "America/Phoenix",
        include_submissions: bool = True,
        prefer_cache: bool = True,
        refresh_if_empty: bool = True,
    ):
        """
        Assignments due in the next 7 days (inclusive of 'now'). DB-first; if miss, fetch & persist.
        """
        tz = ZoneInfo(tz_str)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)
        end_utc = (now_local + timedelta(days=7)).astimezone(timezone.utc)

        start_iso = self._dt_to_iso_z(now_utc)
        end_iso = self._dt_to_iso_z(end_utc)

        if prefer_cache:
            cached = self._get_from_db_window(start_iso, end_iso, course_id=course_id)
            if cached:
                return cached

        fetched = self._fetch_and_filter_window(canvas_auth, start_utc=now_utc, end_utc=end_utc,
                                                course_id=course_id, include_submissions=include_submissions)      
        print(fetched[0])
        if fetched:
            self.repo.bulk_upsert_from_payload(fetched)
        return fetched

    def _get_from_db_window(self, start_iso: str, end_iso: str, course_id: int | None):
        """
        Read assignments due in [start_iso, end_iso) from DB and reshape to your payload.
        """
        rows = self.repo.list_assignments_due_between(start_iso, end_iso, course_id=course_id)
        if not rows:
            return []

        out = []
        for r in rows:
            try:
                assignment_obj = json.loads(r["raw_assignment_json"])
            except Exception:
                assignment_obj = {}

            out.append({
                "courseId": r["course_id"],
                "courseName": r.get("course_name"),
                "assignmentId": r["assignment_id"],
                "due_at": r.get("due_at"),
                "html_url": r.get("html_url"),
                "assignment": assignment_obj,
                "description_html": r.get("description_html") or "",
                "description_text": r.get("description_text") or "",
            })
        out.sort(key=lambda x: self._iso_to_dt(x["due_at"]) if x.get("due_at") else datetime.max.replace(tzinfo=timezone.utc))
        return out

    def _fetch_and_filter_window(
        self,
        canvas_auth: dict,
        start_utc: datetime,
        end_utc: datetime,
        course_id: int | None,
        include_submissions: bool,
    ):
        """
        Fetch from Canvas (bucket=upcoming), filter by [start_utc, end_utc), return payload list.
        """
        if course_id:
            course = self._request("GET", f"/courses/{course_id}", canvas_auth)
            courses = [{"id": course_id, "name": course.get("name", f"Course {course_id}")}]
        else:
            courses = self.get_all_courses(canvas_auth)

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

            params = {"bucket": "upcoming", "include[]": includes}
            assignments = self._paginated("GET", f"/courses/{cid}/assignments", canvas_auth, params=params)

            for a in assignments:
                due_at = a.get("due_at")
                if not due_at:
                    continue
                try:
                    due_dt_utc = self._iso_to_dt(due_at).astimezone(timezone.utc)
                except Exception:
                    continue
                if not (start_utc <= due_dt_utc < end_utc):
                    continue

                record = self._make_payload_record(cid, cname, a)
                # optionally attach submission flags (kept minimal here)
                if include_submissions:
                    sub = a.get("submission") or {}
                    record["has_submitted"] = bool(sub.get("submitted_at"))
                    record["submission"] = sub
                results.append(record)

        results.sort(key=lambda x: self._iso_to_dt(x["due_at"]) if x.get("due_at") else datetime.max.replace(tzinfo=timezone.utc))
        return results
    
    # Will run on a chron job to constantly look for new assignments every 10ish minutes
    def check_new_weekly_assignments(
        self,
        course_id: int | None = None,
        tz_str: str = "America/Phoenix",
        include_submissions: bool = False,
    ) -> list[dict]:

        tz = ZoneInfo(tz_str)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)
        days_until_sunday = (6 - now_local.weekday()) % 7
        end_of_week_local = (now_local + timedelta(days=days_until_sunday)).replace(
            hour=23, minute=59, second=0, microsecond=0
        )
        end_utc = end_of_week_local.astimezone(timezone.utc)

        start_iso = self._dt_to_iso_z(now_utc)
        end_iso = self._dt_to_iso_z(end_utc)

        #DB snapshot of what's already known in this window
        already = self.repo.list_assignments_due_between(start_iso, end_iso, course_id=course_id)
        already_keys = {(r["course_id"], r["assignment_id"]) for r in already}

        fetched = self._fetch_and_filter_window(
            canvas_auth=canvas_auth,
            start_utc=now_utc,
            end_utc=end_utc,
            course_id=course_id,
            include_submissions=include_submissions,
        )
        new_items = [
            rec for rec in fetched
            if (rec["courseId"], rec["assignmentId"]) not in already_keys
        ]

        if fetched:
            self.repo.bulk_upsert_from_payload(fetched)

        #Sort for more predictable output
        new_items.sort(
            key=lambda x: self._iso_to_dt(x.get("due_at") or "9999-12-31T23:59:59+00:00")
        )
        return new_items


if __name__ == "__main__":
    api = CanvasService()
    items = api.get_assignments_next_week(canvas_auth, course_id=52461)
    print(len(items), "items")
