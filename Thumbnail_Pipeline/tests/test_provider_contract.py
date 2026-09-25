import pytest
from Thumbnail_Pipeline.providers import ContractRendererProvider, build_provider_request

def _handoff():
    return {"immutable_title":"LOCKED","category":"mobility","render_contract":{"layout":"split","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear","thumbnail_text":"START HERE"},"provenance":{"source":"test"},"renderer_status":"not_invoked"}

class Backend:
    def __init__(self,result=None): self.calls=[]; self.result=result or {"output_path":"Thumbnail_Pipeline/outputs/p1/thumb.png","width":1280,"height":720}
    def generate(self,request): self.calls.append(request); return self.result

def test_provider_request_preserves_reviewed_contract_and_title():
    request=build_provider_request(_handoff())
    assert request["immutable_title"]=="LOCKED"
    assert request["instructions"]["thumbnail_text"]=="START HERE"
    assert request["instructions"]["safe_zone"]=="bottom_right_clear"

def test_provider_request_rejects_unresolved_contract():
    handoff=_handoff(); handoff["render_contract"]["safe_zone"]=None
    with pytest.raises(ValueError):
        build_provider_request(handoff)

def test_contract_provider_calls_injected_backend_once():
    backend=Backend(); provider=ContractRendererProvider(backend)
    result=provider.render(_handoff())
    assert len(backend.calls)==1
    assert result["width"]==1280

def test_contract_provider_rejects_non_mapping_backend_result():
    class BadBackend:
        def generate(self,request): return "bad"
    with pytest.raises(ValueError):
        ContractRendererProvider(BadBackend()).render(_handoff())

def test_provider_layer_has_no_bundled_external_execution():
    backend=Backend()
    provider=ContractRendererProvider(backend)
    assert backend.calls==[]
    assert provider.backend is backend
