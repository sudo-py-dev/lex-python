# Placeholder for sticker utility functions
def get_sticker_info(message):
    if not message.sticker:
        return None
    return {
        "file_id": message.sticker.file_id,
        "file_unique_id": message.sticker.file_unique_id,
        "set_name": message.sticker.set_name,
        "emoji": message.sticker.emoji,
    }
