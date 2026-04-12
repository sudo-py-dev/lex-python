from src.plugins.lang_block import detect_language_with_confidence


def test_language_detection():
    test_cases = [
        "Hello how are you?",
        "שלום מה שלומך?",
        "Привет, как дела?",
        "This is English with some русский language mixed in.",
    ]

    for text in test_cases:
        res = detect_language_with_confidence(text)
        assert res is not None
        assert isinstance(res, list)
        if res:
            assert isinstance(res[0], tuple)
            assert len(res[0]) == 2
