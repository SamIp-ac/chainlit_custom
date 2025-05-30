import translators as ts


def chinese_to_english(city_name):
    try:
        # 获取翻译结果
        translated = ts.translate_text(city_name, from_language='zh', to_language='en')

        # 转换为小写并替换空格为连字符
        normalized = translated.lower().replace(' ', '-')

        return normalized
    except Exception as e:
        print(f"翻译出错: {e}")
        return city_name  # 失败时返回原名称