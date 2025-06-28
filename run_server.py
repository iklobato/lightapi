from lightapi import LightApi

api = LightApi.from_config("test_server.yaml")

if __name__ == "__main__":
    api.run(host="0.0.0.0", port=8081)
