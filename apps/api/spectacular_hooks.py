def custom_preprocessing_hook(endpoints):
    """
    Swagger uchun endpointlarni guruhlarga ajratish.
    Token autentifikatsiya endpointiga 'Autentifikatsiya' tegi qo'shiladi.
    API root endpointini yashirish.
    """
    processed = []
    for (path, path_regex, method, callback) in endpoints:
        # DRF DefaultRouter root endpoint ni yashirish
        if path == '/api/' and method == 'GET':
            continue
        processed.append((path, path_regex, method, callback))
    return processed
