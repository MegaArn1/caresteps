"""Tests for the system-wide statistics endpoint."""

from __future__ import annotations

import dataclasses
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import repository as repo


@contextmanager
def isolated_client(tmp_path, monkeypatch, *, seed_demo: bool):
    """Bind the application to one temporary database for an HTTP test."""
    db_file = tmp_path / ("seeded-stats.db" if seed_demo else "empty-stats.db")

    from app import config as config_mod
    from app import main as main_mod
    from app.llm import provider as provider_mod
    from app.routes import api as api_mod

    fresh = dataclasses.replace(config_mod.SETTINGS, db_path=db_file)
    for module in (config_mod, main_mod, provider_mod, api_mod):
        monkeypatch.setattr(module, "SETTINGS", fresh, raising=False)

    from app.db import init_db

    init_db(db_file)
    with TestClient(main_mod.app) as test_client:
        if seed_demo:
            test_client.get("/app")
        yield test_client


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Run the application against an isolated, seeded SQLite database."""
    with isolated_client(tmp_path, monkeypatch, seed_demo=True) as test_client:
        yield test_client


@pytest.fixture()
def empty_client(tmp_path, monkeypatch):
    """Run the application against an initialized but unseeded database."""
    with isolated_client(tmp_path, monkeypatch, seed_demo=False) as test_client:
        yield test_client


def test_repository_system_metrics_match_demo_seed(conn, demo_user):
    metrics = repo.system_metrics(conn)

    assert metrics["total_users"] == 1
    assert metrics["total_bp_recordings"] == 11
    assert metrics["total_medications_tracked"] == 2
    assert metrics["active_barriers"] == 1
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    assert metrics["database_size_kb"] == (page_count * page_size + 1023) // 1024


def test_stats_endpoint_returns_flat_system_metrics(client):
    response = client.get("/api/stats")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "total_users",
        "total_bp_recordings",
        "total_medications_tracked",
        "active_barriers",
        "database_size_kb",
    }
    assert body["total_users"] == 1
    assert body["total_bp_recordings"] == 11
    assert body["total_medications_tracked"] == 2
    assert body["active_barriers"] == 1
    assert body["database_size_kb"] > 0


def test_stats_endpoint_does_not_seed_or_create_a_session(empty_client):
    response = empty_client.get("/api/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total_users"] == 0
    assert body["total_bp_recordings"] == 0
    assert body["total_medications_tracked"] == 0
    assert body["active_barriers"] == 0
    assert "caresteps_session" not in response.cookies

    health = empty_client.get("/healthz").json()
    assert health["profiles"] == 0


def test_explicit_days_query_preserves_period_statistics(client):
    response = client.get("/api/stats?days=14")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stats"]["readings"]["n"] == 10


def test_stats_route_is_declared_once():
    from app.routes import api, stats

    matching = [
        route
        for router in (api.router, stats.router)
        for route in router.routes
        if getattr(route, "path", None) == "/api/stats"
        and "GET" in getattr(route, "methods", set())
    ]
    assert len(matching) == 1
