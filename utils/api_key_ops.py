def mask_api_key(key: str) -> str:
    """
    隐藏 API Key 中间部分

    :param key: 完整的 API Key
    :return:
    """
    return key[:8] + '********' + key[-4:]
