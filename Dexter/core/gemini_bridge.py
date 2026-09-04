"""
Dexter Gemini Bridge
Connects to Google Gemini API for fast reasoning, large-context processing, and multimodal tasks.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from .config import settings
from .vault_bridge import VaultBridge


class GeminiBridge:
    """Interface to invoke Google Gemini models and log results to the Obsidian Vault."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.vault = VaultBridge()
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GEMINI_API_KEY is not set. Please add it to your environment or Dexter/configs/.env"
                )
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "The `google-genai` package is required. Install with: pip install google-genai"
                )
        return self._client

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        log_to_vault: bool = True,
        task_name: Optional[str] = None,
    ) -> str:
        """
        Generate text response from Gemini.
        Optionally logs output directly to Obsidian 05_Logs_&_Telemetry/Gemini_Runs/.
        """
        model_name = model or settings.default_fast_model
        client = self._get_client()

        # Build config
        config: Dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            config["system_instruction"] = system_instruction

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        output_text = response.text or ""

        if log_to_vault:
            t_name = task_name or f"Gemini_{model_name}_Prompt"
            self.vault.log_agent_run(
                agent_name="Gemini",
                task_name=t_name,
                input_prompt=prompt,
                output_response=output_text,
                metadata={"model": model_name, "temperature": temperature},
            )

        return output_text

    def analyze_vault_notes(
        self,
        note_paths: List[str],
        query: str,
        model: Optional[str] = None,
    ) -> str:
        """
        Use Gemini's massive context window to synthesize and analyze multiple Obsidian notes.
        """
        combined_context = []
        for p in note_paths:
            try:
                meta, body = self.vault.read_note(p)
                combined_context.append(f"--- NOTE: {p} ---\nMetadata: {meta}\n\n{body}\n")
            except Exception as e:
                combined_context.append(f"--- NOTE: {p} (Error reading: {e}) ---\n")

        full_prompt = (
            "You are a Dexter Knowledge Engine powered by Google Gemini.\n"
            "Analyze the following Obsidian Vault notes and answer the query accurately.\n\n"
            + "\n".join(combined_context)
            + f"\n\nQUERY:\n{query}"
        )

        return self.generate(
            prompt=full_prompt,
            model=model or settings.default_multimodal_model,
            task_name=f"Vault_Analysis_{len(note_paths)}_Notes",
        )
