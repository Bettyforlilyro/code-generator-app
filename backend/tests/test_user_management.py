from backend.app.models.user import User


class TestUserRegister:
    """测试用户注册接口"""
    def test_register_success(self, client):
        """测试成功注册"""
        response = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'user_password': 'Password123!',
            'confirm_password': 'Password123!'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == 20000
        assert data['message'] == '操作成功'
        assert data['data'] is not None
        assert 'id' in data['data']
        assert 'user_account' in data['data']
        assert data['data']['user_name'] == '张三'
        assert data['data']['user_role'] == 'user'
        assert 'create_time' in data['data']
        response = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'user_password': 'Password123!',
            'confirm_password': 'Password123!'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40003    # 代表参数异常，具体信息看message
        assert data['message'] == '用户名已存在'


    def test_register_with_missing_fields(self, client):
        """测试缺少必填字段"""
        response = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'confirm_password': 'Password123!'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40003
        assert data['message'] == "用户名和密码不能为空"

    def test_register_with_empty_body(self, client):
        """测试空请求体"""
        response = client.post('/api/v1/user/register', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40000
        assert data['message'] == "请求体不能为空"

    def test_register_with_weak_password(self, client):
        """测试弱密码"""
        response = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'user_password': '123456',
            'confirm_password': '123456'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40003
        assert data['message'] == "密码复杂度过低，请至少包含大写或小写字母、数字、特殊符号中的其中两种"

    def test_register_password_mismatch(self, client):
        """测试两次密码不一致"""
        response = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'user_password': 'Password123!',
            'confirm_password': 'Password456!'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40003
        assert data['message'] == "两次输入的密码不一致"

    def test_register_password_too_short(self, client):
        """测试密码过短"""
        response = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'user_password': 'pa111',
            'confirm_password': 'pa111'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['code'] == 40003
        assert data['message'] == "密码长度不能小于6个字符"

    def test_register_user_name_too_long(self, client):
        """测试用户名过长"""
        response = client.post('/api/v1/user/register', json={
            'user_name': 'a' * 257,
            'user_password': 'Password123!',
            'confirm_password': 'Password123!'
        })

        assert response.status_code == 500
        data = response.get_json()
        assert data['code'] == 50000


    def test_register_generates_unique_account(self, client):
        """测试生成的用户账号唯一性"""
        response1 = client.post('/api/v1/user/register', json={
            'user_name': '张三',
            'user_password': 'Password123!',
            'confirm_password': 'Password123!'
        })

        response2 = client.post('/api/v1/user/register', json={
            'user_name': '李四',
            'user_password': 'Password456!',
            'confirm_password': 'Password456!'
        })

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.get_json()
        data2 = response2.get_json()

        assert data1['data']['user_account'] != data2['data']['user_account']

    def test_register_creates_user_in_database(self, client, app):
        """测试用户确实被创建到数据库中"""
        with app.app_context():
            initial_count = User.query.count()

        response = client.post('/api/v1/user/register', json={
            'user_name': '王五',
            'user_password': 'Password789!',
            'confirm_password': 'Password789!'
        })

        assert response.status_code == 200

        with app.app_context():
            new_count = User.query.count()
            assert new_count == initial_count + 1

            user = User.query.filter_by(user_name='王五').first()
            assert user is not None
            assert user.user_role == 'user'
            assert user.check_password('Password789!')

    def test_register_password_is_encrypted(self, client, app):
        """测试密码是否被加密存储"""
        response = client.post('/api/v1/user/register', json={
            'user_name': '赵六',
            'user_password': 'Password123!',
            'confirm_password': 'Password123!'
        })

        assert response.status_code == 200

        with app.app_context():
            user = User.query.filter_by(user_name='赵六').first()
            assert user is not None
            # 密码应该是加密后的哈希值，不是明文
            assert user.user_password != 'Password123!'
            assert user.user_password.startswith('pbkdf2:') or user.user_password.startswith('scrypt:')

    def test_register_wrong_method(self, client):
        """测试使用错误的HTTP方法"""
        response = client.get('/api/v1/user/register')

        assert response.status_code == 405
        data = response.get_json()
        assert data['code'] == 40500

    def test_register_multiple_users(self, client):
        """测试批量注册用户"""
        users_data = [
            {'user_name': f'用户{i}', 'user_password': f'Password{i}!', 'confirm_password': f'Password{i}!'}
            for i in range(5)
        ]

        responses = []
        for user_data in users_data:
            response = client.post('/api/v1/user/register', json=user_data)
            responses.append(response)

        for response in responses:
            assert response.status_code == 200

        accounts = [response.get_json()['data']['user_account'] for response in responses]
        # 确保所有账号都是唯一的
        assert len(accounts) == len(set(accounts))
