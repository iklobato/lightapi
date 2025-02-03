from lightapi import LightApi

def test_app_registers_endpoints():
    app = LightApi()
    app.register({'/health': None, '/metrics': None})
    assert set(app.endpoints.keys()) == {'/health', '/metrics'}

def test_app_initializes_middleware():
    app = LightApi()
    app.add_middleware([lambda x: x])
    assert len(app.middleware) == 1
