"""Explicit real-model benchmark with synthetic prompts; no user history is read."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profiles', nargs='+', choices=['economy', 'balanced', 'quality'], default=['quality', 'balanced'])
    parser.add_argument('--runs', type=int, choices=range(1, 4), default=2)
    parser.add_argument('--model', help='An already installed local model; never downloads')
    parser.add_argument('--cold', action='store_true', help='Unload the selected model before each profile')
    args = parser.parse_args()
    from PyQt6.QtCore import QCoreApplication, QEventLoop
    from brave_ollama_request import ChatRequest
    from core.ollama_chat import Settings, bounded_messages
    from core.ollama_service import ensure_server

    app = QCoreApplication([])
    settings = Settings.read()
    if args.model:
        settings = replace(settings, model=args.model)
    ensure_server(settings.url, enabled=settings.autostart)
    samples = []
    for profile in args.profiles:
        selected = replace(settings, profile=profile)
        for run in range(args.runs):
            messages = bounded_messages([], 'Ali 12 ta daftar oldi, 5 tasini berdi. Nechta qoldi? O‘zbek tilida bitta qisqa gap bilan javob bering.', profile)
            job = ChatRequest(selected, messages, cold=args.cold and run == 0, keep_alive='5m')
            loop = QEventLoop()
            result = []
            job.finished.connect(lambda text, error, cancelled: (result.append((text, error, cancelled)), loop.quit()))
            started = time.monotonic()
            job.start()
            loop.exec()
            text, error, cancelled = result[0]
            row = dict(job.metrics, wall_s=time.monotonic()-started, run=run+1,
                       requested_cold=args.cold and run == 0, error=error, answer=text)
            samples.append(row)
            print(json.dumps(row, ensure_ascii=True), flush=True)
            job.deleteLater()
            app.processEvents()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding='utf-8')
            if error or cancelled:
                raise SystemExit(1)


if __name__ == '__main__':
    main()
