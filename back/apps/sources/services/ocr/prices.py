"""What a request may cost: the models the budget allows, their prices, a request's worst case in a batch or alone,
and the budget's two refusals (OverBudget, ModelNotAllowed)."""
from decimal import Decimal

from django.conf import settings


# Standard $ per million tokens (input, output); the Batch API is half (checked 18 Oct 2026).
PRICES = {
    'claude-opus-5-5': (4.00, 20.00),
    'claude-sonnet-5-5': (2.00, 10.00),
    'claude-haiku-5-5': (0.10, 0.50),
}


class OverBudget(RuntimeError):
    def __init__(self, message: str = '', worst: Decimal = Decimal('0')):
        super().__init__(message)
        self.worst = worst      # what the refused batch could have cost: more than a whole run allows, it never fits


class ModelNotAllowed(RuntimeError):
    pass


def check_model(model: str) -> None:
    """Refuse, before anything is sent, a model the budget does not allow (settings.LLM_MODELS_ALLOWED): A10's
    one model held by code. Every reservation passes here, so no batch or call escapes it."""
    allowed = [m.strip() for m in settings.LLM_MODELS_ALLOWED.split(',') if m.strip()]
    if allowed and model not in allowed:
        raise ModelNotAllowed(f'{model}: not among the allowed models ({", ".join(allowed)})')


def price(model: str, usage, *, batch: bool) -> Decimal:
    rate_in, rate_out = PRICES[model]
    factor = 0.5 if batch else 1.0
    tokens_in = (getattr(usage, 'input_tokens', 0) or 0) + 1.25 * (getattr(usage, 'cache_creation_input_tokens', 0) or 0)
    tokens_out = getattr(usage, 'output_tokens', 0) or 0
    return Decimal(str(round((tokens_in * rate_in + tokens_out * rate_out) * factor / 1e6, 6)))


def _worst_case(model: str, n: int, max_tokens: int, *, batch: bool) -> Decimal:
    check_model(model)
    rate_in, rate_out = PRICES[model]
    tokens_in = 4784 + 600  # the image's cap in tiles plus the prompt
    factor = 0.5 if batch else 1.0
    return Decimal(str(n * (tokens_in * rate_in + max_tokens * rate_out) * factor / 1e6))


def call_worst(model: str, chars: int, max_tokens: int) -> Decimal:
    """The most one request outside a batch (standard price) can cost: a token a character of what it sends (Arabic
    runs nearer two characters a token, so a true ceiling), and every token of max_tokens written."""
    check_model(model)
    rate_in, rate_out = PRICES[model]
    return Decimal(str(round((chars * rate_in + max_tokens * rate_out) / 1e6, 6)))
