from .base import LoginError, SiteAdapter
from .demo_portal import DemoPortalAdapter

ADAPTERS = {DemoPortalAdapter.name: DemoPortalAdapter}


def get_adapter(name: str, base_url: str) -> SiteAdapter:
    try:
        return ADAPTERS[name](base_url)
    except KeyError:
        raise ValueError(f"Unknown site adapter '{name}'. Available: {', '.join(ADAPTERS)}") from None


__all__ = ["ADAPTERS", "LoginError", "SiteAdapter", "get_adapter"]
