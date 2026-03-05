class HttpMethod:
    """Namespace for HTTP method marker mixins.

    Inherit from an inner class to restrict a RestEndpoint to specific verbs.
    Multiple mixins may be combined; the framework merges them at app.run().
    """

    class GET:
        _http_method = "GET"

    class POST:
        _http_method = "POST"

    class PUT:
        _http_method = "PUT"

    class PATCH:
        _http_method = "PATCH"

    class DELETE:
        _http_method = "DELETE"
