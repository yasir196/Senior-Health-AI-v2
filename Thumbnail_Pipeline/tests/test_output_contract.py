import pytest

from Thumbnail_Pipeline.outputs import validate_render_result
from Thumbnail_Pipeline.renderer import dispatch_renderer


def _handoff():
    return {
        "renderer_status":"not_invoked",
        "immutable_title":"LOCKED",
        "render_contract":{"layout":"text_left_subject_right"},
        "provenance":{"source":"phase2_concept_direction"},
    }


def _result(path="Thumbnail_Pipeline/outputs/project-1/thumb.png"):
    return {"output_path":path,"width":1280,"height":720,"mime_type":"image/png","asset_id":"asset-1","immutable_title":"LOCKED"}


def test_output_contract_accepts_isolated_thumbnail_asset():
    artifact=validate_render_result(_result(),_handoff())
    assert artifact["asset"]["output_path"]=="Thumbnail_Pipeline/outputs/project-1/thumb.png"
    assert artifact["immutable_title"]=="LOCKED"
    assert artifact["qa_status"]=="pending"


@pytest.mark.parametrize("path",[
    "output.png",
    "Thumbnail_Pipeline/../config.json",
    "../Thumbnail_Pipeline/outputs/thumb.png",
    "/Thumbnail_Pipeline/outputs/thumb.png",
])
def test_output_contract_rejects_paths_outside_pipeline_outputs(path):
    with pytest.raises(ValueError):
        validate_render_result(_result(path),_handoff())


def test_output_contract_rejects_non_image_extension():
    with pytest.raises(ValueError):
        validate_render_result(_result("Thumbnail_Pipeline/outputs/project-1/result.json"),_handoff())


def test_output_contract_rejects_title_mutation():
    result=_result()
    result["immutable_title"]="CHANGED"
    with pytest.raises(ValueError):
        validate_render_result(result,_handoff())


def test_dispatch_validates_provider_result_before_exposing_artifact():
    class FakeProvider:
        def render(self,handoff):
            return _result()
    response=dispatch_renderer(_handoff(),provider=FakeProvider(),execute=True)
    assert response["renderer_invoked"] is True
    assert response["artifact"]["asset"]["width"]==1280
    assert response["artifact"]["qa_status"]=="pending"


def test_dispatch_rejects_provider_output_outside_isolated_folder():
    class BadProvider:
        def render(self,handoff):
            return _result("config.json")
    with pytest.raises(ValueError):
        dispatch_renderer(_handoff(),provider=BadProvider(),execute=True)
