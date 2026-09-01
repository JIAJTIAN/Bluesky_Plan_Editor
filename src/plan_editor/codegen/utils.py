"""Type-coercion and string-formatting helpers for code generation."""
from __future__ import annotations


def _int(v) -> int:
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return 1


def _float(v) -> float:
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return 0.0


def _bool(v) -> str:
    """Coerce a param value to a Python bool literal string."""
    if isinstance(v, bool):
        return str(v)
    s = str(v).strip().lower()
    return "True" if s in ("true", "1", "yes") else "False"


def _try_float(v) -> float | str:
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return str(v)


def _det_list(raw: str) -> str:
    """'det1, det2' → '[det1, det2]'  (bare Python names, not quoted strings)."""
    raw = str(raw).strip()
    if not raw:
        return "[]"
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    return "[" + ", ".join(parts) + "]"


def _parse_det_list(raw: str) -> list[str]:
    """'det1, det2' → ['det1', 'det2']"""
    raw = str(raw).strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _val_list(raw: str) -> str:
    """Convert a values param to a Python iterable expression.

    Passes through anything that already looks like a call or array literal
    (e.g. 'np.linspace(0,1,10)', '[1,2,3]', 'range(10)').
    Otherwise treats the string as comma-separated numbers and wraps in a list.
    """
    raw = raw.strip()
    if any(c in raw for c in ("(", "[", "np.", "range")):
        return raw
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    return "[" + ", ".join(parts) + "]"


def _motor_range_args(p: dict) -> str:
    """Collect motor_N / start_N / stop_N triplets → 'motor1, s1, e1, motor2, s2, e2'."""
    parts, i = [], 0
    while f"motor_{i}" in p:
        m = str(p[f"motor_{i}"]).strip()
        s = p.get(f"start_{i}", 0)
        e = p.get(f"stop_{i}", 1)
        if m:
            parts.append(f"{m}, {s}, {e}")
        i += 1
    return ", ".join(parts) if parts else "motor, 0, 1"


def _extract_pairs(p: dict, key_a: str, key_b: str) -> list[tuple]:
    """Extract numbered pairs (motor_0/pos_0, motor_1/pos_1, …) from params."""
    pairs = []
    i = 0
    while f"{key_a}_{i}" in p:
        a = str(p[f"{key_a}_{i}"]).strip()
        b = p.get(f"{key_b}_{i}", "")
        if a:
            pairs.append((a, b))
        i += 1
    return pairs or [(str(p.get(key_a, "")), p.get(key_b, 0))]


def _md_kwarg(raw: str) -> str:
    """Return ', md={...}' if the raw string is non-empty, else ''."""
    raw = str(raw).strip()
    if not raw:
        return ""
    md: dict = {}
    for part in raw.split(","):
        if "=" in part:
            k, _, v = part.partition("=")
            md[k.strip()] = v.strip()
        elif part.strip():
            md["label"] = part.strip()
    return f", md={md!r}"
