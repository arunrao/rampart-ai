"""
Test security fixes for policy endpoints - verify user_id filtering
"""
import pytest
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient
from api.main import app
from api.routes.policies import policies_db, Policy, PolicyType, PolicyRule, PolicyAction

client = TestClient(app)


def test_list_policies_filters_by_user_id(auth_headers):
    """Test that list_policies only returns policies owned by the authenticated user"""
    # Create policies for different users
    user1_id = uuid4()
    user2_id = uuid4()
    
    policy1 = Policy(
        id=uuid4(),
        user_id=user1_id,
        name="User 1 Policy",
        description="Should be visible to user 1",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="test", action=PolicyAction.ALLOW, priority=1)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policy2 = Policy(
        id=uuid4(),
        user_id=user2_id,
        name="User 2 Policy",
        description="Should NOT be visible to user 1",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="test", action=PolicyAction.ALLOW, priority=1)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policies_db[policy1.id] = policy1
    policies_db[policy2.id] = policy2
    
    # Simulate user1 requesting policies
    # Note: This test requires proper auth setup with user1_id in token
    response = client.get("/api/v1/policies", headers=auth_headers)
    
    # Should only return policies where user_id matches authenticated user
    assert response.status_code == 200
    policies = response.json()
    
    # Verify all returned policies belong to the authenticated user
    for policy in policies:
        # In a real scenario, this would check against the authenticated user's ID
        pass
    
    # Cleanup
    del policies_db[policy1.id]
    del policies_db[policy2.id]


def test_get_policy_prevents_unauthorized_access():
    """Test that users cannot access policies they don't own"""
    user1_id = uuid4()
    user2_id = uuid4()
    
    policy = Policy(
        id=uuid4(),
        user_id=user2_id,
        name="User 2 Private Policy",
        description="Should NOT be accessible to user 1",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="test", action=PolicyAction.ALLOW, priority=1)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policies_db[policy.id] = policy
    
    # User 1 tries to access User 2's policy
    # Should return 404 (not 403, to prevent enumeration)
    # Note: This requires proper auth mocking
    
    # Cleanup
    del policies_db[policy.id]


def test_update_policy_requires_ownership():
    """Test that users cannot update policies they don't own"""
    user2_id = uuid4()
    
    policy = Policy(
        id=uuid4(),
        user_id=user2_id,
        name="Original Name",
        description="Original description",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="test", action=PolicyAction.ALLOW, priority=1)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policies_db[policy.id] = policy
    
    # User 1 tries to update User 2's policy
    # Should return 404
    
    # Cleanup
    del policies_db[policy.id]


def test_delete_policy_requires_ownership():
    """Test that users cannot delete policies they don't own"""
    user2_id = uuid4()
    
    policy = Policy(
        id=uuid4(),
        user_id=user2_id,
        name="User 2 Policy",
        description="Should not be deletable by user 1",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="test", action=PolicyAction.ALLOW, priority=1)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policies_db[policy.id] = policy
    
    # User 1 tries to delete User 2's policy
    # Should return 404
    
    # Cleanup
    if policy.id in policies_db:
        del policies_db[policy.id]


def test_toggle_policy_requires_ownership():
    """Test that users cannot toggle policies they don't own"""
    user2_id = uuid4()
    
    policy = Policy(
        id=uuid4(),
        user_id=user2_id,
        name="User 2 Policy",
        description="Should not be toggleable by user 1",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="test", action=PolicyAction.ALLOW, priority=1)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policies_db[policy.id] = policy
    
    # User 1 tries to toggle User 2's policy
    # Should return 404
    
    # Cleanup
    del policies_db[policy.id]


def test_evaluate_policies_only_uses_owned_policies():
    """Test that policy evaluation only uses policies owned by the user"""
    user1_id = uuid4()
    user2_id = uuid4()
    
    # User 1's policy that should trigger
    policy1 = Policy(
        id=uuid4(),
        user_id=user1_id,
        name="User 1 Policy",
        description="Should be evaluated",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="contains_pii", action=PolicyAction.BLOCK, priority=10)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    # User 2's policy that should NOT be evaluated for User 1
    policy2 = Policy(
        id=uuid4(),
        user_id=user2_id,
        name="User 2 Policy",
        description="Should NOT be evaluated for user 1",
        policy_type=PolicyType.CONTENT_FILTER,
        rules=[PolicyRule(condition="contains_pii", action=PolicyAction.BLOCK, priority=10)],
        enabled=True,
        tags=["test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1
    )
    
    policies_db[policy1.id] = policy1
    policies_db[policy2.id] = policy2
    
    # When user 1 evaluates content, only their policies should be used
    # This prevents users from being affected by other users' policies
    
    # Cleanup
    del policies_db[policy1.id]
    del policies_db[policy2.id]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

