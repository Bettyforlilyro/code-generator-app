import pytest
from flask import Blueprint, current_app

from backend.app.common.exceptions.error_codes import (
    BusinessException,
    ErrorCode,
    ParamValidationError,
    AuthenticationError,
    PermissionDeniedError,
    ResourceNotFoundError
)
from backend.app.schemas.responses.BaseResponse import success_response

# 创建测试用的蓝图
test_bp = Blueprint('test', __name__, url_prefix='/test')


@test_bp.route('/success', methods=['GET'])
def success():
    """成功响应测试"""
    with current_app.app_context():
        return success_response(
            data={"id": 1, "name": "测试"}
        )


@test_bp.route('/success/no-data', methods=['GET'])
def success_no_data():
    """成功响应无数据测试"""
    with current_app.app_context():
        return success_response()


@test_bp.route('/business-error', methods=['GET'])
def business_error():
    """业务异常测试"""
    raise BusinessException(
        ErrorCode.BAD_REQUEST,
        message="这是一个业务错误",
        data={"field": "test"}
    )


@test_bp.route('/param-error', methods=['POST'])
def param_error():
    """参数验证异常测试"""
    raise ParamValidationError(
        message="参数验证失败",
        data={"errors": ["字段A不能为空"]}
    )


@test_bp.route('/auth-error', methods=['GET'])
def auth_error():
    """认证异常测试"""
    raise AuthenticationError(message="请先登录")


@test_bp.route('/permission-error', methods=['GET'])
def permission_error():
    """权限拒绝测试"""
    raise PermissionDeniedError(message="权限不足")


@test_bp.route('/not-found-error', methods=['GET'])
def not_found_error():
    """资源未找到测试"""
    raise ResourceNotFoundError(
        message="资源不存在",
        data={"resource_id": 999}
    )


@test_bp.route('/custom-error', methods=['GET'])
def custom_error():
    """自定义错误码测试"""
    raise BusinessException(
        error_code=ErrorCode.TOO_MANY_REQUESTS,
        message="请求过于频繁"
    )


@test_bp.route('/system-error', methods=['GET'])
def system_error():
    """系统异常测试"""
    raise ValueError("这是一个未捕获的系统异常")


def register_test_routes(app):
    """注册测试路由"""
    app.register_blueprint(test_bp)


class TestSuccessResponses:
    """测试成功响应"""

    @pytest.fixture(autouse=True)
    def setup_routes(self, app):
        """自动注册测试路由"""
        register_test_routes(app)

    def test_success_response_with_data(self, client):
        """测试带数据的成功响应"""
        response = client.get('/test/success')
        assert response.status_code == 200

        data = response.get_json()
        assert data['code'] == 20000
        assert data['message'] == "操作成功"
        assert data['data'] == {"id": 1, "name": "测试"}

    def test_success_response_without_data(self, client):
        """测试不带数据的成功响应"""
        response = client.get('/test/success/no-data')
        assert response.status_code == 200

        data = response.get_json()
        assert data['code'] == 20000
        assert data['message'] == "操作成功"
        assert data['data'] is None

    def test_success_response_content_type(self, client):
        """测试响应的Content-Type"""
        response = client.get('/test/success')
        assert response.content_type == 'application/json'


class TestBusinessExceptionResponses:
    """测试业务异常响应"""

    @pytest.fixture(autouse=True)
    def setup_routes(self, app):
        """自动注册测试路由"""
        register_test_routes(app)

    def test_business_exception_response(self, client):
        """测试业务异常响应格式"""
        response = client.get('/test/business-error')

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40000
        assert data['message'] == "这是一个业务错误"
        assert data['data'] == {"field": "test"}

    def test_param_validation_error_response(self, client):
        """测试参数验证异常响应"""
        response = client.post('/test/param-error')

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40000
        assert data['message'] == "参数验证失败"
        assert data['data'] == {"errors": ["字段A不能为空"]}

    def test_authentication_error_response(self, client):
        """测试认证异常响应"""
        response = client.get('/test/auth-error')

        assert response.status_code == 401
        data = response.get_json()
        assert data['code'] == 40100
        assert data['message'] == "请先登录"
        assert data['data'] is None

    def test_permission_denied_response(self, client):
        """测试权限拒绝响应"""
        response = client.get('/test/permission-error')

        assert response.status_code == 403
        data = response.get_json()
        assert data['code'] == 40300
        assert data['message'] == "权限不足"
        assert data['data'] is None

    def test_resource_not_found_response(self, client):
        """测试资源未找到响应"""
        response = client.get('/test/not-found-error')

        assert response.status_code == 404
        data = response.get_json()
        assert data['code'] == 40400
        assert data['message'] == "资源不存在"
        assert data['data'] == {"resource_id": 999}

    def test_custom_error_code_response(self, client):
        """测试自定义错误码响应"""
        response = client.get('/test/custom-error')

        assert response.status_code == 429
        data = response.get_json()
        assert data['code'] == 42900
        assert data['message'] == "请求过于频繁"
        assert data['data'] is None


class TestSystemExceptionResponses:
    """测试系统异常响应"""

    @pytest.fixture(autouse=True)
    def setup_routes(self, app):
        """自动注册测试路由"""
        register_test_routes(app)

    def test_unhandled_exception_response(self, client):
        """测试未捕获异常响应"""
        response = client.get('/test/system-error')

        assert response.status_code == 500
        data = response.get_json()
        assert data['code'] == 50000
        assert data['message'] == "Unknown Internal Error!"
        assert data['data'] is None


class TestHTTPErrorResponses:
    """测试HTTP错误响应"""

    @pytest.fixture(autouse=True)
    def setup_routes(self, app):
        """自动注册测试路由"""
        register_test_routes(app)

    def test_404_not_found_response(self, client):
        """测试404响应"""
        response = client.get('/non-existent-route')

        assert response.status_code == 404
        data = response.get_json()
        assert data['code'] == 40400
        assert data['message'] == "资源不存在"
        assert data['data'] is None

    def test_405_method_not_allowed_response(self, client):
        """测试405响应"""
        # /test/success 只支持GET，用POST访问应该返回405
        response = client.post('/test/success')

        assert response.status_code == 405
        data = response.get_json()
        assert data['code'] == 40500
        assert data['message'] == "请求方法不允许"
        assert data['data'] is None
