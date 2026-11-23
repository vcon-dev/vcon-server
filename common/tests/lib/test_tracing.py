import builtins
import sys
import types
from unittest.mock import Mock

from lib.tracing import init_tracing


def test_init_tracing_instruments_when_dependency_is_available():
    instrumentor = Mock()
    openai_module = types.ModuleType("openinference.instrumentation.openai")
    openai_module.OpenAIInstrumentor = Mock(return_value=instrumentor)

    openinference_module = types.ModuleType("openinference")
    instrumentation_module = types.ModuleType("openinference.instrumentation")
    openinference_module.instrumentation = instrumentation_module
    instrumentation_module.openai = openai_module
    instrumentation_module.TraceConfig = Mock(name="TraceConfig")

    original_modules = sys.modules.copy()
    sys.modules.update(
        {
            "openinference": openinference_module,
            "openinference.instrumentation": instrumentation_module,
            "openinference.instrumentation.openai": openai_module,
        }
    )
    try:
        init_tracing()
    finally:
        sys.modules.clear()
        sys.modules.update(original_modules)

    instrumentor.instrument.assert_called_once()
    # LLM content capture stays off: every content switch is passed as hidden.
    config_kwargs = instrumentation_module.TraceConfig.call_args.kwargs
    assert config_kwargs["hide_inputs"] is True
    assert config_kwargs["hide_outputs"] is True
    assert config_kwargs["hide_input_messages"] is True
    assert config_kwargs["hide_output_messages"] is True
    assert instrumentor.instrument.call_args.kwargs["config"] is instrumentation_module.TraceConfig.return_value


def test_init_tracing_logs_when_dependency_is_missing(monkeypatch, caplog):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openinference.instrumentation.openai":
            raise ImportError("missing dependency")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    init_tracing()

    assert "will not produce llm spans" in caplog.text.lower()


def test_init_tracing_logs_when_instrumentor_fails(caplog):
    instrumentor = Mock()
    instrumentor.instrument.side_effect = RuntimeError("boom")
    openai_module = types.ModuleType("openinference.instrumentation.openai")
    openai_module.OpenAIInstrumentor = Mock(return_value=instrumentor)

    openinference_module = types.ModuleType("openinference")
    instrumentation_module = types.ModuleType("openinference.instrumentation")
    openinference_module.instrumentation = instrumentation_module
    instrumentation_module.openai = openai_module
    instrumentation_module.TraceConfig = Mock(name="TraceConfig")

    original_modules = sys.modules.copy()
    sys.modules.update(
        {
            "openinference": openinference_module,
            "openinference.instrumentation": instrumentation_module,
            "openinference.instrumentation.openai": openai_module,
        }
    )
    try:
        init_tracing()
    finally:
        sys.modules.clear()
        sys.modules.update(original_modules)

    assert "failed to instrument openai" in caplog.text.lower()
