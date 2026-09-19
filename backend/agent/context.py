import contextvars

# Each FastAPI request that touches the agent runs its whole synchronous call
# chain (route handler -> agent loop -> skill implementation) in a single
# worker thread, so a plain ContextVar set at the top of that chain is safely
# visible to the skill implementations further down it - no need to thread
# group_id through every function signature just so the LLM's tool schemas
# stay free of it.
_group_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("group_id")
_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id")


def set_group_id(group_id: str) -> None:
    _group_id_var.set(group_id)


def get_group_id() -> str:
    return _group_id_var.get()


def set_session_id(session_id: str) -> None:
    _session_id_var.set(session_id)


def get_session_id() -> str:
    return _session_id_var.get()
