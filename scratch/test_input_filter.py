import asyncio
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.input import capture_next_input, is_waiting_for_input


async def test():
    user_id = 12345
    chat_id = 67890

    # Arm capture
    print("Arming capture for 'filterKeyword'...")
    await capture_next_input(user_id, chat_id, "filterKeyword")

    # Create filter
    flt = is_waiting_for_input("filterKeyword")

    # Mock message
    message = MagicMock()
    message.from_user.id = user_id
    message.chat.type = "private"

    # Check filter
    res = await flt(None, message)
    print(f"Filter result for 'filterKeyword': {res}")
    if res:
        print(f"Input state attached: {message.input_state}")

    # Check for mismatch
    flt_wrong = is_waiting_for_input("otherField")
    res_wrong = await flt_wrong(None, message)
    print(f"Filter result for 'otherField': {res_wrong}")


if __name__ == "__main__":
    asyncio.run(test())
