"""Process local Module 2 and Module 3 JSON files through Module 4."""

import asyncio
import json
from pathlib import Path

from services.file_integration_service import build_request
from services.pipeline import run_pipeline
from starlette.datastructures import UploadFile
from io import BytesIO

ROOT = Path(__file__).resolve().parent
MODULE2 = ROOT / "integration_input" / "module2" / "module2_output.json"
MODULE3 = ROOT / "integration_input" / "module3" / "module3_output.json"
OUTPUT = ROOT / "integration_output" / "module4_decision.json"


async def main() -> None:
    with MODULE2.open("rb") as file2, MODULE3.open("rb") as file3:
        upload2 = UploadFile(filename=MODULE2.name, file=BytesIO(file2.read()))
        upload3 = UploadFile(filename=MODULE3.name, file=BytesIO(file3.read()))
        request, metadata = await build_request(upload2, upload3)
    result = run_pipeline(request, integration_metadata=metadata)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"Module 4 decision written to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
