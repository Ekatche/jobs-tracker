import pytest


@pytest.fixture
def task_data():
    """
    Retourne des données pour créer une tâche de test.
    """
    return {
        "title": "Tâche de test",
        "description": "Description de la tâche de test",
        "status": "En cours",
        "due_date": "2025-05-20T10:00:00Z",
    }


@pytest.fixture
def create_task(client, auth_headers, task_data):
    """
    Fixture qui crée une tâche et la retourne.
    """
    response = client.post("tasks/", json=task_data, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


def test_get_task(client, auth_headers, create_task):
    """
    Teste la récupération des tâches.
    """
    response = client.get("tasks/", headers=auth_headers)
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    assert tasks[0]["title"] == create_task["title"]


def test_get_tasks(client, auth_headers):
    """
    Teste la récupération de toutes les tâches.
    """
    task_statuses = ["À faire", "En cours", "Terminée"]
    created_tasks = []
    for i, status in enumerate(task_statuses):
        task_data = {
            "title": f"Tâche de test {i}",
            "description": f"Description de la tâche de test {i}",
            "status": status,
            "due_date": "2025-05-20T10:00:00Z",
        }
        response = client.post("tasks/", json=task_data, headers=auth_headers)
        assert response.status_code == 201
        created_tasks.append(response.json())
    all_tasks_response = client.get("tasks/", headers=auth_headers)
    assert all_tasks_response.status_code == 200
    all_tasks = all_tasks_response.json()
    assert len(all_tasks) == len(created_tasks)


def test_update_task(client, auth_headers, create_task):
    """
    Teste la mise à jour d'une tâche.
    """
    updated_data = {
        "title": "Tâche mise à jour",
        "description": "Description de la tâche mise à jour",
        "status": "Terminée",
        "due_date": "2025-06-20T10:00:00Z",
    }

    response = client.put(
        f"tasks/{create_task['_id']}/", json=updated_data, headers=auth_headers
    )
    assert response.status_code == 200
    updated_task = response.json()
    assert updated_task["title"] == updated_data["title"]


def test_delete_task(client, auth_headers, create_task):
    """
    Teste la suppression d'une tâche.
    """
    response = client.delete(f"tasks/{create_task['_id']}/", headers=auth_headers)
    assert response.status_code == 204
