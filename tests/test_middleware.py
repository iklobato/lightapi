from lightapi.middleware import CORSMiddleware, RateLimitingMiddleware

def test_cors_middleware_sets_headers():
    middleware = CORSMiddleware()
    response = middleware.process({}, {'headers': {}})
    assert response['headers'] == {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    }

def test_rate_limiter_allows_valid_requests():
    middleware = RateLimitingMiddleware(limit=2, window=60)
    request = {'headers': {'X-Forwarded-For': '192.168.1.1'}}
    
    response = middleware.process(request, {})
    assert 'data' not in response or 'error' not in response.get('data', {})
    
    response = middleware.process(request, {})
    assert 'data' not in response or 'error' not in response.get('data', {})

def test_rate_limiter_blocks_excessive_requests():
    middleware = RateLimitingMiddleware(limit=1, window=60)
    request = {'headers': {'X-Forwarded-For': '10.0.0.1'}}
    
    middleware.process(request, {})  
    response = middleware.process(request, {})  
    
    assert response['status_code'] == 429
    assert 'error' in response['data']
    assert 'Rate limit exceeded' in response['data']['error']
