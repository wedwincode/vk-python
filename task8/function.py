from urllib.parse import urlparse


def get_valid_http_urls_from_file(file_path: str) -> list[str]:
    """
    Возвращает список валидных http/https URL из текстового файла.
    """
    valid_urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                parsed = urlparse(raw)
                if parsed.scheme in ('http', 'https') and parsed.netloc:
                    valid_urls.append(raw)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise IOError(f"Failed to read file: {e}")
    return valid_urls
