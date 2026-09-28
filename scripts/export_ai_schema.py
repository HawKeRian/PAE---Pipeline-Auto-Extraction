"""Export the structured-output schema supplied to Local Llama."""

import json
from pathlib import Path

from pae.ai.models import RequirementAnalysis


def main() -> None:
    output_path = Path("schemas/requirement-analysis.schema.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(RequirementAnalysis.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
