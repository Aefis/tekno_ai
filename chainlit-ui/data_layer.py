"""
Custom Data Layer for Chainlit - Local SQLite storage
Enables conversation history sidebar like ChatGPT/Claude
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from chainlit.data import BaseDataLayer
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import User, PersistedUser
from chainlit.step import StepDict
from chainlit.element import ElementDict


class SQLiteDataLayer(BaseDataLayer):
    """SQLite-based data layer for local conversation persistence."""
    
    def __init__(self, db_path: str = "chainlit_data.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE,
                metadata TEXT,
                created_at TEXT
            )
        """)
        
        # Threads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                name TEXT,
                user_id TEXT,
                metadata TEXT,
                tags TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Steps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY,
                thread_id TEXT,
                parent_id TEXT,
                name TEXT,
                type TEXT,
                input TEXT,
                output TEXT,
                metadata TEXT,
                created_at TEXT,
                start_time TEXT,
                end_time TEXT,
                FOREIGN KEY (thread_id) REFERENCES threads(id)
            )
        """)
        
        # Elements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS elements (
                id TEXT PRIMARY KEY,
                thread_id TEXT,
                step_id TEXT,
                type TEXT,
                name TEXT,
                url TEXT,
                mime TEXT,
                content TEXT,
                display TEXT,
                for_id TEXT,
                FOREIGN KEY (thread_id) REFERENCES threads(id)
            )
        """)
        
        # Feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                step_id TEXT,
                value INTEGER,
                comment TEXT,
                strategy TEXT,
                FOREIGN KEY (step_id) REFERENCES steps(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
    
    # =====================
    # USER METHODS
    # =====================
    
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE identifier = ?", (identifier,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return PersistedUser(
                id=row[0],
                identifier=row[1],
                metadata=json.loads(row[2]) if row[2] else {},
                createdAt=row[3]
            )
        return None
    
    async def create_user(self, user: User) -> Optional[PersistedUser]:
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO users (id, identifier, metadata, created_at) VALUES (?, ?, ?, ?)",
                (user_id, user.identifier, json.dumps(user.metadata or {}), created_at)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # User already exists, fetch it
            conn.close()
            return await self.get_user(user.identifier)
        
        conn.close()
        
        return PersistedUser(
            id=user_id,
            identifier=user.identifier,
            metadata=user.metadata or {},
            createdAt=created_at
        )
    
    # =====================
    # THREAD METHODS
    # =====================
    
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM threads WHERE id = ?", (thread_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # Get steps for this thread
        cursor.execute("SELECT * FROM steps WHERE thread_id = ? ORDER BY created_at", (thread_id,))
        step_rows = cursor.fetchall()
        
        steps = []
        for step_row in step_rows:
            steps.append({
                "id": step_row[0],
                "threadId": step_row[1],
                "parentId": step_row[2],
                "name": step_row[3],
                "type": step_row[4],
                "input": step_row[5],
                "output": step_row[6],
                "metadata": json.loads(step_row[7]) if step_row[7] else {},
                "createdAt": step_row[8],
                "startTime": step_row[9],
                "endTime": step_row[10],
            })
        
        conn.close()
        
        return {
            "id": row[0],
            "name": row[1],
            "userId": row[2],
            "metadata": json.loads(row[3]) if row[3] else {},
            "tags": json.loads(row[4]) if row[4] else [],
            "createdAt": row[5],
            "steps": steps,
        }
    
    async def create_thread(
        self,
        thread_id: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> ThreadDict:
        thread_id = thread_id or str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO threads (id, name, user_id, metadata, tags, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                thread_id,
                name or "Nouvelle conversation",
                user_id,
                json.dumps(metadata or {}),
                json.dumps(tags or []),
                created_at,
                created_at
            )
        )
        conn.commit()
        conn.close()
        
        return {
            "id": thread_id,
            "name": name,
            "userId": user_id,
            "metadata": metadata or {},
            "tags": tags or [],
            "createdAt": created_at,
            "steps": [],
        }
    
    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if metadata is not None:
            updates.append("metadata = ?")
            values.append(json.dumps(metadata))
        if tags is not None:
            updates.append("tags = ?")
            values.append(json.dumps(tags))
        if user_id is not None:
            updates.append("user_id = ?")
            values.append(user_id)
        
        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(thread_id)
        
        cursor.execute(
            f"UPDATE threads SET {', '.join(updates)} WHERE id = ?",
            values
        )
        conn.commit()
        conn.close()
    
    async def delete_thread(self, thread_id: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
        cursor.execute("DELETE FROM elements WHERE thread_id = ?", (thread_id,))
        cursor.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        
        conn.commit()
        conn.close()
    
    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT * FROM threads"
        params = []
        conditions = []
        
        if filters.userId:
            conditions.append("user_id = ?")
            params.append(filters.userId)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY updated_at DESC"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Apply pagination
        query += f" LIMIT {pagination.first}"
        if pagination.cursor:
            query += f" OFFSET {int(pagination.cursor)}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        threads = []
        for row in rows:
            # Get first message as preview
            cursor.execute(
                "SELECT output FROM steps WHERE thread_id = ? AND type = 'user_message' ORDER BY created_at LIMIT 1",
                (row[0],)
            )
            first_msg = cursor.fetchone()
            
            threads.append({
                "id": row[0],
                "name": row[1] or (first_msg[0][:50] + "..." if first_msg and first_msg[0] and len(first_msg[0]) > 50 else (first_msg[0] if first_msg else "Nouvelle conversation")),
                "userId": row[2],
                "metadata": json.loads(row[3]) if row[3] else {},
                "tags": json.loads(row[4]) if row[4] else [],
                "createdAt": row[5],
                "steps": [],
            })
        
        conn.close()
        
        # Calculate pagination info
        has_next = len(threads) == pagination.first
        next_cursor = str(int(pagination.cursor or 0) + len(threads)) if has_next else None
        
        return PaginatedResponse(
            data=threads,
            pageInfo=PageInfo(
                hasNextPage=has_next,
                endCursor=next_cursor,
            ),
        )
    
    # =====================
    # STEP METHODS
    # =====================
    
    async def create_step(self, step_dict: StepDict):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO steps 
               (id, thread_id, parent_id, name, type, input, output, metadata, created_at, start_time, end_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                step_dict.get("id"),
                step_dict.get("threadId"),
                step_dict.get("parentId"),
                step_dict.get("name"),
                step_dict.get("type"),
                step_dict.get("input"),
                step_dict.get("output"),
                json.dumps(step_dict.get("metadata", {})),
                step_dict.get("createdAt"),
                step_dict.get("startTime"),
                step_dict.get("endTime"),
            )
        )
        
        # Update thread name with first user message
        if step_dict.get("type") == "user_message" and step_dict.get("output"):
            cursor.execute(
                "SELECT COUNT(*) FROM steps WHERE thread_id = ? AND type = 'user_message'",
                (step_dict.get("threadId"),)
            )
            count = cursor.fetchone()[0]
            if count == 1:  # First user message
                name = step_dict.get("output", "")[:50]
                if len(step_dict.get("output", "")) > 50:
                    name += "..."
                cursor.execute(
                    "UPDATE threads SET name = ? WHERE id = ?",
                    (name, step_dict.get("threadId"))
                )
        
        conn.commit()
        conn.close()
    
    async def update_step(self, step_dict: StepDict):
        await self.create_step(step_dict)
    
    async def delete_step(self, step_id: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM steps WHERE id = ?", (step_id,))
        conn.commit()
        conn.close()
    
    # =====================
    # ELEMENT METHODS
    # =====================
    
    async def create_element(self, element: ElementDict):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO elements 
               (id, thread_id, step_id, type, name, url, mime, content, display, for_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                element.get("id"),
                element.get("threadId"),
                element.get("stepId"),
                element.get("type"),
                element.get("name"),
                element.get("url"),
                element.get("mime"),
                element.get("content"),
                element.get("display"),
                element.get("forId"),
            )
        )
        conn.commit()
        conn.close()
    
    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM elements WHERE id = ? AND thread_id = ?",
            (element_id, thread_id)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "threadId": row[1],
                "stepId": row[2],
                "type": row[3],
                "name": row[4],
                "url": row[5],
                "mime": row[6],
                "content": row[7],
                "display": row[8],
                "forId": row[9],
            }
        return None
    
    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        conn = self._get_conn()
        cursor = conn.cursor()
        if thread_id:
            cursor.execute("DELETE FROM elements WHERE id = ? AND thread_id = ?", (element_id, thread_id))
        else:
            cursor.execute("DELETE FROM elements WHERE id = ?", (element_id,))
        conn.commit()
        conn.close()
    
    # =====================
    # FEEDBACK METHODS
    # =====================
    
    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback_id = feedback.id or str(uuid.uuid4())
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO feedback (id, step_id, value, comment, strategy)
               VALUES (?, ?, ?, ?, ?)""",
            (feedback_id, feedback.forId, feedback.value, feedback.comment, feedback.strategy)
        )
        conn.commit()
        conn.close()
        
        return feedback_id
    
    async def delete_feedback(self, feedback_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
        affected = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return affected
    
    # =====================
    # BUILD METHODS (required stubs)
    # =====================
    
    async def build_debug_url(self) -> str:
        return ""
    
    async def get_thread_author(self, thread_id: str) -> str:
        """Retourne l'auteur d'un thread."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM threads WHERE id = ?", (thread_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ""
    
    async def close(self):
        """Ferme les connexions à la base de données."""
        pass  # SQLite gère les connexions par requête, pas besoin de fermer globalement

