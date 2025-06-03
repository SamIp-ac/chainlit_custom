import translators as ts


def chinese_to_english(city_name):
    try:
        # Detect source language and translate to English
        translated = ts.translate_text(city_name, to_language='en')

        # Convert to lowercase and replace spaces with hyphens
        normalized = translated.lower().replace(' ', '-')

        return normalized
    except Exception as e:
        print(f"Translation error: {e}")
        return city_name  # Return original name if translation fails

def 