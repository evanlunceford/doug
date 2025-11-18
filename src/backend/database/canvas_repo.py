# canvas_db.py
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

CANVAS_DB_PATH = str(BASE_DIR / "canvas.db")

def _connect(db_path: str = CANVAS_DB_PATH) -> sqlite3.Connection:
    print(CANVAS_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def _tx(db_path: str = CANVAS_DB_PATH):
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}

def _b(val) -> int:
    return int(bool(val))


class CanvasRepo:
    def __init__(self, db_path: str = CANVAS_DB_PATH):
        self.db_path = db_path
        # Ensure database exists
        if not Path(db_path).exists():
            CanvasRepo.create_canvas_db(Path(db_path))

    # ------------- CREATE / UPSERT -------------
    @staticmethod
    def create_canvas_db(db_path: Path = CANVAS_DB_PATH) -> None:
        p = Path(db_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f"[SQLite] Initializing DB at: {p}")

        with sqlite3.connect(str(p)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cur = conn.cursor()

            cur.executescript("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                course_name TEXT,
                assignment_id INTEGER NOT NULL,
                due_at TEXT,
                html_url TEXT,
                description_html TEXT,
                description_text TEXT,

                name TEXT,
                position INTEGER,
                description TEXT,
                points_possible REAL,
                grading_type TEXT,
                created_at TEXT,
                updated_at TEXT,
                lock_at TEXT,
                unlock_at TEXT,
                assignment_group_id INTEGER,
                peer_reviews INTEGER,
                anonymous_peer_reviews INTEGER,
                automatic_peer_reviews INTEGER,
                intra_group_peer_reviews INTEGER,
                post_to_sis INTEGER,
                grade_group_students_individually INTEGER,
                group_category_id INTEGER,
                grading_standard_id INTEGER,
                moderated_grading INTEGER,
                hide_in_gradebook INTEGER,
                omit_from_final_grade INTEGER,
                suppress_assignment INTEGER,
                anonymous_instructor_annotations INTEGER,
                anonymous_grading INTEGER,
                allowed_attempts INTEGER,
                annotatable_attachment_id INTEGER,
                secure_params TEXT,
                lti_context_id TEXT,
                final_grader_id INTEGER,
                grader_count INTEGER,
                graders_anonymous_to_graders INTEGER,
                grader_comments_visible_to_graders INTEGER,
                grader_names_visible_to_final_grader INTEGER,
                has_submitted_submissions INTEGER,
                due_date_required INTEGER,
                max_name_length INTEGER,
                in_closed_grading_period INTEGER,
                graded_submissions_exist INTEGER,
                is_quiz_assignment INTEGER,
                can_duplicate INTEGER,
                original_course_id INTEGER,
                original_assignment_id INTEGER,
                original_lti_resource_link_id TEXT,
                original_assignment_name TEXT,
                original_quiz_id INTEGER,
                workflow_state TEXT,
                important_dates INTEGER,
                muted INTEGER,
                published INTEGER,
                only_visible_to_overrides INTEGER,
                visible_to_everyone INTEGER,
                bucket TEXT,
                locked_for_user INTEGER,
                submissions_download_url TEXT,
                post_manually INTEGER,
                anonymize_students INTEGER,
                require_lockdown_browser INTEGER,
                restrict_quantitative_data INTEGER,
                quiz_id INTEGER,

                raw_assignment_json TEXT NOT NULL,
                uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE (course_id, assignment_id)
            );

            CREATE INDEX IF NOT EXISTS idx_assignments_course ON assignments(course_id);
            CREATE INDEX IF NOT EXISTS idx_assignments_due ON assignments(due_at);
            CREATE INDEX IF NOT EXISTS idx_assignments_bucket ON assignments(bucket);
            CREATE INDEX IF NOT EXISTS idx_assignments_workflow ON assignments(workflow_state);

            CREATE TABLE IF NOT EXISTS assignment_submission_types (
                course_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                submission_type TEXT NOT NULL,
                PRIMARY KEY (course_id, assignment_id, submission_type),
                FOREIGN KEY (course_id, assignment_id)
                  REFERENCES assignments(course_id, assignment_id)
                  ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS assignment_all_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                title TEXT,
                base INTEGER,
                due_at TEXT,
                unlock_at TEXT,
                lock_at TEXT,
                FOREIGN KEY (course_id, assignment_id)
                  REFERENCES assignments(course_id, assignment_id)
                  ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_all_dates_assignment
              ON assignment_all_dates(course_id, assignment_id);

            CREATE TABLE IF NOT EXISTS assignment_discussion_topics (
                course_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                discussion_id INTEGER,
                title TEXT,
                delayed_post_at TEXT,
                lock_at TEXT,
                created_at TEXT,
                last_reply_at TEXT,
                posted_at TEXT,
                root_topic_id INTEGER,
                podcast_has_student_posts INTEGER,
                discussion_type TEXT,
                allow_rating INTEGER,
                only_graders_can_rate INTEGER,
                sort_by_rating INTEGER,
                is_section_specific INTEGER,
                anonymous_state TEXT,
                summary_enabled INTEGER,
                discussion_subentry_count INTEGER,
                read_state TEXT,
                unread_count INTEGER,
                subscribed INTEGER,
                published INTEGER,
                can_unpublish INTEGER,
                locked INTEGER,
                can_lock INTEGER,
                comments_disabled INTEGER,
                html_url TEXT,
                url TEXT,
                pinned INTEGER,
                group_category_id INTEGER,
                can_group INTEGER,
                message TEXT,
                todo_date TEXT,
                user_pronouns TEXT,
                is_announcement INTEGER,
                sort_order TEXT,
                sort_order_locked INTEGER,
                expanded INTEGER,
                expanded_locked INTEGER,
                PRIMARY KEY (course_id, assignment_id),
                FOREIGN KEY (course_id, assignment_id)
                  REFERENCES assignments(course_id, assignment_id)
                  ON DELETE CASCADE
            );
            """)

        print("[SQLite] Schema ready ✔")

    def upsert_assignment_from_payload(self, p: Dict[str, Any]) -> None:
        """
        Upsert one assignment wrapper item from your API payload (the object in payload[]).
        Handles main row + submission_types + all_dates + discussion_topic.
        """
        a = p["assignment"]
        cid = p["courseId"]

        with _tx(self.db_path) as conn:
            cur = conn.cursor()
            
            #To place as the VALUES inputs
            placeholders = ",".join(["?"] * 67)

            # main row (unchanged; includes course_id in the insert + unique key)
            cur.execute(f'''
            INSERT INTO assignments (
                course_id, course_name, assignment_id, due_at, html_url,
                description_html, description_text,
                name, position, description, points_possible, grading_type, created_at, updated_at,
                lock_at, unlock_at, assignment_group_id, peer_reviews, anonymous_peer_reviews,
                automatic_peer_reviews, intra_group_peer_reviews, post_to_sis, grade_group_students_individually,
                group_category_id, grading_standard_id, moderated_grading, hide_in_gradebook,
                omit_from_final_grade, suppress_assignment, anonymous_instructor_annotations,
                anonymous_grading, allowed_attempts, annotatable_attachment_id, secure_params, lti_context_id,
                final_grader_id, grader_count, graders_anonymous_to_graders, grader_comments_visible_to_graders,
                grader_names_visible_to_final_grader, has_submitted_submissions, due_date_required, max_name_length,
                in_closed_grading_period, graded_submissions_exist, is_quiz_assignment, can_duplicate,
                original_course_id, original_assignment_id, original_lti_resource_link_id, original_assignment_name,
                original_quiz_id, workflow_state, important_dates, muted, published, only_visible_to_overrides,
                visible_to_everyone, bucket, locked_for_user, submissions_download_url, post_manually,
                anonymize_students, require_lockdown_browser, restrict_quantitative_data, quiz_id,
                raw_assignment_json
            ) VALUES ({placeholders})
            ON CONFLICT(course_id, assignment_id) DO UPDATE SET
                course_name=excluded.course_name,
                due_at=excluded.due_at,
                html_url=excluded.html_url,
                description_html=excluded.description_html,
                description_text=excluded.description_text,
                name=excluded.name,
                position=excluded.position,
                description=excluded.description,
                points_possible=excluded.points_possible,
                grading_type=excluded.grading_type,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at,
                lock_at=excluded.lock_at,
                unlock_at=excluded.unlock_at,
                assignment_group_id=excluded.assignment_group_id,
                peer_reviews=excluded.peer_reviews,
                anonymous_peer_reviews=excluded.anonymous_peer_reviews,
                automatic_peer_reviews=excluded.automatic_peer_reviews,
                intra_group_peer_reviews=excluded.intra_group_peer_reviews,
                post_to_sis=excluded.post_to_sis,
                grade_group_students_individually=excluded.grade_group_students_individually,
                group_category_id=excluded.group_category_id,
                grading_standard_id=excluded.grading_standard_id,
                moderated_grading=excluded.moderated_grading,
                hide_in_gradebook=excluded.hide_in_gradebook,
                omit_from_final_grade=excluded.omit_from_final_grade,
                suppress_assignment=excluded.suppress_assignment,
                anonymous_instructor_annotations=excluded.anonymous_instructor_annotations,
                anonymous_grading=excluded.anonymous_grading,
                allowed_attempts=excluded.allowed_attempts,
                annotatable_attachment_id=excluded.annotatable_attachment_id,
                secure_params=excluded.secure_params,
                lti_context_id=excluded.lti_context_id,
                final_grader_id=excluded.final_grader_id,
                grader_count=excluded.grader_count,
                graders_anonymous_to_graders=excluded.graders_anonymous_to_graders,
                grader_comments_visible_to_graders=excluded.grader_comments_visible_to_graders,
                grader_names_visible_to_final_grader=excluded.grader_names_visible_to_final_grader,
                has_submitted_submissions=excluded.has_submitted_submissions,
                due_date_required=excluded.due_date_required,
                max_name_length=excluded.max_name_length,
                in_closed_grading_period=excluded.in_closed_grading_period,
                graded_submissions_exist=excluded.graded_submissions_exist,
                is_quiz_assignment=excluded.is_quiz_assignment,
                can_duplicate=excluded.can_duplicate,
                original_course_id=excluded.original_course_id,
                original_assignment_id=excluded.original_assignment_id,
                original_lti_resource_link_id=excluded.original_lti_resource_link_id,
                original_assignment_name=excluded.original_assignment_name,
                original_quiz_id=excluded.original_quiz_id,
                workflow_state=excluded.workflow_state,
                important_dates=excluded.important_dates,
                muted=excluded.muted,
                published=excluded.published,
                only_visible_to_overrides=excluded.only_visible_to_overrides,
                visible_to_everyone=excluded.visible_to_everyone,
                bucket=excluded.bucket,
                locked_for_user=excluded.locked_for_user,
                submissions_download_url=excluded.submissions_download_url,
                post_manually=excluded.post_manually,
                anonymize_students=excluded.anonymize_students,
                require_lockdown_browser=excluded.require_lockdown_browser,
                restrict_quantitative_data=excluded.restrict_quantitative_data,
                quiz_id=excluded.quiz_id,
                raw_assignment_json=excluded.raw_assignment_json
            ''', (
                cid, p.get("courseName"), a["id"], a.get("due_at"), a.get("html_url"),
                p.get("description_html"), p.get("description_text"),
                a.get("name"), a.get("position"), a.get("description"), a.get("points_possible"), a.get("grading_type"),
                a.get("created_at"), a.get("updated_at"),
                a.get("lock_at"), a.get("unlock_at"), a.get("assignment_group_id"),
                _b(a.get("peer_reviews")), _b(a.get("anonymous_peer_reviews")),
                _b(a.get("automatic_peer_reviews")), _b(a.get("intra_group_peer_reviews")),
                _b(a.get("post_to_sis")), _b(a.get("grade_group_students_individually")),
                a.get("group_category_id"), a.get("grading_standard_id"), _b(a.get("moderated_grading")),
                _b(a.get("hide_in_gradebook")), _b(a.get("omit_from_final_grade")),
                _b(a.get("suppress_assignment")), _b(a.get("anonymous_instructor_annotations")),
                _b(a.get("anonymous_grading")), a.get("allowed_attempts"), a.get("annotatable_attachment_id"),
                a.get("secure_params"), a.get("lti_context_id"), a.get("final_grader_id"), a.get("grader_count"),
                _b(a.get("graders_anonymous_to_graders")),
                _b(a.get("grader_comments_visible_to_graders")),
                _b(a.get("grader_names_visible_to_final_grader")),
                _b(a.get("has_submitted_submissions")), _b(a.get("due_date_required")),
                a.get("max_name_length"), _b(a.get("in_closed_grading_period")),
                _b(a.get("graded_submissions_exist")), _b(a.get("is_quiz_assignment")),
                _b(a.get("can_duplicate")), a.get("original_course_id"), a.get("original_assignment_id"),
                a.get("original_lti_resource_link_id"), a.get("original_assignment_name"), a.get("original_quiz_id"),
                a.get("workflow_state"), _b(a.get("important_dates")), _b(a.get("muted")),
                _b(a.get("published")), _b(a.get("only_visible_to_overrides")),
                _b(a.get("visible_to_everyone")), a.get("bucket"), _b(a.get("locked_for_user")),
                a.get("submissions_download_url"), _b(a.get("post_manually")),
                _b(a.get("anonymize_students")), _b(a.get("require_lockdown_browser")),
                _b(a.get("restrict_quantitative_data")), a.get("quiz_id"),
                json.dumps(a)
            ))

            # child: submission_types (now scoped by course_id, assignment_id)
            cur.execute('DELETE FROM assignment_submission_types WHERE course_id=? AND assignment_id=?', (cid, a["id"]))
            for st in (a.get("submission_types") or []):
                cur.execute(
                    'INSERT OR IGNORE INTO assignment_submission_types (course_id, assignment_id, submission_type) VALUES (?,?,?)',
                    (cid, a["id"], st)
                )

            # child: all_dates
            cur.execute('DELETE FROM assignment_all_dates WHERE course_id=? AND assignment_id=?', (cid, a["id"]))
            for ad in (a.get("all_dates") or []):
                cur.execute(
                    '''
                    INSERT INTO assignment_all_dates (course_id, assignment_id, title, base, due_at, unlock_at, lock_at)
                    VALUES (?,?,?,?,?,?,?)
                    ''',
                    (cid, a["id"], ad.get("title"), _b(ad.get("base")), ad.get("due_at"), ad.get("unlock_at"), ad.get("lock_at"))
                )

            # child: discussion_topic
            dt = a.get("discussion_topic")
            if dt:
                cur.execute(
                    '''
                    INSERT INTO assignment_discussion_topics (
                        course_id, assignment_id, discussion_id, title, delayed_post_at, lock_at, created_at, last_reply_at, posted_at,
                        root_topic_id, podcast_has_student_posts, discussion_type, allow_rating, only_graders_can_rate,
                        sort_by_rating, is_section_specific, anonymous_state, summary_enabled, discussion_subentry_count,
                        read_state, unread_count, subscribed, published, can_unpublish, locked, can_lock, comments_disabled,
                        html_url, url, pinned, group_category_id, can_group, message, todo_date, user_pronouns, is_announcement,
                        sort_order, sort_order_locked, expanded, expanded_locked
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(course_id, assignment_id) DO UPDATE SET
                        discussion_id=excluded.discussion_id,
                        title=excluded.title,
                        delayed_post_at=excluded.delayed_post_at,
                        lock_at=excluded.lock_at,
                        created_at=excluded.created_at,
                        last_reply_at=excluded.last_reply_at,
                        posted_at=excluded.posted_at,
                        root_topic_id=excluded.root_topic_id,
                        podcast_has_student_posts=excluded.podcast_has_student_posts,
                        discussion_type=excluded.discussion_type,
                        allow_rating=excluded.allow_rating,
                        only_graders_can_rate=excluded.only_graders_can_rate,
                        sort_by_rating=excluded.sort_by_rating,
                        is_section_specific=excluded.is_section_specific,
                        anonymous_state=excluded.anonymous_state,
                        summary_enabled=excluded.summary_enabled,
                        discussion_subentry_count=excluded.discussion_subentry_count,
                        read_state=excluded.read_state,
                        unread_count=excluded.unread_count,
                        subscribed=excluded.subscribed,
                        published=excluded.published,
                        can_unpublish=excluded.can_unpublish,
                        locked=excluded.locked,
                        can_lock=excluded.can_lock,
                        comments_disabled=excluded.comments_disabled,
                        html_url=excluded.html_url,
                        url=excluded.url,
                        pinned=excluded.pinned,
                        group_category_id=excluded.group_category_id,
                        can_group=excluded.can_group,
                        message=excluded.message,
                        todo_date=excluded.todo_date,
                        user_pronouns=excluded.user_pronouns,
                        is_announcement=excluded.is_announcement,
                        sort_order=excluded.sort_order,
                        sort_order_locked=excluded.sort_order_locked,
                        expanded=excluded.expanded,
                        expanded_locked=excluded.expanded_locked
                    ''',
                    (
                        cid, a["id"], dt.get("id"), dt.get("title"), dt.get("delayed_post_at"), dt.get("lock_at"),
                        dt.get("created_at"), dt.get("last_reply_at"), dt.get("posted_at"),
                        dt.get("root_topic_id"), _b(dt.get("podcast_has_student_posts")),
                        dt.get("discussion_type"), _b(dt.get("allow_rating")),
                        _b(dt.get("only_graders_can_rate")), _b(dt.get("sort_by_rating")),
                        _b(dt.get("is_section_specific")), dt.get("anonymous_state"),
                        _b(dt.get("summary_enabled")), dt.get("discussion_subentry_count"),
                        dt.get("read_state"), dt.get("unread_count"), _b(dt.get("subscribed")),
                        _b(dt.get("published")), _b(dt.get("can_unpublish")), _b(dt.get("locked")),
                        _b(dt.get("can_lock")), _b(dt.get("comments_disabled")), dt.get("html_url"), dt.get("url"),
                        _b(dt.get("pinned")), dt.get("group_category_id"), _b(dt.get("can_group")),
                        dt.get("message"), dt.get("todo_date"), dt.get("user_pronouns"),
                        _b(dt.get("is_announcement")), dt.get("sort_order"), _b(dt.get("sort_order_locked")),
                        _b(dt.get("expanded")), _b(dt.get("expanded_locked"))
                    )
                )


    def bulk_upsert_from_payload(self, payload_items: Iterable[Dict[str, Any]]) -> None:
        for p in payload_items:
            self.upsert_assignment_from_payload(p)

    # ------------- READ -------------

    def get_assignment(self, course_id: int, assignment_id: int) -> Optional[dict]:
        with _tx(self.db_path) as conn:
            row = conn.execute('''
                SELECT * FROM assignments WHERE course_id=? AND assignment_id=? LIMIT 1
            ''', (course_id, assignment_id)).fetchone()
            return _row_to_dict(row) if row else None

    def get_assignment_full(self, course_id: int, assignment_id: int) -> Optional[dict]:
        with _tx(self.db_path) as conn:
            main = conn.execute(
                'SELECT * FROM assignments WHERE course_id=? AND assignment_id=?',
                (course_id, assignment_id)
            ).fetchone()
            if not main:
                return None
            main_d = _row_to_dict(main)

            subs = conn.execute(
                'SELECT submission_type FROM assignment_submission_types WHERE course_id=? AND assignment_id=?',
                (course_id, assignment_id)
            ).fetchall()
            all_dates = conn.execute(
                '''SELECT id, title, base, due_at, unlock_at, lock_at
                FROM assignment_all_dates
                WHERE course_id=? AND assignment_id=?
                ORDER BY id''',
                (course_id, assignment_id)
            ).fetchall()
            dt = conn.execute(
                'SELECT * FROM assignment_discussion_topics WHERE course_id=? AND assignment_id=?',
                (course_id, assignment_id)
            ).fetchone()

            main_d["submission_types"] = [r["submission_type"] for r in subs]
            main_d["all_dates"] = [_row_to_dict(r) for r in all_dates]
            main_d["discussion_topic"] = _row_to_dict(dt) if dt else None
            return main_d


    def list_assignments_by_course(self, course_id: int, limit: int = 100, offset: int = 0) -> List[dict]:
        with _tx(self.db_path) as conn:
            rows = conn.execute('''
                SELECT * FROM assignments
                WHERE course_id=?
                ORDER BY datetime(due_at) NULLS LAST, assignment_id
                LIMIT ? OFFSET ?
            ''', (course_id, limit, offset)).fetchall()
            return [_row_to_dict(r) for r in rows]

    def list_assignments_due_between(self, start_iso: str, end_iso: str, course_id: Optional[int] = None) -> List[dict]:
        """
        Pass start/end as ISO8601 strings (UTC) like '2025-11-01T06:59:59Z'.
        """
        q = '''
            SELECT * FROM assignments
            WHERE due_at IS NOT NULL
              AND datetime(due_at) >= datetime(?)
              AND datetime(due_at) <  datetime(?)
        '''
        params: Tuple[Any, ...] = (start_iso, end_iso)
        if course_id is not None:
            q += ' AND course_id=?'
            params = (start_iso, end_iso, course_id)
        q += ' ORDER BY datetime(due_at) ASC'
        with _tx(self.db_path) as conn:
            rows = conn.execute(q, params).fetchall()
            return [_row_to_dict(r) for r in rows]

    def search_assignments(self, query_text: str, limit: int = 50, offset: int = 0) -> List[dict]:
        """
        Simple LIKE search across name, course_name, description_text/HTML.
        """
        like = f"%{query_text}%"
        with _tx(self.db_path) as conn:
            rows = conn.execute('''
                SELECT * FROM assignments
                WHERE (name LIKE ? OR course_name LIKE ? OR description_text LIKE ? OR description_html LIKE ?)
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (like, like, like, like, limit, offset)).fetchall()
            return [_row_to_dict(r) for r in rows]

    # ------------- UPDATE -------------

    def update_assignment_fields(self, course_id: int, assignment_id: int, **fields) -> int:
        """
        Partial update of scalar columns in assignments (e.g., workflow_state='published', bucket='upcoming').
        Returns # rows updated.
        """
        if not fields:
            return 0
        allowed = {
            "due_at","html_url","description_html","description_text","name","position","description",
            "points_possible","grading_type","updated_at","lock_at","unlock_at","assignment_group_id",
            "peer_reviews","anonymous_peer_reviews","automatic_peer_reviews","intra_group_peer_reviews",
            "post_to_sis","grade_group_students_individually","group_category_id","grading_standard_id",
            "moderated_grading","hide_in_gradebook","omit_from_final_grade","suppress_assignment",
            "anonymous_instructor_annotations","anonymous_grading","allowed_attempts","annotatable_attachment_id",
            "secure_params","lti_context_id","final_grader_id","grader_count","graders_anonymous_to_graders",
            "grader_comments_visible_to_graders","grader_names_visible_to_final_grader","has_submitted_submissions",
            "due_date_required","max_name_length","in_closed_grading_period","graded_submissions_exist",
            "is_quiz_assignment","can_duplicate","original_course_id","original_assignment_id",
            "original_lti_resource_link_id","original_assignment_name","original_quiz_id","workflow_state",
            "important_dates","muted","published","only_visible_to_overrides","visible_to_everyone","bucket",
            "locked_for_user","submissions_download_url","post_manually","anonymize_students",
            "require_lockdown_browser","restrict_quantitative_data","quiz_id"
        }
        sets = []
        params: List[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets.append(f"{k}=?")
            # normalize booleans to 0/1 for bool fields (SQLite is lenient, but be consistent)
            if isinstance(v, bool):
                params.append(_b(v))
            else:
                params.append(v)
        if not sets:
            return 0
        params.extend([course_id, assignment_id])
        with _tx(self.db_path) as conn:
            cur = conn.execute(f'''
                UPDATE assignments SET {", ".join(sets)}
                WHERE course_id=? AND assignment_id=?
            ''', params)
            return cur.rowcount

    # ------------- DELETE -------------

    def delete_assignment(self, course_id: int, assignment_id: int) -> int:
        """
        Deletes the assignment and cascades to child tables (thanks to FK ON DELETE CASCADE).
        Returns # rows deleted from assignments.
        """
        with _tx(self.db_path) as conn:
            cur = conn.execute('DELETE FROM assignments WHERE course_id=? AND assignment_id=?',
                               (course_id, assignment_id))
            return cur.rowcount

    def delete_assignments_by_course(self, course_id: int) -> int:
        with _tx(self.db_path) as conn:
            cur = conn.execute('DELETE FROM assignments WHERE course_id=?', (course_id,))
            return cur.rowcount
        

if __name__ == "__main__":
    canvas_repo = CanvasRepo()
    canvas_repo.create_canvas_db()
