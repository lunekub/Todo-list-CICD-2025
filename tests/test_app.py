import pytest
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError
from app import create_app
from app.models import db, Todo


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


# -------------------- 1.1 TestAppFactory --------------------
class TestAppFactory:
    """Test application factory and configuration"""

    def test_app_creation(self, app):
        assert app is not None
        assert app.config['TESTING'] is True

    def test_root_endpoint(self, client):
        response = client.get('/')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data
        assert 'version' in data
        assert 'endpoints' in data

    def test_404_error_handler(self, client):
        response = client.get('/nonexistent-endpoint')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_exception_handler(self, app):
        app.config['TESTING'] = False

        @app.route('/test-error')
        def trigger_error():
            raise Exception('Test error')

        with app.test_client() as test_client:
            response = test_client.get('/test-error')
            assert response.status_code == 500
            assert 'Internal server error' in response.get_json()['error']

        app.config['TESTING'] = True


# -------------------- 1.2 TestHealthCheck --------------------
class TestHealthCheck:
    """Test health check endpoint"""

    def test_health_endpoint_success(self, client):
        response = client.get('/api/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'

    @patch('app.routes.db.session.execute')
    def test_health_endpoint_database_error(self, mock_execute, client):
        mock_execute.side_effect = Exception('Database connection failed')
        response = client.get('/api/health')
        assert response.status_code == 503
        data = response.get_json()
        assert data['status'] == 'unhealthy'
        assert data['database'] == 'disconnected'
        assert 'error' in data


# -------------------- 1.3 TestTodoModel --------------------
class TestTodoModel:
    """Test Todo model methods"""

    def test_todo_to_dict(self, app):
        with app.app_context():
            todo = Todo(title='Test Todo', description='Test Description')
            db.session.add(todo)
            db.session.commit()

            todo_dict = todo.to_dict()
            assert todo_dict['title'] == 'Test Todo'
            assert todo_dict['description'] == 'Test Description'
            assert todo_dict['completed'] is False
            assert 'id' in todo_dict
            assert 'created_at' in todo_dict
            assert 'updated_at' in todo_dict

    def test_todo_repr(self, app):
        with app.app_context():
            todo = Todo(title='Test Todo')
            db.session.add(todo)
            db.session.commit()

            repr_str = repr(todo)
            assert 'Todo' in repr_str
            assert 'Test Todo' in repr_str


# -------------------- 1.4 TestTodoAPI --------------------
class TestTodoAPI:
    """Test Todo CRUD operations"""

    def test_get_empty_todos(self, client):
        response = client.get('/api/todos')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] == 0
        assert data['data'] == []

    def test_create_todo_with_full_data(self, client):
        todo_data = {'title': 'Test Todo', 'description': 'This is a test todo'}
        response = client.post('/api/todos', json=todo_data)
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['title'] == 'Test Todo'
        assert data['data']['description'] == 'This is a test todo'
        assert data['data']['completed'] is False
        assert 'message' in data

    def test_create_todo_with_title_only(self, client):
        todo_data = {'title': 'Test Todo Only Title'}
        response = client.post('/api/todos', json=todo_data)
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['title'] == 'Test Todo Only Title'
        assert data['data']['description'] == ''

    def test_create_todo_without_title(self, client):
        response = client.post('/api/todos', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data
        assert 'Title is required' in data['error']

    def test_create_todo_with_none_data(self, client):
        response = client.post('/api/todos', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    @patch('app.routes.db.session.commit')
    def test_create_todo_database_error(self, mock_commit, client):
        mock_commit.side_effect = SQLAlchemyError('Database error')
        response = client.post('/api/todos', json={'title': 'Test'})
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_get_todo_by_id(self, client, app):
        with app.app_context():
            todo = Todo(title='Test Todo', description='Test Description')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        response = client.get(f'/api/todos/{todo_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['title'] == 'Test Todo'
        assert data['data']['description'] == 'Test Description'

    def test_get_nonexistent_todo(self, client):
        response = client.get('/api/todos/9999')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data
        assert 'not found' in data['error'].lower()

    def test_update_todo_title(self, client, app):
        with app.app_context():
            todo = Todo(title='Original Title')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {'title': 'Updated Title'}
        response = client.put(f'/api/todos/{todo_id}', json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['title'] == 'Updated Title'
        assert 'message' in data

    def test_update_todo_description(self, client, app):
        with app.app_context():
            todo = Todo(title='Test', description='Old Description')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {'description': 'New Description'}
        response = client.put(f'/api/todos/{todo_id}', json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['description'] == 'New Description'

    def test_update_todo_completed_status(self, client, app):
        with app.app_context():
            todo = Todo(title='Test')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {'completed': True}
        response = client.put(f'/api/todos/{todo_id}', json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['completed'] is True

    def test_update_todo_all_fields(self, client, app):
        with app.app_context():
            todo = Todo(title='Original', description='Old')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        update_data = {
            'title': 'New Title',
            'description': 'New Description',
            'completed': True
        }
        response = client.put(f'/api/todos/{todo_id}', json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['title'] == 'New Title'
        assert data['data']['description'] == 'New Description'
        assert data['data']['completed'] is True

    def test_update_nonexistent_todo(self, client):
        response = client.put('/api/todos/9999', json={'title': 'Updated'})
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    @patch('app.routes.db.session.commit')
    def test_update_todo_database_error(self, mock_commit, client, app):
        with app.app_context():
            todo = Todo(title='Test')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        mock_commit.side_effect = SQLAlchemyError('Database error')
        response = client.put(f'/api/todos/{todo_id}', json={'title': 'New'})
        assert response.status_code == 500

    def test_delete_todo(self, client, app):
        with app.app_context():
            todo = Todo(title='To Be Deleted')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        response = client.delete(f'/api/todos/{todo_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'message' in data

        response = client.get(f'/api/todos/{todo_id}')
        assert response.status_code == 404

    def test_delete_nonexistent_todo(self, client):
        response = client.delete('/api/todos/9999')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False

    @patch('app.routes.db.session.delete')
    def test_delete_todo_database_error(self, mock_commit, client, app):
        with app.app_context():
            todo = Todo(title='Test')
            db.session.add(todo)
            db.session.commit()
            todo_id = todo.id

        mock_commit.side_effect = SQLAlchemyError('Database error')
        response = client.delete(f'/api/todos/{todo_id}')
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False

    def test_get_all_todos_ordered(self, client, app):
        with app.app_context():
            todos = [Todo(title='Todo 1'), Todo(title='Todo 2'), Todo(title='Todo 3')]
            db.session.add_all(todos)
            db.session.commit()

        response = client.get('/api/todos')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['count'] == 3
        assert data['data'][0]['title'] == 'Todo 3'
        assert data['data'][2]['title'] == 'Todo 1'

    @patch('app.routes.Todo.query')
    def test_get_todos_database_error(self, mock_query, client):
        mock_query.order_by.return_value.all.side_effect = SQLAlchemyError('DB Error')
        response = client.get('/api/todos')
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False


# -------------------- 1.5 TestIntegration --------------------
class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_todo_lifecycle(self, client):
        create_response = client.post('/api/todos', json={
            'title': 'Integration Test Todo',
            'description': 'Testing full lifecycle'
        })
        assert create_response.status_code == 201
        todo_id = create_response.get_json()['data']['id']

        read_response = client.get(f'/api/todos/{todo_id}')
        assert read_response.status_code == 200
        assert read_response.get_json()['data']['title'] == 'Integration Test Todo'

        update_response = client.put(f'/api/todos/{todo_id}', json={
            'title': 'Updated Integration Test',
            'completed': True
        })
        assert update_response.status_code == 200
        updated_data = update_response.get_json()['data']
        assert updated_data['title'] == 'Updated Integration Test'
        assert updated_data['completed'] is True

        delete_response = client.delete(f'/api/todos/{todo_id}')
        assert delete_response.status_code == 200

        verify_response = client.get(f'/api/todos/{todo_id}')
        assert verify_response.status_code == 404

    def test_multiple_todos_workflow(self, client):
        for i in range(5):
            response = client.post('/api/todos', json={
                'title': f'Todo {i+1}',
                'completed': i % 2 == 0
            })
            assert response.status_code == 201

        response = client.get('/api/todos')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 5

        todo_id = data['data'][0]['id']
        response = client.put(f'/api/todos/{todo_id}', json={'completed': True})
        assert response.status_code == 200

        response = client.delete(f'/api/todos/{todo_id}')
        assert response.status_code == 200

        response = client.get('/api/todos')
        assert response.get_json()['count'] == 4
