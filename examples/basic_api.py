from lightapi import LightApi, RestEndpoint


class HelloEndpoint(RestEndpoint):
    def get(self, request):
        return {'message': 'Hello, World!'}


app = LightApi()
app.register({'/hello': HelloEndpoint})
app.run()
