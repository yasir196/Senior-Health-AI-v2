import pytest
from Thumbnail_Pipeline.providers import ProviderRegistry, validate_provider_config

class Backend:
    def __init__(self, config): self.config=config
    def generate(self, request): return {"request":request}

def test_registry_builds_explicit_backend():
    r=ProviderRegistry(); r.register("demo", lambda c: Backend(c))
    b=r.build("DEMO",{"model":"image-x"})
    assert b.config["model"]=="image-x"

def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError):
        ProviderRegistry().build("missing")

def test_registry_rejects_duplicate_registration():
    r=ProviderRegistry(); r.register("demo",lambda c: Backend(c))
    with pytest.raises(ValueError):
        r.register("demo",lambda c: Backend(c))

def test_config_rejects_embedded_secrets():
    with pytest.raises(ValueError):
        validate_provider_config({"provider":"demo","settings":{"api_key":"do-not-store"}})

def test_config_keeps_non_secret_provider_settings():
    c=validate_provider_config({"provider":"demo","settings":{"model":"image-x","size":"1280x720"}})
    assert c["provider"]=="demo"
    assert c["settings"]["size"]=="1280x720"

def test_no_vendor_is_registered_by_default():
    assert ProviderRegistry().names()==()
