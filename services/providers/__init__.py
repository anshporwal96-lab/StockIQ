"""
services/providers/__init__.py
==============================
Chooses which data provider the application uses, based on .env.

This is the ONLY place in the codebase that knows which provider classes exist.
Everything else just calls get_provider() and uses the returned object.
"""

from config import Config
from services.providers.base import BaseProvider, DataProviderError, empty_result
from services.providers.demo_provider import DemoProvider

# Built once and reused, because creating a provider can be expensive.
_provider_instance = None


def get_provider():
    """Return the configured data provider.

    DATA_PROVIDER=demo      -> DemoProvider     (offline sample data)
    DATA_PROVIDER=yfinance  -> YFinanceProvider (real data, needs `pip install yfinance`)

    To add your own source, import it and add a branch below.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    choice = Config.DATA_PROVIDER

    if choice == "yfinance":
        # Imported lazily so a missing yfinance install cannot stop the app
        # from starting in demo mode.
        from services.providers.yfinance_provider import YFinanceProvider

        _provider_instance = YFinanceProvider()
    else:
        _provider_instance = DemoProvider()

    return _provider_instance


def reset_provider():
    """Forget the cached provider. Used by tests that switch providers."""
    global _provider_instance
    _provider_instance = None


__all__ = [
    "BaseProvider",
    "DataProviderError",
    "DemoProvider",
    "empty_result",
    "get_provider",
    "reset_provider",
]
