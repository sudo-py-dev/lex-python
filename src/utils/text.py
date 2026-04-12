import re


def smart_split(text: str, limit: int = 4096) -> list[str]:
    """
    Split text into chunks while preserving Telegram HTML tags.
    Closes open tags at segment ends and re-opens them in next segments.
    """
    if len(text) <= limit:
        return [text]

    tag_re = re.compile(r"<(/?)([a-zA-Z0-9-]+)([^>]*)>")
    chunks = []
    remaining = text
    active_stack = []

    while remaining:
        prefix = "".join(active_stack)
        current_closing = "".join(
            [f"</{tag_re.match(t).group(2)}>" for t in reversed(active_stack)]
        )

        max_chunk_payload = limit - len(prefix) - len(current_closing)

        if max_chunk_payload <= 0:
            max_chunk_payload = limit // 2

        if len(remaining) <= max_chunk_payload:
            chunks.append(prefix + remaining)
            break

        split_point = remaining.rfind("\n", 0, max_chunk_payload)
        if split_point == -1:
            split_point = remaining.rfind(" ", 0, max_chunk_payload)
        if split_point <= 0:
            split_point = max_chunk_payload

        segment = remaining[:split_point]
        remaining = remaining[split_point:]

        segment_stack = []
        for match in tag_re.finditer(segment):
            is_closing, name, _ = match.groups()
            if is_closing:
                if segment_stack and tag_re.match(segment_stack[-1]).group(2) == name:
                    segment_stack.pop()
                elif active_stack and tag_re.match(active_stack[-1]).group(2) == name:
                    active_stack.pop()
            else:
                segment_stack.append(match.group(0))

        closing_str = "".join([f"</{tag_re.match(t).group(2)}>" for t in reversed(active_stack)])

        chunks.append(prefix + segment + closing_str)

        active_stack.extend(segment_stack)

    return chunks
