import json

from pyrogram import Client
from pyrogram.types import Message


async def extract_message_data(message: Message) -> dict:
    """
    Extracts relevant data from a Telegram message for storage.
    Supports text, media, polls, locations, etc.
    """
    data = {
        "type": "text",
        "text": message.text or message.caption,
        "file_id": None,
        "additional_data": None,
    }

    if message.media:
        if message.photo:
            data.update({"type": "photo", "file_id": message.photo.file_id})
        elif message.video:
            data.update({"type": "video", "file_id": message.video.file_id})
        elif message.animation:
            data.update({"type": "animation", "file_id": message.animation.file_id})
        elif message.audio:
            data.update({"type": "audio", "file_id": message.audio.file_id})
        elif message.document:
            data.update({"type": "document", "file_id": message.document.file_id})
        elif message.sticker:
            data.update({"type": "sticker", "file_id": message.sticker.file_id})
        elif message.voice:
            data.update({"type": "voice", "file_id": message.voice.file_id})
        elif message.video_note:
            data.update({"type": "video_note", "file_id": message.video_note.file_id})

    elif message.poll:
        data.update({
            "type": "poll",
            "additional_data": json.dumps({
                "question": message.poll.question,
                "options": [opt.text for opt in message.poll.options],
                "is_anonymous": message.poll.is_anonymous,
                "type": message.poll.type,
                "allows_multiple_answers": message.poll.allows_multiple_answers,
            })
        })
    elif message.location:
        data.update({
            "type": "location",
            "additional_data": json.dumps({
                "latitude": message.location.latitude,
                "longitude": message.location.longitude,
            })
        })
    elif message.venue:
        data.update({
            "type": "venue",
            "additional_data": json.dumps({
                "latitude": message.venue.location.latitude,
                "longitude": message.venue.location.longitude,
                "title": message.venue.title,
                "address": message.venue.address,
                "foursquare_id": message.venue.foursquare_id,
            })
        })
    elif message.contact:
        data.update({
            "type": "contact",
            "additional_data": json.dumps({
                "phone_number": message.contact.phone_number,
                "first_name": message.contact.first_name,
                "last_name": message.contact.last_name,
                "vcard": message.contact.vcard,
            })
        })

    return data

async def send_stored_message(client: Client, chat_id: int, message_type: str, text: str | None, file_id: str | None, additional_data: str | None, **kwargs) -> Message:
    """
    Sends a message based on stored data.
    """
    if message_type == "text":
        return await client.send_message(chat_id, text, **kwargs)
    
    if message_type == "photo":
        return await client.send_photo(chat_id, file_id, caption=text, **kwargs)
    
    if message_type == "video":
        return await client.send_video(chat_id, file_id, caption=text, **kwargs)
    
    if message_type == "animation":
        return await client.send_animation(chat_id, file_id, caption=text, **kwargs)
    
    if message_type == "audio":
        return await client.send_audio(chat_id, file_id, caption=text, **kwargs)
    
    if message_type == "document":
        return await client.send_document(chat_id, file_id, caption=text, **kwargs)
    
    if message_type == "sticker":
        return await client.send_sticker(chat_id, file_id, **kwargs)
    
    if message_type == "voice":
        return await client.send_voice(chat_id, file_id, caption=text, **kwargs)
    
    if message_type == "video_note":
        return await client.send_video_note(chat_id, file_id, **kwargs)

    if additional_data:
        extra = json.loads(additional_data)
        if message_type == "poll":
            return await client.send_poll(
                chat_id,
                question=extra["question"],
                options=extra["options"],
                is_anonymous=extra.get("is_anonymous", True),
                type=extra.get("type", "regular"),
                allows_multiple_answers=extra.get("allows_multiple_answers", False),
                **kwargs
            )
        if message_type == "location":
            return await client.send_location(chat_id, extra["latitude"], extra["longitude"], **kwargs)
        if message_type == "venue":
            return await client.send_venue(
                chat_id,
                extra["latitude"],
                extra["longitude"],
                extra["title"],
                extra["address"],
                foursquare_id=extra.get("foursquare_id"),
                **kwargs
            )
        if message_type == "contact":
            return await client.send_contact(
                chat_id,
                extra["phone_number"],
                extra["first_name"],
                last_name=extra.get("last_name"),
                vcard=extra.get("vcard"),
                **kwargs
            )

    return await client.send_message(chat_id, text, **kwargs)
