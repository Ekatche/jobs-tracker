
def test_create_user(client):
    """
    Test de la création d'un utilisateur.
    """
    user_data = {
        "username": "johndoe",
        "email": "john.doe@example.com",
        "password": "strongPassword234",
        "full_name": "John Doe",
    }
    response = client.post("auth/register/", json=user_data)
    assert response.status_code == 201
    created_user = response.json()
    assert created_user["username"] == user_data["username"]
    assert created_user["email"] == user_data["email"]
    assert created_user["full_name"] == user_data["full_name"]


def test_user_already_exists(client):
    """
    Test de la création d'un utilisateur déjà existant.
    """
    # Création de l'utilisateur initial
    initial_user = {
        "username": "duplicatetest",
        "email": "duplicate@test.com",
        "password": "strongPassword234",
        "full_name": "Duplicate Test",
    }
    client.post("auth/register/", json=initial_user)

    # Tentative avec le même username
    response = client.post("auth/register", json=initial_user)
    assert response.status_code == 400

    # Tentative avec un username différent mais le même email
    initial_user["username"] = "anotherduplicate"
    response = client.post("auth/register/", json=initial_user)
    assert response.status_code == 400


def test_user_authentication(client, registered_user):
    """
    Test de l'authentification d'un utilisateur.
    """
    # Utilise les données de registered_user au lieu d'en créer un nouveau
    login_data = {
        "username": registered_user["username"],
        "password": "TestPassword123",  # Mot de passe de test_user
    }
    response = client.post("auth/token", data=login_data)
    assert response.status_code == 200
    token = response.json().get("access_token")
    assert token is not None


def test_refresh_token(client, registered_user):
    """
    Test du rafraîchissement de token.
    """
    # D'abord authentifier l'utilisateur
    login_response = client.post(
        "auth/token",
        data={
            "username": registered_user["username"],
            "password": "TestPassword123",
        },
    )
    assert login_response.status_code == 200

    # Récupérer le refresh token
    tokens = login_response.json()
    assert "refresh_token" in tokens
    refresh_token = tokens["refresh_token"]

    # Utiliser le refresh token pour obtenir un nouveau token
    refresh_response = client.post(
        "auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 200

    # Vérifier que la réponse contient les nouveaux tokens
    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert "token_type" in new_tokens
    assert new_tokens["token_type"] == "bearer"

    # Vérifier que les nouveaux tokens sont différents des anciens
    assert new_tokens["access_token"] != tokens["access_token"]
    # Le refresh token est également renouvelé (rotation des tokens)
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Vérifier que le nouveau access_token fonctionne
    me_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
    me_response = client.get("auth/me", headers=me_headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == registered_user["username"]


def test_user_authentication_invalid(client):
    """
    Test de l'authentification d'un utilisateur avec des identifiants invalides.
    """
    # Création d'un utilisateur connu pour ensuite tester avec des identifiants incorrects
    valid_user = {
        "username": "validuser",
        "email": "valid.user@example.com",
        "password": "correctPassword123",
        "full_name": "Valid User",
    }
    client.post("auth/register", json=valid_user)
    # Test avec username invalide
    invalid_username = {
        "username": "invaliduser",
        "password": "correctPassword123",
    }
    response = client.post("auth/token", data=invalid_username)
    assert response.status_code == 401


def test_change_password(client, registered_user, auth_headers):
    """
    Test du changement de mot de passe.
    """
    # Utilisation directe de auth_headers au lieu de refaire l'authentification
    new_password_data = {
        "current_password": "TestPassword123",
        "new_password": "NewPassword456",
    }

    change_password_response = client.post(
        "auth/change-password",
        json=new_password_data,
        headers=auth_headers,
    )
    assert change_password_response.status_code == 200

    # Vérification: le nouveau mot de passe fonctionne
    new_login = client.post(
        "auth/token",
        data={
            "username": registered_user["username"],
            "password": "NewPassword456",
        },
    )
    assert new_login.status_code == 200


def test_get_current_user(client, registered_user, auth_headers):
    """
    Test pour récupérer les informations de l'utilisateur actuel.
    """
    me_response = client.get("auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    user_info = me_response.json()
    assert user_info["username"] == registered_user["username"]
    assert user_info["email"] == registered_user["email"]
    assert user_info["full_name"] == registered_user["full_name"]


def test_update_user(client):
    """
    Test de mise à jour des informations utilisateur.
    """
    # Création d'un utilisateur spécifique pour ce test
    user_data = {
        "username": "updateuser",
        "email": "update.user@example.com",
        "password": "updatePassword123",
        "full_name": "Update User",
    }
    register_response = client.post("auth/register", json=user_data)
    assert register_response.status_code == 201
    user_id = register_response.json()["_id"]

    # Authentification
    login_response = client.post(
        "auth/token",
        data={
            "username": "updateuser",
            "password": "updatePassword123",
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # Mise à jour des informations - utilisation de l'URL correcte
    headers = {"Authorization": f"Bearer {access_token}"}
    update_data = {
        "full_name": "Updated Full Name",
        "email": "new.email@example.com",
    }

    # Utilisation de PUT sur /users/{user_id} au lieu de PATCH sur /auth/me
    update_response = client.put(f"users/{user_id}", headers=headers, json=update_data)

    assert update_response.status_code == 200
    updated_user = update_response.json()
    assert updated_user["full_name"] == "Updated Full Name"
    assert updated_user["email"] == "new.email@example.com"
    assert updated_user["username"] == "updateuser"
