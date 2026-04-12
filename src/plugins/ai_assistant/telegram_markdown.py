import re


def render_pyrogram_html(text: str) -> str:
    """
    Convert common LLM markdown-like output into safe HTML for ParseMode.HTML.
    """
    if not text:
        return ""

    src = text.strip()

    # Triple backtick blocks.
    src = re.sub(
        r"```([a-zA-Z0-9_+-]+)?\n?([\s\S]*?)```",
        lambda m: (
            f'<pre><code class="language-{m.group(1) or "text"}">{m.group(2).strip()}</code></pre>'
        ),
        src,
    )
    # Inline code.
    src = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", src)

    # Bold / italic / strike / spoiler.
    src = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", src, flags=re.DOTALL)
    src = re.sub(r"__(.+?)__", r"<i>\1</i>", src, flags=re.DOTALL)
    src = re.sub(r"~~(.+?)~~", r"<s>\1</s>", src, flags=re.DOTALL)
    src = re.sub(r"\|\|(.+?)\|\|", r"<tg-spoiler>\1</tg-spoiler>", src, flags=re.DOTALL)

    # Links.
    src = re.sub(r"\[([^\]\n]+?)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', src)

    return src
