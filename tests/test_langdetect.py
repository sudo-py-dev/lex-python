from src.plugins.lang_block.service import detect_language_with_confidence

test_cases = [
    "Hello how are you?",
    "שלום מה שלומך?",
    "Привет, как дела?",
    "This is English with some русский language mixed in.",
]

for text in test_cases:
    res = detect_language_with_confidence(text)
    print(f"Text: {text}")
    print(f"Detected: {res}")
    print("-" * 20)
