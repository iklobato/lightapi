from lightapi.rest import RestEndpoint, ModelEndpoint


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


def test_model_endpoint_provides_queryset(test_model, db_session):
    class ModelEndpointTest(ModelEndpoint):
        model = test_model
        
    request = {'db': db_session}
    queryset = ModelEndpointTest().get_queryset(request)
    assert str(queryset).endswith('FROM test_models')


class HealthCheckEndpoint(RestEndpoint):
    http_method_names = ['get']  
    
    def get(self, request):
        return {'status': 'healthy'}

