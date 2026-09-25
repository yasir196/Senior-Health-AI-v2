from __future__ import annotations
import argparse
import json
from pathlib import Path

def resolve_project(project: str, root: str = "Projects") -> Path:
    base = Path(root).resolve()
    candidate = (base / project).resolve()
    if candidate.parent != base:
        raise ValueError("Project must be a direct child of Projects/.")
    if not candidate.is_dir():
        raise FileNotFoundError(f"Project folder not found: {candidate}")
    return candidate

def main() -> int:
    parser=argparse.ArgumentParser(description="Thumbnail Pipeline prompt-only project CLI")
    parser.add_argument("--project", required=True, help="Exact folder name under Projects/")
    parser.add_argument("--projects-root", default="Projects")
    args=parser.parse_args()
    project=resolve_project(args.project,args.projects_root)
    files=sorted(p.name for p in project.iterdir() if p.is_file())
    print(json.dumps({"status":"project_resolved","project":args.project,"project_path":str(project),"files":files},indent=2))
    print("Project resolved successfully. Prompt generation requires the reviewed composition/gate workflow; no image generation or YouTube upload is invoked.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
