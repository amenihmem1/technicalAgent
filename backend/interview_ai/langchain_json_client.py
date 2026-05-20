from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from openai import RateLimitError

from interview_ai.base import LLMRateLimitError
from interview_ai.payloads import parse_json_response

logger = logging.getLogger(__name__)


class LangChainJSONClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        default_temperature: float,
        max_tokens: int,
        azure_endpoint: str = "",
        azure_deployment: str = "",
        azure_api_version: str = "2025-01-01-preview",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.azure_endpoint = (azure_endpoint or "").strip().rstrip("/")
        self.azure_deployment = (azure_deployment or "").strip()
        self.azure_api_version = (azure_api_version or "2025-01-01-preview").strip()
        self.is_azure = bool(self.azure_endpoint and self.azure_deployment)
        self.default_temperature = default_temperature
        self.max_tokens = max_tokens
        if self.is_azure:
            self.client = AzureChatOpenAI(
                azure_endpoint=self.azure_endpoint,
                azure_deployment=self.azure_deployment,
                api_version=self.azure_api_version,
                api_key=self.api_key,
                temperature=self.default_temperature,
                max_tokens=self.max_tokens,
            )
        else:
            self.client = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.default_temperature,
                max_tokens=self.max_tokens,
            )

    def request_json(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        log_mode: str,
        phase: str,
    ) -> dict[str, Any]:
        response = self._create_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            log_mode=log_mode,
            phase=phase,
        )
        content = self._response_text(response)
        parsed = parse_json_response(content)
        if parsed:
            return parsed

        logger.warning(
            "Reponse LLM LangChain non parsable phase=%s raw_preview=%s",
            phase,
            content[:500],
        )

        compact_retry = messages + [
            {
                "role": "user",
                "content": (
                    "Ta reponse precedente etait tronquee ou invalide. "
                    "Recommence en JSON tres compact sur UNE seule ligne. "
                    "Pas de markdown. Pas de texte hors JSON. "
                    "Chaque champ evidence doit etre tres court, 6 mots maximum. "
                    "notes doit etre [] sauf si necessaire. "
                    "Hors phase FINAL, final_report doit etre null. "
                    "Ferme correctement tous les objets et tableaux."
                ),
            }
        ]
        retry = self._create_completion(
            messages=compact_retry,
            max_tokens=max(max_tokens, 700),
            temperature=min(temperature, 0.2),
            log_mode=f"{log_mode}_compact_retry",
            phase=phase,
        )
        retry_content = self._response_text(retry)
        parsed = parse_json_response(retry_content)
        if parsed:
            return parsed

        logger.warning(
            "Reponse LLM LangChain retry non parsable phase=%s raw_preview=%s",
            phase,
            retry_content[:500],
        )
        raise ValueError("Reponse vide apres parsing")

    def healthcheck(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "ok": False,
            "base_url": self.azure_endpoint if self.is_azure else self.base_url,
            "model": self.model,
            "provider": "azure_openai" if self.is_azure else "langchain",
        }
        if self.is_azure:
            info["deployment"] = self.azure_deployment
            info["api_version"] = self.azure_api_version
            info["ok"] = bool(self.api_key and self.azure_endpoint and self.azure_deployment)
            if not info["ok"]:
                info["error"] = "Azure OpenAI endpoint, deployment ou cle API manquant"
            return info
        try:
            response = httpx.get(
                f"{self.base_url}/models",
                timeout=5.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            models = [item.get("id", "") for item in response.json().get("data", [])]
            info["ok"] = True
            info["available_models"] = [item for item in models if item]
            info["model_available"] = self.model in info["available_models"]
            return info
        except Exception as exc:
            info["error"] = str(exc)
            return info

    def _create_completion(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        log_mode: str,
        phase: str,
    ) -> Any:
        started_at = time.perf_counter()
        try:
            response = self._build_chain(
                temperature=temperature,
                max_tokens=max_tokens,
            ).invoke(self._build_chain_payload(messages))
        except RateLimitError as exc:
            logger.warning("Quota LLM LangChain atteint phase=%s model=%s error=%s", phase, self.model, exc)
            raise self._to_rate_limit_error(exc) from exc

        logger.info(
            "LLM LangChain call mode=%s phase=%s model=%s ms=%.1f",
            log_mode,
            phase,
            self.model,
            (time.perf_counter() - started_at) * 1000,
        )
        return response

    def _build_chain(self, *, temperature: float, max_tokens: int):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("system", "Memoire session:\n{memory_snapshot}"),
                MessagesPlaceholder(variable_name="conversation"),
            ]
        )
        bind_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if not self.is_azure:
            bind_kwargs["extra_body"] = {"reasoning_effort": "low", "include_reasoning": False}
        model = self.client.bind(**bind_kwargs)
        return (
            RunnableLambda(lambda payload: payload)
            | prompt
            | model
            | StrOutputParser()
        )

    def _build_chain_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        system_prompt, conversation = self._split_prompt_messages(messages)
        return {
            "system_prompt": system_prompt,
            "conversation": conversation,
            "memory_snapshot": self._build_memory_snapshot(messages),
        }

    @staticmethod
    def _split_prompt_messages(messages: list[dict[str, str]]) -> tuple[str, list[Any]]:
        system_parts: list[str] = []
        conversation: list[Any] = []
        for message in messages:
            role = str(message.get("role", "user")).strip().lower()
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                conversation.append(AIMessage(content=content))
            else:
                conversation.append(HumanMessage(content=content))

        merged_system = "\n\n".join(system_parts).strip()
        return merged_system, (conversation or [HumanMessage(content="")])

    @staticmethod
    def _build_memory_snapshot(messages: list[dict[str, str]]) -> str:
        history_lines: list[str] = []
        for message in messages[-6:]:
            role = str(message.get("role", "user")).strip().lower()
            content = " ".join(str(message.get("content", "")).split()).strip()
            if not content:
                continue
            if role == "system":
                continue
            label = "Assistant" if role == "assistant" else "User"
            history_lines.append(f"{label}: {content[:220]}")
        return "\n".join(history_lines) if history_lines else "Aucun historique exploitable."

    @staticmethod
    def _response_text(response: Any) -> str:
        if isinstance(response, dict):
            output = response.get("output")
            if isinstance(output, str):
                return output.strip()
            messages = response.get("messages", [])
            if isinstance(messages, list) and messages:
                last_message = messages[-1]
                if isinstance(last_message, dict):
                    content = last_message.get("content", "")
                else:
                    content = getattr(last_message, "content", "")
                if isinstance(content, str):
                    return content.strip()
                if isinstance(content, list):
                    parts: list[str] = []
                    for item in content:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict):
                            text = item.get("text")
                            if isinstance(text, str):
                                parts.append(text)
                    return "\n".join(part.strip() for part in parts if part.strip()).strip()
                return str(content or "").strip()
        if isinstance(response, str):
            return response.strip()
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(part.strip() for part in parts if part.strip()).strip()
        return str(content or "").strip()

    @staticmethod
    def _extract_retry_after_hint(message: str) -> str:
        if not message:
            return ""
        match = re.search(r"try again in\s+([0-9hms\.\s]+)", message, re.IGNORECASE)
        return match.group(1).strip().rstrip(".") if match else ""

    def _to_rate_limit_error(self, exc: RateLimitError) -> LLMRateLimitError:
        raw_message = str(exc).strip()
        retry_after = self._extract_retry_after_hint(raw_message)
        wait_hint = f" Reessayez dans {retry_after}." if retry_after else " Reessayez dans quelques minutes."
        return LLMRateLimitError(
            f"Quota LLM LangChain atteint pour le modele {self.model}.{wait_hint} "
            "Vous pouvez aussi reduire les tokens, changer de modele ou augmenter le quota du compte."
        )
