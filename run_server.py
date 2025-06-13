from lightapi import LightApi
import aiohttp.web

api = LightApi.from_config('test_server.yaml')
app = api.app

if __name__ == "__main__":
    aiohttp.web.run_app(app, port=8081) 