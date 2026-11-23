"""Audit trail for sensitive actions (price changes, stock adjustments, cancellations)."""


def log(cur, user_id, action, entity, entity_id, details=""):
    """Write an audit row using the caller's cursor so it is part of the same transaction."""
    cur.execute(
        "INSERT INTO audit_log (user_id, action, entity, entity_id, details) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, action, entity, entity_id, details[:500]),
    )
