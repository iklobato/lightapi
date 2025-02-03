from lightapi.middleware import CORSMiddleware, RateLimitingMiddleware

def test_cors_middleware_sets_headers():
    middleware = CORSMiddleware()
    response = middleware.process({}, {'headers': {}})
    assert response.headers == {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }

def test_rate_limiter_allows_valid_requests():
    middleware = RateLimitingMiddleware(limit=2, window=60)
    request = {'headers': {'X-Forwarded-For': '192.168.1.1'}}
    
    # First request
    response = middleware.process(request, {})
    assert 'error' not in response.data
    
    # Second request
    response = middleware.process(request, {})
    assert 'error' not in response.data

def test_rate_limiter_blocks_excessive_requests():
    middleware = RateLimitingMiddleware(limit=1, window=60)
    request = {'headers': {'X-Forwarded-For': '10.0.0.1'}}
    
    middleware.process(request, {})  # Allowed
    response = middleware.process(request, {})  # Blocked
    
    assert response.status_code == 429
    assert 'Too many requests' in response.data['error']
