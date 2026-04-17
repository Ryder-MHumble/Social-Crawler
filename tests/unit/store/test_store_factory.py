# -*- coding: utf-8 -*-
"""Unit tests for Store Factory functionality."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from store.excel_store_base import ExcelStoreBase
from store.xhs import XhsStoreFactory
from store.xhs._store_impl import (
    XhsCsvStoreImplement,
    XhsDbStoreImplement,
    XhsJsonStoreImplement,
    XhsSqliteStoreImplement,
)


class _FakeMongoStore:
    pass


class TestXhsStoreFactory:
    """Test cases for XhsStoreFactory."""

    @patch("config.SAVE_DATA_OPTION", "csv")
    def test_create_csv_store(self):
        store = XhsStoreFactory.create_store()
        assert isinstance(store, XhsCsvStoreImplement)

    @patch("config.SAVE_DATA_OPTION", "json")
    def test_create_json_store(self):
        store = XhsStoreFactory.create_store()
        assert isinstance(store, XhsJsonStoreImplement)

    @patch("config.SAVE_DATA_OPTION", "db")
    def test_create_db_store(self):
        store = XhsStoreFactory.create_store()
        assert isinstance(store, XhsDbStoreImplement)

    @patch("config.SAVE_DATA_OPTION", "sqlite")
    def test_create_sqlite_store(self):
        store = XhsStoreFactory.create_store()
        assert isinstance(store, XhsSqliteStoreImplement)

    @patch.dict(XhsStoreFactory.STORES, {"mongodb": _FakeMongoStore}, clear=False)
    @patch("config.SAVE_DATA_OPTION", "mongodb")
    def test_create_mongodb_store_uses_registered_class(self):
        store = XhsStoreFactory.create_store()
        assert isinstance(store, _FakeMongoStore)

    @patch("config.SAVE_DATA_OPTION", "excel")
    def test_create_excel_store(self):
        store = XhsStoreFactory.create_store()
        assert isinstance(store, ExcelStoreBase)

    @patch("config.SAVE_DATA_OPTION", "invalid")
    def test_invalid_store_option(self):
        with pytest.raises(ValueError) as exc_info:
            XhsStoreFactory.create_store()

        assert "Invalid save option" in str(exc_info.value)

    def test_all_stores_registered(self):
        expected_stores = {
            "csv",
            "json",
            "db",
            "postgres",
            "sqlite",
            "mongodb",
            "excel",
            "supabase",
        }
        assert expected_stores.issubset(XhsStoreFactory.STORES.keys())
