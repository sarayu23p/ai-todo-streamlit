import json
from datetime import datetime
from typing import Dict, Any, List

import streamlit as st

st.set_page_config(page_title="AI To‑Do List", page_icon="📝", layout="centered")

# ------------------------------
# Helpers
# ------------------------------

def keyword_category(task: str) -> str:
    task_l = task.lower()
    rules = {
        "work": ["report", "meeting", "email", "client", "analysis", "dashboard", "ppt", "excel", "jira"],
        "study": ["read", "study", "course", "assignment", "notebook", "lecture", "learn"],
        "personal": ["call", "doctor", "medicine", "family", "clean", "groceries", "shopping"],
        "finance": ["tax", "invoice", "budget", "payment", "salary", "bill"],
        "fitness": ["gym", "run", "walk", "yoga", "workout", "swim"],
        "errand": ["buy", "pick", "drop", "bank", "post", "repair"],
    }
    for cat, kws in rules.items():
        if any(kw in task_l for kw in kws):
            return cat.title()
    return "General"


def ai_enrich_task(task: str, api_key: str | None) -> Dict[str, Any]:
    """
    If api_key exists, call OpenAI to suggest a category, priority, and 2-5 subtasks (JSON).
    Else, return a lightweight rule-based suggestion.
    """
    # Fallback defaults
    suggestion = {
        "category": keyword_category(task),
        "priority": "Medium",
        "subtasks": []
    }

    if not api_key:
        return suggestion

    try:
        # Import inside the function so the app still runs if package isn't present locally
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system = (
            "You are an assistant that classifies a to-do task and suggests helpful subtasks. "
            "Return STRICT JSON with keys: category (one of: Work, Study, Personal, Finance, Fitness, Errand, General), "
            "priority (High/Medium/Low), subtasks (list of 2-5 concise strings). Do NOT include any other text."
        )
        user = f"Task: {task}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content.strip()
        # Ensure we only parse JSON portion
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end+1]
        suggested = json.loads(content)
        # Validate keys
        if "category" in suggested and "priority" in suggested and "subtasks" in suggested:
            suggestion["category"] = str(suggested["category"]).title()
            pr = str(suggested["priority"]).title()
            suggestion["priority"] = pr if pr in {"High", "Medium", "Low"} else "Medium"
            if isinstance(suggested["subtasks"], list):
                suggestion["subtasks"] = [str(s).strip() for s in suggested["subtasks"][:5]]
    except Exception as e:
        # Silent fallback
        pass

    return suggestion


def init_state():
    if "tasks" not in st.session_state:
        st.session_state.tasks: List[Dict[str, Any]] = []


def add_task(task_text: str, ai_key: str | None):
    if not task_text.strip():
        st.warning("Please enter a valid task.")
        return
    enrich = ai_enrich_task(task_text.strip(), ai_key)
    st.session_state.tasks.append({
        "task": task_text.strip(),
        "done": False,
        "category": enrich.get("category", "General"),
        "priority": enrich.get("priority", "Medium"),
        "subtasks": enrich.get("subtasks", []),
        "created_at": datetime.utcnow().isoformat() + "Z",
    })
    st.success("Task added!")


def remove_task(idx: int):
    st.session_state.tasks.pop(idx)
    st.rerun()


def clear_completed():
    st.session_state.tasks = [t for t in st.session_state.tasks if not t.get("done")]
    st.rerun()


def download_tasks_button():
    data = json.dumps(st.session_state.tasks, indent=2)
    st.download_button("⬇️ Download tasks as JSON", data=data, file_name="tasks.json", mime="application/json")


def upload_tasks():
    uploaded = st.file_uploader("Upload tasks JSON", type=["json"], label_visibility="collapsed")
    if uploaded is not None:
        try:
            tasks = json.load(uploaded)
            if isinstance(tasks, list):
                st.session_state.tasks = tasks
                st.success("Tasks loaded from file.")
                st.rerun()
            else:
                st.error("Invalid file format.")
        except Exception as e:
            st.error(f"Could not load file: {e}")


# ------------------------------
# UI
# ------------------------------
init_state()

st.title("📝 AI-Powered To‑Do List")

with st.sidebar:
    st.header("⚙️ Settings")
    st.caption("Optional: add your OpenAI API key to get AI suggestions for category, priority, and subtasks.")
    # Prefer secrets; allow manual input for local testing.
    default_key = st.secrets.get("OPENAI_API_KEY", None)
    api_key = st.text_input("OpenAI API Key (optional)", type="password", value=default_key if default_key else "")
    st.markdown("---")
    st.subheader("Import / Export")
    download_tasks_button()
    upload_tasks()
    st.markdown("---")
    if st.button("🧹 Clear completed"):
        clear_completed()
    st.caption("Data is stored in your session only. Use Download to save your list.")

# Add Task
with st.container():
    st.subheader("Add a new task")
    col_a, col_b = st.columns([0.7, 0.3])
    with col_a:
        new_task = st.text_input("What do you need to do?", placeholder="e.g., Prepare XGBoost slides for interview")
    with col_b:
        st.write("")  # spacing
        if st.button("➕ Add Task", use_container_width=True):
            add_task(new_task, api_key.strip() or None)

# Task list
st.subheader("Your tasks")
if not st.session_state.tasks:
    st.info("No tasks yet. Add one above to get started.")
else:
    for i, t in enumerate(st.session_state.tasks):
        with st.container(border=True):
            top = st.columns([0.06, 0.64, 0.12, 0.18])
            with top[0]:
                st.session_state.tasks[i]["done"] = st.checkbox("", value=t.get("done", False), key=f"done_{i}")
            with top[1]:
                st.write(f"**{t['task']}**")
                st.caption(f"Created: {t.get('created_at', '')}")
            with top[2]:
                st.write(f"**{t.get('priority','Medium')}**")
                st.caption("Priority")
            with top[3]:
                st.write(f"**{t.get('category','General')}**")
                st.caption("Category")

            if t.get("subtasks"):
                st.write("Subtasks:")
                for j, sub in enumerate(t["subtasks"]):
                    st.checkbox(sub, key=f"sub_{i}_{j}")

            c1, c2 = st.columns([0.7, 0.3])
            with c2:
                if st.button("❌ Remove", key=f"rm_{i}"):
                    remove_task(i)

st.caption("Tip: Add your OpenAI key in the sidebar to get smart suggestions. If no key is provided, the app still works with sensible defaults.")