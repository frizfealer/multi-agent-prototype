import json
import os
import uuid

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    """Establishes a connection to the database."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def create_conversation(initial_agent="triage"):
    """Creates a new conversation and returns its ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    conversation_id = uuid.uuid4()
    cur.execute(
        "INSERT INTO Conversations (conversation_id, current_agent, context_data) VALUES (%s, %s, %s)",
        (str(conversation_id), initial_agent, json.dumps({})),
    )
    conn.commit()
    cur.close()
    conn.close()
    return conversation_id


def add_message(conversation_id, role, content, agent=None, task_id=None):
    """Adds a message to a conversation."""
    conn = get_db_connection()
    cur = conn.cursor()
    message_id = uuid.uuid4()
    cur.execute(
        "INSERT INTO Messages (message_id, conversation_id, role, agent, content, task_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (str(message_id), str(conversation_id), role, agent, content, str(task_id) if task_id else None),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_conversation_state(conversation_id):
    """Retrieves the full state of a conversation."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT current_agent, context_data FROM Conversations WHERE conversation_id = %s", (str(conversation_id),)
    )
    conversation_data = cur.fetchone()

    cur.execute(
        "SELECT role, agent, content, task_id FROM Messages WHERE conversation_id = %s ORDER BY created_at ASC",
        (str(conversation_id),),
    )
    messages = cur.fetchall()

    cur.close()
    conn.close()

    if not conversation_data:
        return None

    return {
        "current_agent": conversation_data[0],
        "context_data": conversation_data[1],
        "history": [
            {"role": role, "agent": agent, "content": content, "task_id": task_id}
            for role, agent, content, task_id in messages
        ],
    }


def update_conversation_state(conversation_id, current_agent=None, context_data=None):
    """Updates the state of a conversation."""
    conn = get_db_connection()
    cur = conn.cursor()

    if current_agent:
        cur.execute(
            "UPDATE Conversations SET current_agent = %s, updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s",
            (current_agent, str(conversation_id)),
        )

    if context_data:
        cur.execute(
            "UPDATE Conversations SET context_data = %s, updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s",
            (json.dumps(context_data), str(conversation_id)),
        )

    conn.commit()
    cur.close()
    conn.close()


def create_task(task_dict):
    """Creates a new task from a dictionary."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    task_id = task_dict.get("task_id", str(uuid.uuid4()))
    conversation_id = task_dict["conversation_id"]
    goal = task_dict["goal"]
    domain = task_dict["domain"]
    task_status = task_dict.get("status", "pending")
    context = json.dumps(task_dict.get("context", {}))
    
    cur.execute(
        "INSERT INTO Task (task_id, conversation_id, goal, domain, task_status, context) VALUES (%s, %s, %s, %s, %s, %s)",
        (task_id, str(conversation_id), goal, domain, task_status, context),
    )
    conn.commit()
    cur.close()
    conn.close()
    return task_id


def get_pending_tasks_by_conversation(conversation_id):
    """Retrieves all pending tasks for a conversation."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT task_id, goal, domain, task_status, context, result, created_at, updated_at FROM Task WHERE conversation_id = %s AND task_status = 'pending' ORDER BY created_at ASC",
        (str(conversation_id),),
    )
    tasks = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "task_id": task[0],
            "goal": task[1],
            "domain": task[2],
            "task_status": task[3],
            "context": json.loads(task[4]) if task[4] else {},
            "result": task[5],
            "created_at": task[6],
            "updated_at": task[7],
        }
        for task in tasks
    ]


def start_tasks(conversation_id, task_ids=None):
    """Start tasks for a conversation. If task_ids not provided, start all pending tasks."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if task_ids:
        # Start specific tasks
        placeholders = ','.join(['%s'] * len(task_ids))
        cur.execute(
            f"UPDATE Task SET task_status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s AND task_id IN ({placeholders})",
            [str(conversation_id)] + [str(task_id) for task_id in task_ids]
        )
    else:
        # Start all pending tasks
        cur.execute(
            "UPDATE Task SET task_status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s AND task_status = 'pending'",
            (str(conversation_id),)
        )
    
    conn.commit()
    affected_rows = cur.rowcount
    cur.close()
    conn.close()
    
    return affected_rows


def update_task(task_id, task_status=None, result=None, context=None):
    """Updates a task's status, result, or context."""
    conn = get_db_connection()
    cur = conn.cursor()

    updates = []
    params = []

    if task_status:
        updates.append("task_status = %s")
        params.append(task_status)

    if result:
        updates.append("result = %s")
        params.append(result)

    if context:
        updates.append("context = %s")
        params.append(context)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(str(task_id))

        query = f"UPDATE Task SET {', '.join(updates)} WHERE task_id = %s"
        cur.execute(query, params)
        conn.commit()

    cur.close()
    conn.close()


def get_task(task_id):
    """Retrieves a task by its ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT task_id, conversation_id, goal, domain, task_status, context, result, created_at, updated_at FROM Task WHERE task_id = %s",
        (str(task_id),),
    )
    task_data = cur.fetchone()
    cur.close()
    conn.close()

    if not task_data:
        return None

    return {
        "task_id": task_data[0],
        "conversation_id": task_data[1],
        "goal": task_data[2],
        "domain": task_data[3],
        "task_status": task_data[4],
        "context": task_data[5],
        "result": task_data[6],
        "created_at": task_data[7],
        "updated_at": task_data[8],
    }


def get_tasks_by_conversation(conversation_id):
    """Retrieves all tasks for a conversation."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT task_id, goal, domain, task_status, context, result, created_at, updated_at FROM Task WHERE conversation_id = %s ORDER BY created_at ASC",
        (str(conversation_id),),
    )
    tasks = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "task_id": task[0],
            "goal": task[1],
            "domain": task[2],
            "task_status": task[3],
            "context": task[4],
            "result": task[5],
            "created_at": task[6],
            "updated_at": task[7],
        }
        for task in tasks
    ]
