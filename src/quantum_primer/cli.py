import argparse
import json
from pathlib import Path

from .config import Settings
from .models import Question
from .service import create_graph


def main():
    parser = argparse.ArgumentParser(prog="quantum-primer")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Index all sources from a JSON catalog")
    ingest.add_argument("catalog", type=Path)
    ingest.add_argument("--dry-run", action="store_true", help="Parse/chunk without network calls")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("cases", type=Path)
    evaluate.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    args = parser.parse_args()
    settings = Settings()
    if args.command == "ingest":
        from .ingest import load_chunks

        chunks = load_chunks(args.catalog)
        if args.dry_run:
            print(
                json.dumps(
                    {"chunks": len(chunks), "sources": sorted({c.source_id for c in chunks})}
                )
            )
        else:
            from .providers import index_corpus

            print(json.dumps(index_corpus(settings, chunks)))
    elif args.command == "ask":
        question = Question(question=args.question)
        result = create_graph(settings).invoke({"question": question.question})["response"]
        print(result.model_dump_json(indent=2))
    else:
        from .evaluation import evaluate

        report = evaluate(create_graph(settings), args.cases)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {args.output}; human faithfulness review is still required.")


if __name__ == "__main__":
    main()
