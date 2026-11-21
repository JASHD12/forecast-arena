"""Model loading helpers (4-bit base, LoRA adapter); heavy imports stay inside the functions."""

from __future__ import annotations

from typing import Any

LORA_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


def load_base(model_id: str, *, revision: str | None = None, four_bit: bool = False) -> Any:
    """Load a causal LM; `four_bit` uses NF4 with double quantization (needs a CUDA GPU)."""
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    kwargs: dict[str, Any] = {"revision": revision, "torch_dtype": torch.float16}
    if four_bit:
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        kwargs["device_map"] = {"": 0}
    return AutoModelForCausalLM.from_pretrained(model_id, **kwargs)


def add_lora(
    model: Any,
    *,
    r: int = 16,
    alpha: int = 32,
    dropout: float = 0.05,
    four_bit: bool = False,
    seed: int = 0,
) -> Any:
    """Wrap the model with a LoRA adapter on all attention and MLP projections."""
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    torch.manual_seed(seed)
    if four_bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    cfg = LoraConfig(
        r=r,
        lora_alpha=alpha,
        lora_dropout=dropout,
        target_modules=list(LORA_TARGETS),
        bias="none",
        task_type="CAUSAL_LM",
    )
    return get_peft_model(model, cfg)
