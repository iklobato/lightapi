from lightapi.exceptions import ValidationError


class RestEndpoint:
    http_method_names = ['get', 'post', 'put', 'delete', 'patch']  # Lowercase methods
    authentication_class = None
    validator_class = None

    def handle_request(self, method, request):
        method = method.lower()
        if method not in self.http_method_names:
            return {'error': 'Method not allowed'}, 405

        # Authentication
        if self.authentication_class:
            auth_header = request.get('headers', {}).get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return {'error': 'Unauthorized'}, 401
            token = auth_header.split(' ')[1]
            user = self.authentication_class.decode_token(token)
            if not user:
                return {'error': 'Invalid token'}, 401
            request['user'] = user

        # Validation
        if self.validator_class and request.get('body'):
            validator = self.validator_class()
            try:
                request['data'] = validator.validate(request['body'])
            except ValidationError as e:
                return {'error': str(e)}, 400

        # Call handler method
        handler = getattr(self, method, None)
        if not handler:
            return {'error': 'Method not implemented'}, 501

        result = handler(request)
        if not isinstance(result, tuple):
            return result, 200  # Add default status code
        return result


class ModelEndpoint:
    model = None

    def get_queryset(self, request):
        return request['db'].query(self.model)

    def get_object(self, request, obj_id):
        return self.get_queryset(request).filter_by(id=obj_id).first()


class Response:
    def __init__(
        self, data, status_code=200, content_type='application/json', headers=None
    ):
        self.data = data
        self.status_code = status_code
        self.content_type = content_type
        self.headers = headers or {}


class Validator:
    def validate(self, data):
        validated = {}
        for key, value in data.items():
            validator_method = getattr(self, f'validate_{key}', None)
            if validator_method:
                validated[key] = validator_method(value)
            else:
                validated[key] = value
        return validated
