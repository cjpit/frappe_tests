import pytest
import frappe
from unittest.mock import MagicMock
from frappe.defaults import *
import os


@pytest.fixture(scope='session')
def db_instance():
    # monkey patch the commit, so that records do not get saved to the database.
    frappe.connect(site=os.environ.get("site"))
    frappe.db.commit = MagicMock()
    yield frappe.db


@pytest.fixture()
def db_transaction(db_instance):
    # create a new transaction.
    db_instance.begin()
    yield db_instance
    db_instance.rollback()
