from lightapi.rest import RestEndpoint, ModelEndpoint

class HealthCheckEndpoint(RestEndpoint):
    def get(self, request):
        return {'status': 'healthy'}

def test_rest_endpoint_handles_valid_method():
    endpoint = HealthCheckEndpoint()
    response, status = endpoint.handle_request('GET', {})
    assert status == 200
    assert response == {'status': 'healthy'}

def test_rest_endpoint_rejects_invalid_method():
    endpoint = HealthCheckEndpoint()
    response, status = endpoint.handle_request('DELETE', {})
    assert status == 405
    assert 'Method not allowed' in response['error']

def test_model_endpoint_provides_queryset(test_model):
    class ModelEndpointTest(ModelEndpoint):
        model = test_model
        
    queryset = ModelEndpointTest().get_queryset({})
    assert str(queryset).endswith('FROM test_models')
