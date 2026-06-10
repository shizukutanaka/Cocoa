"""Tests for database_manager — DatabaseManager, models, repositories."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))
import database_manager as _dm_module
from database_manager import (
    Avatar,
    DatabaseManager,
    User,
    UserRepository,
)

SQLALCHEMY_AVAILABLE = _dm_module.SQLALCHEMY_AVAILABLE
requires_sqlalchemy = unittest.skipUnless(SQLALCHEMY_AVAILABLE, "sqlalchemy not installed")


@requires_sqlalchemy
class TestDatabaseManagerInit(unittest.TestCase):

    def setUp(self):
        self.dm = DatabaseManager(database_url="sqlite:///:memory:")

    def tearDown(self):
        self.dm.close()

    def test_create_tables_does_not_raise(self):
        self.dm.create_tables()

    def test_get_session_returns_session(self):
        session = self.dm.get_session()
        self.assertIsNotNone(session)
        session.close()

    def test_health_check_returns_true(self):
        self.dm.create_tables()
        result = self.dm.health_check()
        self.assertTrue(result)


@requires_sqlalchemy
class TestUserModel(unittest.TestCase):

    def setUp(self):
        self.dm = DatabaseManager(database_url="sqlite:///:memory:")
        self.dm.create_tables()
        self.session = self.dm.get_session()

    def tearDown(self):
        self.session.close()
        self.dm.close()

    def test_create_user(self):
        user = User(username="testuser", email="test@example.com", password_hash="hash123")
        self.session.add(user)
        self.session.commit()
        self.assertIsNotNone(user.id)

    def test_query_user_by_username(self):
        user = User(username="queryuser", email="query@example.com", password_hash="hash")
        self.session.add(user)
        self.session.commit()
        result = self.session.query(User).filter(User.username == "queryuser").first()
        self.assertIsNotNone(result)
        self.assertEqual(result.email, "query@example.com")


@requires_sqlalchemy
class TestAvatarModel(unittest.TestCase):

    def setUp(self):
        self.dm = DatabaseManager(database_url="sqlite:///:memory:")
        self.dm.create_tables()
        self.session = self.dm.get_session()
        user = User(username="avatarowner", email="owner@example.com", password_hash="h")
        self.session.add(user)
        self.session.commit()
        self.user_id = user.id

    def tearDown(self):
        self.session.close()
        self.dm.close()

    def test_create_avatar(self):
        avatar = Avatar(user_id=self.user_id, name="TestAvatar")
        self.session.add(avatar)
        self.session.commit()
        self.assertIsNotNone(avatar.id)

    def test_avatar_belongs_to_user(self):
        avatar = Avatar(user_id=self.user_id, name="UserAvatar")
        self.session.add(avatar)
        self.session.commit()
        result = self.session.query(Avatar).filter(Avatar.user_id == self.user_id).first()
        self.assertEqual(result.name, "UserAvatar")


@requires_sqlalchemy
class TestUserRepository(unittest.TestCase):

    def setUp(self):
        self.dm = DatabaseManager(database_url="sqlite:///:memory:")
        self.dm.create_tables()
        self.session = self.dm.get_session()
        self.repo = UserRepository(self.session)

    def tearDown(self):
        self.session.close()
        self.dm.close()

    def test_create_returns_user(self):
        user = self.repo.create(username="repouser", email="repo@example.com", password_hash="h")
        self.assertIsNotNone(user.id)

    def test_get_by_id(self):
        user = self.repo.create(username="getuser", email="get@example.com", password_hash="h")
        fetched = self.repo.get_by_id(user.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.username, "getuser")

    def test_get_by_id_missing_returns_none(self):
        result = self.repo.get_by_id(99999)
        self.assertIsNone(result)

    def test_get_all_returns_list(self):
        self.repo.create(username="a1", email="a1@x.com", password_hash="h")
        self.repo.create(username="a2", email="a2@x.com", password_hash="h")
        all_users = self.repo.get_all()
        self.assertGreaterEqual(len(all_users), 2)
