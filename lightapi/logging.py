import logging

from lightapi.middleware import Middleware


class RequestLogger:
    def __init__(self):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO,
        )
        self.logger = logging.getLogger('lightapi')

    def log_request(self, request):
        self.logger.info(f"{request['method']} {request['path']}")


class LoggingMiddleware(Middleware):
    def process(self, request, response):
        logger = RequestLogger()
        logger.log_request(request)
        return response
