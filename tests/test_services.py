import json
import os
import struct
import sys
from pathlib import Path

from app.codex_service import run_codex_stl
from app.config import Settings
from app.image_service import generate_views
from app.schemas import GenerateRequest


def _settings(tmp_path, codex_bin="codex"):
    return Settings(
        service_api_key=None,
        codex_bin=str(codex_bin),
        job_root=tmp_path,
        job_timeout_seconds=10,
        max_input_bytes=1_000_000,
        max_artifact_bytes=1_000_000,
        keep_jobs=True,
    )


def _binary_stl():
    return (
        b"fake".ljust(80, b"\0")
        + struct.pack("<I", 1)
        + struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 3, 4, 0)
    )


def test_image_service_generates_requested_views(tmp_path):
    fake = tmp_path / "fake_codex_images.py"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args=sys.argv[1:]\n"
        "assert '--approve-for-me' not in args\n"
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "job=pathlib.Path(args[args.index('--cd')+1]); out=job/'output'; out.mkdir(exist_ok=True)\n"
        "png=b'\\x89PNG\\r\\n\\x1a\\n' + b'test'\n"
        "[(out/name).write_bytes(png) for name in ['01_front.png','02_back.png']]\n"
        "answer=pathlib.Path(args[args.index('--output-last-message')+1])\n"
        "answer.write_text(json.dumps({'summary':'ok','warnings':[]}))\n"
        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':6,'output_tokens':4,'total_tokens':10}}))\n"
    )
    fake.chmod(0o755)
    input_path = tmp_path / "input.png"
    input_path.write_bytes(b"input")
    request = GenerateRequest.model_validate({
        "mode": "render_3d_views",
        "images": [{"data_base64": "aW5wdXQ=", "mime_type": "image/png"}],
        "requirement": "same object",
        "views": ["front", "back"],
    })
    artifacts, usage, warnings = generate_views(
        request, [input_path], tmp_path / "job" / "output", _settings(tmp_path, fake),
    )
    assert [item.filename for item in artifacts] == ["01_front.png", "02_back.png"]
    assert usage.total_tokens == 10
    assert warnings == []


def test_codex_service_collects_artifacts_and_usage(tmp_path):
    fake = tmp_path / "fake_codex.py"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, struct, sys, zipfile\n"
        "args=sys.argv[1:]\n"
        "job=pathlib.Path(args[args.index('--cd')+1]); out=job/'output'; out.mkdir(exist_ok=True)\n"
        "stl=b'fake'.ljust(80,b'\\0')+struct.pack('<I',1)+struct.pack('<12fH',0,0,1,0,0,0,2,0,0,0,3,4,0)\n"
        "(out/'model.stl').write_bytes(stl)\n"
        "[(out/name).write_bytes(b'png') for name in ['preview_front.png','preview_back.png','preview_oblique.png']]\n"
        "(out/'validation.json').write_text('{}')\n"
        "with zipfile.ZipFile(out/'source.zip','w') as z: z.writestr('source.txt','ok')\n"
        "answer=pathlib.Path(args[args.index('--output-last-message')+1])\n"
        "answer.write_text(json.dumps({'summary':'ok','classification':'simplified_initial','warnings':[]}))\n"
        "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':11,'output_tokens':7,'total_tokens':18},'thread_id':'t_1'}))\n"
    )
    fake.chmod(0o755)
    image = tmp_path / "ref.png"
    image.write_bytes(b"x")
    request = GenerateRequest.model_validate({
        "mode": "reconstruct_stl",
        "images": [{"data_base64": "eA==", "mime_type": "image/png"}],
        "requirement": "printable",
        "dimensions_mm": {"height": 40},
    })
    artifacts, usage, result, dimensions, thread = run_codex_stl(
        request, [image], tmp_path / "job", _settings(tmp_path, fake)
    )
    assert len(artifacts) == 6
    assert usage.total_tokens == 18
    assert result["classification"] == "simplified_initial"
    assert dimensions["width"] == 2
    assert dimensions["depth"] == 3
    assert dimensions["height"] == 4
    assert thread == "t_1"

