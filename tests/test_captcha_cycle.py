"""Tests for captcha cycle button implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import ChatSettings
from src.plugins.admin_panel.handlers.callbacks.security import on_cycle_captcha_mode
from src.utils.actions import CAPTCHA_MODES, CaptchaMode, cycle_action


class TestCaptchaCycleAction:
    """Test the cycle_action utility with captcha modes."""

    def test_cycle_action_captcha_button_to_math(self):
        """Test cycling from BUTTON to MATH."""
        result = cycle_action(CaptchaMode.BUTTON, CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.MATH.value

    def test_cycle_action_captcha_math_to_poll(self):
        """Test cycling from MATH to POLL."""
        result = cycle_action(CaptchaMode.MATH, CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.POLL.value

    def test_cycle_action_captcha_poll_to_image(self):
        """Test cycling from POLL to IMAGE."""
        result = cycle_action(CaptchaMode.POLL, CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.IMAGE.value

    def test_cycle_action_captcha_image_to_button(self):
        """Test cycling from IMAGE wraps back to BUTTON."""
        result = cycle_action(CaptchaMode.IMAGE, CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.BUTTON.value

    def test_cycle_action_captcha_full_cycle(self):
        """Test complete cycle through all modes."""
        modes = [CaptchaMode.BUTTON, CaptchaMode.MATH, CaptchaMode.POLL, CaptchaMode.IMAGE]
        current = CaptchaMode.BUTTON

        for _ in range(len(modes) + 1):
            current_str = cycle_action(current, CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
            current = CaptchaMode(current_str)

        # After full cycle + 1, should be MATH (started at BUTTON -> MATH)
        assert current == CaptchaMode.MATH

    def test_cycle_action_captcha_with_string_values(self):
        """Test cycling with string values instead of enums."""
        result = cycle_action("button", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == "math"

        result = cycle_action("math", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == "poll"

    def test_cycle_action_captcha_case_insensitive(self):
        """Test case insensitivity with captcha modes."""
        result = cycle_action("BUTTON", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == "math"

        result = cycle_action("Math", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == "poll"

    def test_cycle_action_captcha_none_defaults_to_button(self):
        """Test that None current action defaults to button."""
        result = cycle_action(None, CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.BUTTON.value

    def test_cycle_action_captcha_empty_string_defaults_to_button(self):
        """Test that empty string current action defaults to button."""
        result = cycle_action("", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.BUTTON.value

    def test_cycle_action_captcha_invalid_mode_with_default(self):
        """Test that invalid mode returns default when provided."""
        result = cycle_action("invalid", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == CaptchaMode.BUTTON.value

    def test_cycle_action_captcha_invalid_mode_without_default(self):
        """Test that invalid mode returns first item when no default."""
        result = cycle_action("invalid", CAPTCHA_MODES)
        assert result == CAPTCHA_MODES[0].value


class TestCaptchaCycleHandler:
    """Test the on_cycle_captcha_mode handler logic directly."""

    @pytest.fixture
    def mock_callback(self):
        """Create a mock callback query."""
        callback = MagicMock()
        callback.from_user.id = 123456
        callback.matches = [MagicMock()]
        callback.matches[0].group.return_value = "captchaMode"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.type = MagicMock()
        callback.message.chat.type.name = "supergroup"
        callback.message.edit_text = AsyncMock()
        callback.message.edit_reply_markup = AsyncMock()
        callback.answer = AsyncMock()
        return callback

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_captcha_cycle_existing_chat_button_to_math(
        self, mock_client, mock_callback, db_session
    ):
        """Test cycling captcha mode for existing chat with BUTTON mode."""
        # Setup existing chat with BUTTON mode
        chat = ChatSettings(
            id=-1001234567890,
            captchaMode="button",
            captchaEnabled=True,
            captchaTimeout=120,
        )
        db_session.add(chat)
        await db_session.commit()

        # Create proper AppContext mock
        from src.core.context import AppContext

        mock_ctx = MagicMock(spec=AppContext)
        mock_ctx.db = MagicMock(return_value=db_session)

        # Create AdminPanelContext
        from src.plugins.admin_panel.decorators import AdminPanelContext

        ap_ctx = AdminPanelContext(
            chat_id=-1001234567890,
            at_id=123456,
            ctx=mock_ctx,
            is_pm=False,
            chat_type=None,
            chat_title=None,
        )

        # Mock dependencies
        with (
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.check_user_permission",
                return_value=True,
            ),
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.captcha_kb",
                return_value=MagicMock(),
            ),
            patch("src.utils.i18n.at", return_value="test"),
        ):
            await on_cycle_captcha_mode(mock_client, mock_callback, ap_ctx)

        # Verify mode was updated to math
        result = await db_session.get(ChatSettings, -1001234567890)
        assert result.captchaMode == "math"

    @pytest.mark.asyncio
    async def test_captcha_cycle_new_chat_defaults_to_button(
        self, mock_client, mock_callback, db_session
    ):
        """Test cycling captcha mode for new chat (no prior settings)."""
        # No chat in database - should be created
        from src.core.context import AppContext

        mock_ctx = MagicMock(spec=AppContext)
        mock_ctx.db = MagicMock(return_value=db_session)

        from src.plugins.admin_panel.decorators import AdminPanelContext

        ap_ctx = AdminPanelContext(
            chat_id=-1001234567890,
            at_id=123456,
            ctx=mock_ctx,
            is_pm=False,
            chat_type=None,
            chat_title=None,
        )

        with (
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.check_user_permission",
                return_value=True,
            ),
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.captcha_kb",
                return_value=MagicMock(),
            ),
            patch("src.utils.i18n.at", return_value="test"),
        ):
            await on_cycle_captcha_mode(mock_client, mock_callback, ap_ctx)

        # Verify chat was created and mode set to math (default button -> next is math)
        result = await db_session.get(ChatSettings, -1001234567890)
        assert result is not None
        assert result.captchaMode == "math"

    @pytest.mark.asyncio
    async def test_captcha_cycle_wraps_from_image_to_button(
        self, mock_client, mock_callback, db_session
    ):
        """Test that IMAGE mode cycles back to BUTTON."""
        # Setup chat with IMAGE mode
        chat = ChatSettings(
            id=-1001234567890,
            captchaMode="image",
            captchaEnabled=True,
            captchaTimeout=120,
        )
        db_session.add(chat)
        await db_session.commit()

        from src.core.context import AppContext

        mock_ctx = MagicMock(spec=AppContext)
        mock_ctx.db = MagicMock(return_value=db_session)

        from src.plugins.admin_panel.decorators import AdminPanelContext

        ap_ctx = AdminPanelContext(
            chat_id=-1001234567890,
            at_id=123456,
            ctx=mock_ctx,
            is_pm=False,
            chat_type=None,
            chat_title=None,
        )

        with (
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.check_user_permission",
                return_value=True,
            ),
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.captcha_kb",
                return_value=MagicMock(),
            ),
            patch("src.utils.i18n.at", return_value="test"),
        ):
            await on_cycle_captcha_mode(mock_client, mock_callback, ap_ctx)

        # Verify mode wrapped to button
        result = await db_session.get(ChatSettings, -1001234567890)
        assert result.captchaMode == "button"

    @pytest.mark.asyncio
    async def test_captcha_cycle_handles_none_mode(self, mock_client, mock_callback, db_session):
        """Test handling when captchaMode is None in database."""
        # Setup chat with None captchaMode
        chat = ChatSettings(
            id=-1001234567890,
            captchaMode=None,
            captchaEnabled=True,
            captchaTimeout=120,
        )
        db_session.add(chat)
        await db_session.commit()

        from src.core.context import AppContext

        mock_ctx = MagicMock(spec=AppContext)
        mock_ctx.db = MagicMock(return_value=db_session)

        from src.plugins.admin_panel.decorators import AdminPanelContext

        ap_ctx = AdminPanelContext(
            chat_id=-1001234567890,
            at_id=123456,
            ctx=mock_ctx,
            is_pm=False,
            chat_type=None,
            chat_title=None,
        )

        with (
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.check_user_permission",
                return_value=True,
            ),
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.captcha_kb",
                return_value=MagicMock(),
            ),
            patch("src.utils.i18n.at", return_value="test"),
        ):
            await on_cycle_captcha_mode(mock_client, mock_callback, ap_ctx)

        # Verify mode set to math (default button -> next is math)
        result = await db_session.get(ChatSettings, -1001234567890)
        assert result.captchaMode == "math"

    @pytest.mark.asyncio
    async def test_captcha_cycle_no_permission_denied(self, mock_client, mock_callback, db_session):
        """Test that users without permission are denied."""
        # Setup existing chat
        chat = ChatSettings(
            id=-1001234567890,
            captchaMode="button",
            captchaEnabled=True,
        )
        db_session.add(chat)
        await db_session.commit()

        from src.core.context import AppContext

        mock_ctx = MagicMock(spec=AppContext)
        mock_ctx.db = MagicMock(return_value=db_session)

        from src.plugins.admin_panel.decorators import AdminPanelContext

        ap_ctx = AdminPanelContext(
            chat_id=-1001234567890,
            at_id=123456,
            ctx=mock_ctx,
            is_pm=False,
            chat_type=None,
            chat_title=None,
        )

        # Mock permission check to return False
        with (
            patch(
                "src.plugins.admin_panel.handlers.callbacks.security.check_user_permission",
                return_value=False,
            ),
            patch("src.utils.i18n.at", return_value="No permission"),
        ):
            await on_cycle_captcha_mode(mock_client, mock_callback, ap_ctx)

        # Verify mode was NOT changed
        result = await db_session.get(ChatSettings, -1001234567890)
        assert result.captchaMode == "button"

        # Verify callback answer was called with error
        mock_callback.answer.assert_called_once()
        call_args = mock_callback.answer.call_args
        assert "show_alert" in call_args.kwargs
        assert call_args.kwargs["show_alert"] is True


class TestCaptchaModesList:
    """Test the CAPTCHA_MODES list configuration."""

    def test_captcha_modes_contains_all_modes(self):
        """Verify CAPTCHA_MODES includes all expected modes in correct order."""
        assert len(CAPTCHA_MODES) == 4
        assert CAPTCHA_MODES[0] == CaptchaMode.BUTTON
        assert CAPTCHA_MODES[1] == CaptchaMode.MATH
        assert CAPTCHA_MODES[2] == CaptchaMode.POLL
        assert CAPTCHA_MODES[3] == CaptchaMode.IMAGE

    def test_captcha_modes_are_unique(self):
        """Verify all captcha modes are unique."""
        values = [mode.value for mode in CAPTCHA_MODES]
        assert len(values) == len(set(values))

    def test_captcha_mode_enum_values(self):
        """Verify CaptchaMode enum has correct string values."""
        assert CaptchaMode.BUTTON.value == "button"
        assert CaptchaMode.MATH.value == "math"
        assert CaptchaMode.POLL.value == "poll"
        assert CaptchaMode.IMAGE.value == "image"


class TestCaptchaCycleEdgeCases:
    """Test edge cases for captcha cycling."""

    def test_cycle_action_preserves_captcha_mode_case(self):
        """Test that cycling preserves the case of next mode in list."""
        # CAPTCHA_MODES uses enums, so values are always lowercase
        result = cycle_action("BUTTON", CAPTCHA_MODES, default_action=CaptchaMode.BUTTON)
        assert result == "math"

    def test_cycle_action_captcha_with_enum_input(self):
        """Test cycling when input is enum vs string."""
        # Both should produce same result
        result_enum = cycle_action(CaptchaMode.BUTTON, CAPTCHA_MODES)
        result_str = cycle_action("button", CAPTCHA_MODES)
        assert result_enum == result_str == "math"

    def test_cycle_action_captcha_empty_list_raises(self):
        """Test that empty allowed_actions raises ValueError."""
        with pytest.raises(ValueError, match="allowed_actions cannot be empty"):
            cycle_action(CaptchaMode.BUTTON, [])

    def test_cycle_action_captcha_single_mode(self):
        """Test cycling with single mode always returns that mode."""
        single_mode = [CaptchaMode.BUTTON]
        result = cycle_action(CaptchaMode.BUTTON, single_mode)
        assert result == "button"

        result = cycle_action(CaptchaMode.MATH, single_mode, default_action=CaptchaMode.BUTTON)
        assert result == "button"
