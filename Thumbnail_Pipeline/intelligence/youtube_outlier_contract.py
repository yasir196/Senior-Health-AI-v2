from __future__ import annotations
from typing import Any

def build_youtube_outlier_brief(*,title:str,category:str,topic:str|None=None)->dict[str,Any]:
    """Provider-neutral discovery contract. Search execution is supplied by the runtime/connector."""
    return {
        "query_context":{"immutable_title":title,"topic":topic or title,"category":category},
        "search_requirements":{
            "platform":"youtube",
            "same_topic_first":True,
            "same_category_expand":True,
            "same_channel_only":False,
            "outlier_required":False,
            "inspect_title_and_thumbnail_together":True,
        },
        "capture_fields":["video_id","channel_name","video_title","thumbnail_url_or_path","views","published_at","topic_match","category_match","outlier_evidence"],
        "selection_policy":[
            "Prefer relevant same-topic examples.",
            "Expand to same-category examples when useful.",
            "Do not restrict discovery to this channel.",
            "An outlier is useful evidence but is not mandatory.",
            "Never call a video an outlier without observed comparative evidence.",
            "Inspect each selected video's title and thumbnail as a pair.",
        ],
        "use_policy":"External YouTube examples are inspiration/reference evidence only. They do not override the channel's eligible winner evidence or the immutable project title.",
    }

def combine_new_project_evidence(*,winner_prior:dict[str,Any],youtube_examples:list[dict[str,Any]])->dict[str,Any]:
    return {
        "primary_learning_source":"channel_winners",
        "winner_prior":winner_prior,
        "youtube_reference_examples":youtube_examples,
        "instruction":"Build the new thumbnail direction from channel winner evidence, then use relevant YouTube title+thumbnail pairs to broaden visual/hook ideas. Do not copy a thumbnail verbatim and do not import loser patterns as positive priors.",
    }
