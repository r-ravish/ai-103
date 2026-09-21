"""
backend/tests/test_db_models.py
--------------------------------
Automated unit tests for the core SQLAlchemy 2.0 ORM models:
    - User
    - Document
    - Ticket
    - Feedback
    - EscalationEvent

Tests run in-memory using an SQLite engine to validate schema,
relationships, cascades, constraints, and defaults.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

# Ensure backend/ is on sys.path
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from db.models import (
    Base,
    Document,
    DocumentStatus,
    EscalationEvent,
    Feedback,
    Ticket,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)


class TestDatabaseModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite engine for schema and ORM testing
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)

    def setUp(self):
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_schema_tables_and_indexes(self):
        inspector = inspect(self.engine)
        tables = set(inspector.get_table_names())
        expected_tables = {"users", "documents", "tickets", "feedback", "escalation_events"}
        self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

        # Check indexes on users
        user_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
        self.assertIn("ix_users_email", user_indexes)
        self.assertIn("ix_users_role", user_indexes)

        # Check indexes on documents
        doc_indexes = {idx["name"] for idx in inspector.get_indexes("documents")}
        self.assertIn("ix_documents_document_id", doc_indexes)
        self.assertIn("ix_documents_status", doc_indexes)

        # Check indexes on tickets
        ticket_indexes = {idx["name"] for idx in inspector.get_indexes("tickets")}
        self.assertIn("ix_tickets_ticket_id", ticket_indexes)
        self.assertIn("ix_tickets_status", ticket_indexes)

    def test_user_creation_defaults(self):
        user = User(
            name="Alice Employee",
            email="alice@company.com",
        )
        self.session.add(user)
        self.session.commit()

        self.assertIsNotNone(user.id)
        self.assertEqual(user.role, UserRole.employee)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.password_hash)
        self.assertIsInstance(user.created_at, datetime)

    def test_document_creation_and_relationship(self):
        user = User(name="Uploader Admin", email="uploader@company.com", role=UserRole.hr_admin)
        self.session.add(user)
        self.session.flush()

        doc = Document(
            document_id="leave_policy_2026",
            filename="leave_policy.pdf",
            title="Employee Leave Policy 2026",
            uploaded_by_id=user.id,
        )
        self.session.add(doc)
        self.session.commit()

        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.status, DocumentStatus.pending)
        self.assertEqual(doc.uploaded_by.email, "uploader@company.com")
        self.assertIn(doc, user.documents)

    def test_ticket_creation_and_defaults(self):
        user = User(name="Ticket Creator", email="creator@company.com")
        self.session.add(user)
        self.session.flush()

        ticket = Ticket(
            ticket_id="TKT-ABC12345",
            title="VPN access issue",
            description="Unable to connect to production VPN gateway",
            created_by_id=user.id,
        )
        self.session.add(ticket)
        self.session.commit()

        self.assertIsNotNone(ticket.id)
        self.assertEqual(ticket.priority, TicketPriority.medium)
        self.assertEqual(ticket.status, TicketStatus.open)
        self.assertEqual(ticket.created_by.name, "Ticket Creator")
        self.assertIn(ticket, user.tickets)

    def test_feedback_and_escalation_event(self):
        user = User(name="Feedback User", email="feedback@company.com")
        self.session.add(user)
        self.session.flush()

        ticket = Ticket(
            ticket_id="TKT-ESC99999",
            title="Payroll escalation",
            description="Direct deposit delay",
            priority=TicketPriority.high,
            created_by_id=user.id,
        )
        self.session.add(ticket)
        self.session.flush()

        esc = EscalationEvent(
            response_id="resp-123",
            question="When will direct deposit arrive?",
            reason="knowledge_gap",
            ticket_id=ticket.id,
            success=True,
        )
        self.session.add(esc)

        fb = Feedback(
            response_id="resp-123",
            question="When will direct deposit arrive?",
            rating=4,
            comment="Helpful escalation to payroll",
            user_id=user.id,
        )
        self.session.add(fb)
        self.session.commit()

        self.assertIsNotNone(esc.id)
        self.assertTrue(esc.success)
        self.assertEqual(esc.ticket.ticket_id, "TKT-ESC99999")
        self.assertIn(esc, ticket.escalation_events)

        self.assertIsNotNone(fb.id)
        self.assertEqual(fb.rating, 4)
        self.assertEqual(fb.user.email, "feedback@company.com")
        self.assertIn(fb, user.feedback_list)

    def test_nullable_foreign_keys_for_pre_auth_mode(self):
        # Models must work even when user_id is None (pre-auth phase)
        doc = Document(
            document_id="anonymous_doc_01",
            filename="handbook.pdf",
            uploaded_by_id=None,
        )
        ticket = Ticket(
            ticket_id="TKT-ANON-001",
            title="Anonymous help request",
            description="Agent question without logged-in user",
            created_by_id=None,
        )
        fb = Feedback(
            question="Sample question?",
            rating=5,
            user_id=None,
        )
        self.session.add_all([doc, ticket, fb])
        self.session.commit()

        self.assertIsNone(doc.uploaded_by_id)
        self.assertIsNone(ticket.created_by_id)
        self.assertIsNone(fb.user_id)


if __name__ == "__main__":
    unittest.main()
