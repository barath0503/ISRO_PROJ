"""Distributed RF clock synchronization dashboard."""

__all__ = ["create_app"]


def create_app():
    from rf_sync_dashboard.app import create_app as _create_app

    return _create_app()
