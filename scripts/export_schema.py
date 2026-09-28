"""Export the canonical Pipeline Specification JSON Schema."""

import json
from pathlib import Path

from pae.domain.models import PipelineSpecification


def main() -> None:
    output_path = Path("schemas/pipeline-specification.schema.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(PipelineSpecification.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
