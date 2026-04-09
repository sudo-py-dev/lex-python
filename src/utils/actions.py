def cycle_action(
    current_action: str | None, allowed_actions: list[str], default_action: str | None = None
) -> str:
    """
    Returns the next action in a cyclic list of allowed_actions.
    If current_action is not in the list, or is None, returns the first element of allowed_actions (or default_action).
    """
    if not allowed_actions:
        raise ValueError("allowed_actions cannot be empty")

    fallback = default_action if default_action is not None else allowed_actions[0]

    if not current_action:
        return fallback

    current = current_action.lower()
    normalized_list = [x.lower() for x in allowed_actions]

    if current in normalized_list:
        idx = normalized_list.index(current)
        return allowed_actions[(idx + 1) % len(allowed_actions)]

    return fallback
