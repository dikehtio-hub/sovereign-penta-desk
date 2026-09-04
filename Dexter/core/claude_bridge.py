"""
Dexter Claude Bridge
Connects to Anthropic Claude API and Claude Code CLI for deep reasoning and terminal coding tasks.
"""

from __future__ import annotations
import os
import subprocess
from typing import Any, Dict, Optional

from .config import settings
from .vault_bridge import VaultBridge


class ClaudeBridge:
    """Interface to invoke Anthropic Claude and execute Claude Code CLI sessions."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.vault = VaultBridge()
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is not set. Please add it to your environment or Dexter/configs/.env"
                )
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "The `anthropic` package is required. Install with: pip install anthropic"
                )
        return self._client

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        log_to_vault: bool = True,
        task_name: Optional[str] = None,
    ) -> str:
        """
        Generate text response from Anthropic Claude API.
        Optionally logs output directly to Obsidian 05_Logs_&_Telemetry/Claude_Runs/.
        """
        model_name = model or settings.default_reasoning_model
        client = self._get_client()

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            kwargs["system"] = system_instruction

        response = client.messages.create(**kwargs)
        output_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                output_text += block.text

        if log_to_vault:
            t_name = task_name or f"Claude_{model_name}_Prompt"
            self.vault.log_agent_run(
                agent_name="Claude",
                task_name=t_name,
                input_prompt=prompt,
                output_response=output_text,
                metadata={"model": model_name, "temperature": temperature},
            )

        return output_text

    def run_claude_code(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout_seconds: int = 300,
        log_to_vault: bool = True,
        task_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a prompt via Claude Code CLI (`claude -p "..."`).
        Captures output and logs execution trace to Obsidian.
        """
        work_dir = cwd or str(settings.dev_root)
        t_name = task_name or "Claude_Code_Execution"

        try:
            # Run Claude Code CLI in non-interactive print mode
            cmd = ["claude", "-p", prompt]
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=True,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            return_code = result.returncode

            combined_output = stdout
            if stderr:
                combined_output += f"\n\n### Errors / Warnings\n```\n{stderr}\n```"

            if log_to_vault:
                self.vault.log_agent_run(
                    agent_name="Claude_Code",
                    task_name=t_name,
                    input_prompt=prompt,
                    output_response=combined_output,
                    metadata={"return_code": return_code, "cwd": work_dir},
                )

            return {
                "success": return_code == 0,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code,
            }

        except subprocess.TimeoutExpired:
            err_msg = f"Claude Code execution timed out after {timeout_seconds}s"
            if log_to_vault:
                self.vault.log_agent_run(
                    agent_name="Claude_Code",
                    task_name=t_name,
                    input_prompt=prompt,
                    output_response=f"**Error:** {err_msg}",
                    metadata={"status": "timeout"},
                )
            return {"success": False, "stdout": "", "stderr": err_msg, "return_code": -1}

        except FileNotFoundError:
            err_msg = "Claude CLI executable (`claude`) not found in PATH."
            return {"success": False, "stdout": "", "stderr": err_msg, "return_code": -1}
