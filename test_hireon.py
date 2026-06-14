import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ── Shared test data ──────────────────────────────────────────────
TEST_EMAIL    = "testuser_pytest@gmail.com"
TEST_PHONE    = "+237600000001"
TEST_PASSWORD = "testpass123"
TEST_TOKEN    = None
TEST_USER_ID  = None

# ════════════════════════════════════════════════════════════════════
# 1. USER REGISTRATION
# ════════════════════════════════════════════════════════════════════

def test_register_success():
    """New user registers with valid data — should return 201 + token"""
    response = client.post("/auth/register", json={
        "name":         "Test User Pytest",
        "email":        TEST_EMAIL,
        "phone_number": TEST_PHONE,
        "password":     TEST_PASSWORD,
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == TEST_EMAIL

    # Save token and user_id for later tests
    global TEST_TOKEN, TEST_USER_ID
    TEST_TOKEN  = data["access_token"]
    TEST_USER_ID = data["user"]["user_id"]


def test_register_duplicate_email():
    """Registering with same email — should return 400"""
    response = client.post("/auth/register", json={
        "name":         "Another User",
        "email":        TEST_EMAIL,
        "phone_number": "+237600000099",
        "password":     TEST_PASSWORD,
    })
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_register_duplicate_phone():
    """Registering with same phone — should return 400"""
    response = client.post("/auth/register", json={
        "name":         "Another User",
        "email":        "another@gmail.com",
        "phone_number": TEST_PHONE,
        "password":     TEST_PASSWORD,
    })
    assert response.status_code == 400
    assert "Phone number already registered" in response.json()["detail"]


def test_register_invalid_category():
    """Registering with an invalid skill category — should return 400"""
    response = client.post("/auth/register", json={
        "name":         "Bad Category",
        "email":        "badcat@gmail.com",
        "phone_number": "+237611000002",
        "password":     TEST_PASSWORD,
        "category":     "Astronaut",
    })
    assert response.status_code == 400


# ════════════════════════════════════════════════════════════════════
# 2. USER LOGIN
# ════════════════════════════════════════════════════════════════════

def test_login_with_email():
    """Login using email + correct password — should return 200 + token"""
    response = client.post("/auth/login", json={
        "identifier": TEST_EMAIL,
        "password":   TEST_PASSWORD,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_phone():
    """Login using phone number + correct password — should return 200 + token"""
    response = client.post("/auth/login", json={
        "identifier": TEST_PHONE,
        "password":   TEST_PASSWORD,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password():
    """Login with wrong password — should return 401"""
    response = client.post("/auth/login", json={
        "identifier": TEST_EMAIL,
        "password":   "wrongpassword",
    })
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_login_nonexistent_user():
    """Login with email that doesn't exist — should return 401"""
    response = client.post("/auth/login", json={
        "identifier": "nobody@gmail.com",
        "password":   TEST_PASSWORD,
    })
    assert response.status_code == 401


# ════════════════════════════════════════════════════════════════════
# 3. PROFILE MANAGEMENT
# ════════════════════════════════════════════════════════════════════

def test_get_my_profile():
    """Get own profile with valid token — should return 200 + user data"""
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL


def test_get_profile_no_token():
    """Get profile without token — should return 401"""
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_profile_invalid_token():
    """Get profile with fake token — should return 401"""
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer faketoken123"}
    )
    assert response.status_code == 401


def test_update_profile():
    """Update profile fields — should return 200 + updated data"""
    response = client.put(
        "/auth/me",
        json={
            "city":     "Yaounde",
            "location": "Centre",
            "category": "Electrician",
            "bio":      "I am a professional electrician with 5 years of experience.",
        },
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["city"]     == "Yaounde"
    assert data["category"] == "Electrician"


def test_update_invalid_category():
    """Update with invalid skill category — should return 400"""
    response = client.put(
        "/auth/me",
        json={"category": "Pilot"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 400


# ════════════════════════════════════════════════════════════════════
# 4. GET ALL USERS
# ════════════════════════════════════════════════════════════════════

def test_get_all_users():
    """Get all users — should return 200 + list"""
    response = client.get("/auth/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_users_filter_by_category():
    """Filter users by category — should return only Electricians"""
    response = client.get("/auth/users?category=Electrician")
    assert response.status_code == 200
    users = response.json()
    for user in users:
        assert user["category"] == "Electrician"


def test_get_users_filter_by_availability():
    """Filter users by availability=true — all returned should be available"""
    response = client.get("/auth/users?availability=true")
    assert response.status_code == 200
    users = response.json()
    for user in users:
        assert user["availability"] == True


# ════════════════════════════════════════════════════════════════════
# 5. HIRE REQUEST
# ════════════════════════════════════════════════════════════════════

# Register a second user to act as provider
PROVIDER_TOKEN  = None
PROVIDER_ID     = None
REQUEST_ID      = None

def test_register_provider():
    """Register a second user who will act as provider"""
    response = client.post("/auth/register", json={
        "name":         "Provider Test",
        "email":        "provider_pytest@gmail.com",
        "phone_number": "+237622000002",
        "password":     TEST_PASSWORD,
        "category":     "Plumber",
    })
    assert response.status_code == 201

    global PROVIDER_TOKEN, PROVIDER_ID
    data          = response.json()
    PROVIDER_TOKEN = data["access_token"]
    PROVIDER_ID   = data["user"]["user_id"]


def test_send_hire_request():
    """Client sends hire request to provider — should return 201"""
    response = client.post(
        "/hire/request",
        json={
            "provider_id":    PROVIDER_ID,
            "description":    "I need my bathroom pipes fixed urgently",
            "scheduled_date": "2026-06-15",
            "scheduled_time": "10:00",
            "latitude":       3.848,
            "longitude":      11.502,
            "address":        "Bastos, Yaounde",
        },
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"

    global REQUEST_ID
    REQUEST_ID = data["request_id"]


def test_cannot_hire_yourself():
    """User tries to hire themselves — should return 400"""
    response = client.post(
        "/hire/request",
        json={
            "provider_id":    TEST_USER_ID,
            "description":    "Self hire attempt",
            "scheduled_date": "2026-06-15",
            "scheduled_time": "10:00",
        },
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 400
    assert "cannot hire yourself" in response.json()["detail"].lower()


def test_get_notifications():
    """Provider gets notifications — should include the hire request"""
    response = client.get(
        "/hire/notifications",
        headers={"Authorization": f"Bearer {PROVIDER_TOKEN}"}
    )
    assert response.status_code == 200
    notifs = response.json()
    assert len(notifs) >= 1
    types = [n["type"] for n in notifs]
    assert "hire_request" in types


def test_accept_hire_request():
    """Provider accepts hire request — status should become accepted"""
    response = client.put(
        f"/hire/request/{REQUEST_ID}/accept",
        headers={"Authorization": f"Bearer {PROVIDER_TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_cannot_accept_twice():
    """Provider tries to accept already-accepted request — should return 400"""
    response = client.put(
        f"/hire/request/{REQUEST_ID}/accept",
        headers={"Authorization": f"Bearer {PROVIDER_TOKEN}"}
    )
    assert response.status_code == 400
    assert "already responded" in response.json()["detail"].lower()


# ════════════════════════════════════════════════════════════════════
# 6. REVIEWS
# ════════════════════════════════════════════════════════════════════

def test_mark_job_completed():
    """Client marks accepted job as completed — should return success"""
    response = client.put(
        f"/reviews/complete/{REQUEST_ID}",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert "completed" in response.json()["message"].lower()


def test_submit_review():
    """Client submits 5-star review — should return 201"""
    response = client.post(
        "/reviews",
        json={
            "request_id": REQUEST_ID,
            "rating":     5,
            "comment":    "Excellent work, very professional!",
        },
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["rating"]  == 5


def test_cannot_review_twice():
    """Client tries to review same job twice — should return 400"""
    response = client.post(
        "/reviews",
        json={
            "request_id": REQUEST_ID,
            "rating":     3,
            "comment":    "Second review attempt",
        },
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 400
    assert "already reviewed" in response.json()["detail"].lower()


def test_invalid_rating():
    """Submit rating of 6 (out of range) — should return 400"""
    response = client.post(
        "/reviews",
        json={
            "request_id": REQUEST_ID,
            "rating":     6,
        },
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 400


def test_get_user_profile_with_rating():
    """Get provider public profile — should include average_rating"""
    response = client.get(f"/reviews/profile/{PROVIDER_ID}")
    assert response.status_code == 200
    data = response.json()
    assert "average_rating" in data
    assert data["total_reviews"] >= 1


# ════════════════════════════════════════════════════════════════════
# 7. RECOMMENDATIONS
# ════════════════════════════════════════════════════════════════════

def test_get_recommendations():
    """Get recommendations for logged-in user — should return a list"""
    response = client.get(
        "/recommendations",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ════════════════════════════════════════════════════════════════════
# 8. CHAT
# ════════════════════════════════════════════════════════════════════

def test_get_conversations():
    """Get conversations list — should return 200 + list"""
    response = client.get(
        "/chat/conversations",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_start_conversation():
    """Start conversation between client and provider — should return 200"""
    response = client.post(
        f"/chat/conversations/{PROVIDER_ID}",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert "conversation_id" in response.json()


def test_cannot_message_yourself():
    """Start conversation with yourself — should return 400"""
    response = client.post(
        f"/chat/conversations/{TEST_USER_ID}",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 400


# ════════════════════════════════════════════════════════════════════
# 9. PAYMENT PLANS
# ════════════════════════════════════════════════════════════════════

def test_get_payment_plans():
    """Get subscription plans — should return 3 plans"""
    response = client.get("/payment/plans")
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == 3
    keys = [p["key"] for p in plans]
    assert "quarterly"   in keys
    assert "semi_annual" in keys
    assert "annual"      in keys


def test_get_subscription_no_sub():
    """Get subscription status with no active sub — is_active should be False"""
    response = client.get(
        "/payment/subscription",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] == False


# ════════════════════════════════════════════════════════════════════
# 10. ROOT ENDPOINT
# ════════════════════════════════════════════════════════════════════

def test_root():
    """Root endpoint — should return running message"""
    response = client.get("/")
    assert response.status_code == 200
    assert "running" in response.json()["message"].lower()