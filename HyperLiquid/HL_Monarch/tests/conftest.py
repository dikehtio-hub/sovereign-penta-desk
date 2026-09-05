import pytest


@pytest.fixture(autouse=True)
def _no_user_level_webhook(monkeypatch):
    """Round 54: WebhookAlerter falls back to the USER-level registry variable, and this
    machine has a real DISCORD_WEBHOOK_URL there. Tests must construct alerters that stay
    silent, so the registry fallback is neutralised for every test."""
    import analytics.alerter as alerter_module
    monkeypatch.setattr(alerter_module, "_registry_user_env", lambda name: None)
    for name in ("DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)
