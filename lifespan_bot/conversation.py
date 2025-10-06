from __future__ import annotations

import time
import uuid
from typing import Optional, List, Dict

from rich.console import Console
from rich.prompt import Prompt

from .api_client import BinjieClient
from .prompts import SYSTEM_PROMPT_FA
from .schemas import AssistantResponse, AssistantQuestion, AssistantFinal
from .fallback import RuleBasedFallback


class LifespanConversation:
    def __init__(self, client: BinjieClient, *, user_id: Optional[str] = None) -> None:
        self.client = client
        self.user_id = user_id or f"lifespan-cli-{uuid.uuid4().hex[:8]}"
        self.console = Console()
        self.qa_history: List[Dict[str, str]] = []
        self.fallback = RuleBasedFallback()

    def _compose_user_prompt(self) -> str:
        state_lines = [
            "وضعیت مصاحبه (JSON):",
        ]
        if self.qa_history:
            import json as _json
            state_lines.append(_json.dumps({"answers": self.qa_history}, ensure_ascii=False))
        else:
            state_lines.append('{"answers": []}')

        guidance_lines = [
            "راهنما:",
            "- اگر اطلاعات کافی نیست، فقط یک سوال جدید بپرس (فرم question).",
            "- اگر کافی است، نتیجه نهایی بده (فرم final).",
            "- خروجی باید فقط یک JSON معتبر باشد.",
        ]
        if not self.qa_history:
            guidance_lines.append("- این اولین نوبت است؛ اولین سوال را بپرس.")
        else:
            guidance_lines.append("- پاسخ‌های داده‌شده را لحاظ کن و مرحله بعد را پیش ببر.")

        return "\n".join(state_lines + [""] + guidance_lines)

    def _call_model(self) -> AssistantResponse:
        message = self._compose_user_prompt()
        # Always include the system prompt and discourage context carry-over by asking
        # for stateless behavior on the server side as much as possible.
        try:
            raw = self.client.generate(
                message,
                system=SYSTEM_PROMPT_FA,
                user_id=self.user_id,
                network=True,
                without_context=True,
                stream=False,
            )
            data = self.client.try_extract_json(raw)
            if data is None:
                # Attempt a repair call by reminding JSON-only rule
                raw2 = self.client.generate(
                    "فقط یک JSON معتبر طبق قالب خواسته‌شده برگردان. هیچ متن اضافی چاپ نکن.",
                    system=SYSTEM_PROMPT_FA,
                    user_id=self.user_id,
                    network=True,
                    without_context=True,
                    stream=False,
                )
                data = self.client.try_extract_json(raw2)
        except Exception:
            data = None
        if data is None or not isinstance(data, dict):
            # Fall back to local rule-based planner
            return self.fallback.next()

        # Validate against schema union; if kind missing, attempt gentle coercion
        kind = data.get("kind")
        try:
            if kind == "question":
                return AssistantQuestion.model_validate(data)
            if kind == "final":
                return AssistantFinal.model_validate(data)
        except Exception:
            # If validation fails, try coercion below
            pass

        # Coercion: if there is a 'question' field, wrap as question
        if isinstance(data.get("question"), str):
            try:
                return AssistantQuestion(kind="question", question=data["question"], choices=data.get("choices"))
            except Exception:
                return self.fallback.next()

        # Otherwise, fall back
        return self.fallback.next()

    def run_cli(self) -> None:
        self.console.print("[bold green]شروع مصاحبه تخمین طول‌عمر[/bold green]")
        self.console.print("برای خروج، کلیدهای Ctrl+C را بزنید.\n")

        # Kick off with START to get the first question
        response = self._call_model()

        while True:
            if isinstance(response, AssistantQuestion):
                self.console.print(f"[bold]سوال:[/bold] {response.question}")
                if response.choices:
                    # Show choices in a friendly way
                    for idx, ch in enumerate(response.choices, 1):
                        self.console.print(f"  {idx}. {ch}")
                answer = Prompt.ask("پاسخ شما")
                # Record into history for stateful prompting
                self.qa_history.append({"question": response.question, "answer": answer})
                # Feed fallback too, for continuity if we switch
                self.fallback.ingest(answer)
                # Send only the user's answer; server maintains context via userId
                response = self._call_model()
                continue

            if isinstance(response, AssistantFinal):
                self.console.rule("نتیجه نهایی")
                self.console.print(
                    f"[bold]تخمین طول‌عمر:[/bold] {response.lifespanEstimate:.1f} سال"
                )
                self.console.print(
                    f"[bold]اعتماد:[/bold] {int(response.confidence * 100)}%"
                )
                if response.reasoning:
                    self.console.print(f"[bold]استدلال:[/bold] {response.reasoning}")
                if response.advice:
                    self.console.print(f"[bold]پیشنهادها:[/bold] {response.advice}")
                self.console.print("\n[green]گفت‌وگو پایان یافت.[/green]")
                break

            time.sleep(0.1)
