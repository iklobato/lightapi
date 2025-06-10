import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def simple_endpoint(request):
    return JSONResponse(
        {"data": "ok", "message": "GET request successful"}, status_code=200
    )


app = Starlette(routes=[Route("/test", simple_endpoint, methods=["GET"])])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
