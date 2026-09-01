"""Code generation package for plan-editor.

Public API
----------
generate_plan_code(scene) -> str
    Walk the node graph and return a complete Python function string.

build_queue_items(scene) -> list[dict]
    For simple linear chains only: return queue-server plan item dicts.

Internal modules
----------------
generator.py     DAG traversal, for-loop / for-each / sequence emission
call_builders.py Per-node call-string builders (_build_call and value helpers)
queue_items.py   Queue-server item serialisation
utils.py         Type coercions and string-formatting helpers
"""
from plan_editor.codegen.generator    import generate_plan_code   # noqa: F401
from plan_editor.codegen.queue_items  import build_queue_items    # noqa: F401
