import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from opentelemetry.context import get_value

from pulse_otel import Pulse, observe, pulse_agent, pulse_tool, util

# The key Pulse.enable_content_tracing writes into the OTel context. Traceloop reads
# either this context value or the TRACELOOP_TRACE_CONTENT env var to decide whether
# prompts/completions are logged as span attributes.
CONTENT_TRACING_KEY = "override_enable_content_tracing"


class TestEnableContentTracing:
    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            ({"enabled": True}, True),
            ({"enabled": False}, False),
            ({}, True),  # defaults to True
        ],
    )
    def test_sets_context_value(self, kwargs, expected):
        Pulse.enable_content_tracing(**kwargs)
        assert get_value(CONTENT_TRACING_KEY) == expected

    def test_repeated_calls_track_latest_value(self):
        Pulse.enable_content_tracing(enabled=True)
        assert get_value(CONTENT_TRACING_KEY) is True
        Pulse.enable_content_tracing(enabled=False)
        assert get_value(CONTENT_TRACING_KEY) is False
        Pulse.enable_content_tracing(enabled=True)
        assert get_value(CONTENT_TRACING_KEY) is True


class TestPulseToolContentTracing:
    @pytest.mark.parametrize(
        "decorator_factory, expected_arg",
        [
            (lambda: pulse_tool, True),  # bare @pulse_tool
            (lambda: pulse_tool(), True),  # @pulse_tool()
            (lambda: pulse_tool(enable_content_tracing=True), True),
            (lambda: pulse_tool(enable_content_tracing=False), False),
            (lambda: pulse_tool("StringToolName"), True),  # old positional-name form
        ],
    )
    def test_forwards_enable_content_tracing(self, mocker, decorator_factory, expected_arg):
        mock_enable = mocker.patch("pulse_otel.main.Pulse.enable_content_tracing")
        mocker.patch("pulse_otel.main.tool", return_value=lambda func: MagicMock())

        @decorator_factory()
        def test_function():
            return "test_result"

        test_function()
        mock_enable.assert_called_once_with(expected_arg)

    def test_name_is_passed_to_tool(self, mocker):
        mocker.patch("pulse_otel.main.Pulse.enable_content_tracing")
        mock_tool = mocker.patch("pulse_otel.main.tool", return_value=lambda func: MagicMock())

        @pulse_tool(name="CustomToolName", enable_content_tracing=False)
        def test_function():
            return "test_result"

        test_function()
        mock_tool.assert_called_with("CustomToolName")

    def test_function_metadata_preserved(self):
        @pulse_tool
        def sample_function():
            """Sample docstring."""
            return "sample_result"

        assert sample_function.__name__ == "sample_function"
        assert sample_function.__doc__ == "Sample docstring."


class TestPulseAgentContentTracing:
    @pytest.mark.parametrize(
        "kwargs, expected_arg",
        [
            ({}, True),
            ({"enable_content_tracing": True}, True),
            ({"enable_content_tracing": False}, False),
        ],
    )
    def test_forwards_enable_content_tracing(self, mocker, kwargs, expected_arg):
        mock_enable = mocker.patch("pulse_otel.main.Pulse.enable_content_tracing")
        mock_agent = mocker.patch("pulse_otel.main.agent", return_value=lambda func: MagicMock())
        mocker.patch("pulse_otel.main.add_session_id_to_span_attributes")

        @pulse_agent("TestAgent", **kwargs)
        def test_agent_function():
            return "agent_result"

        test_agent_function()
        mock_enable.assert_called_once_with(expected_arg)
        mock_agent.assert_called_with("TestAgent")

    def test_function_metadata_preserved(self):
        @pulse_agent("SampleAgent")
        def sample_agent_function():
            """Sample agent docstring."""
            return "sample_agent_result"

        assert sample_agent_function.__name__ == "sample_agent_function"
        assert sample_agent_function.__doc__ == "Sample agent docstring."


class TestObserveDecorator:
    def test_does_not_toggle_content_tracing(self, mocker):
        mock_enable = mocker.patch("pulse_otel.main.Pulse.enable_content_tracing")

        @observe(name="TestObservation")
        def test_observe_function():
            return "observe_result"

        test_observe_function()
        mock_enable.assert_not_called()


class TestContentTracingIntegration:
    """Decorators drive Pulse.enable_content_tracing per call; verify real trace files are written."""

    def test_mixed_tool_usage_forwards_each_setting(self, mocker):
        mock_enable = mocker.patch("pulse_otel.main.Pulse.enable_content_tracing")
        mocker.patch("pulse_otel.main.tool", return_value=lambda func: func)

        @pulse_tool()
        def tool_default():
            return "r1"

        @pulse_tool(name="ToolA", enable_content_tracing=False)
        def tool_disabled():
            return "r2"

        @pulse_tool("toolB", enable_content_tracing=True)
        def tool_enabled():
            return "r3"

        tool_default()
        tool_disabled()
        tool_enabled()
        mock_enable.assert_has_calls([call(True), call(False), call(True)])

    def test_agent_forwards_setting_through_observe_wrapper(self, mocker):
        mock_enable = mocker.patch("pulse_otel.main.Pulse.enable_content_tracing")
        mocker.patch("pulse_otel.main.agent", return_value=lambda func: func)
        mocker.patch("pulse_otel.main.add_session_id_to_span_attributes")

        @pulse_agent("MyAgentName", enable_content_tracing=False)
        def agent_run(prompt):
            return f"Agent processed: {prompt}"

        @observe(name="ObservationWrapper")
        def wrapped_agent_call(user_prompt):
            return agent_run(user_prompt)

        wrapped_agent_call("What time is it?")
        mock_enable.assert_called_once_with(False)

    @pytest.mark.parametrize("enabled", [True, False])
    def test_file_writing_emits_trace_files(self, tmp_path, monkeypatch, enabled):
        monkeypatch.chdir(tmp_path)
        Pulse(write_to_file=True)
        Pulse.enable_content_tracing(enabled=enabled)
        assert get_value(CONTENT_TRACING_KEY) == enabled

        @pulse_tool(enable_content_tracing=enabled)
        def test_tool():
            return "traced content"

        test_tool()

        trace_files = list(Path(tmp_path).glob("*traces*.json"))
        assert trace_files, "no trace files were created"


class TestIsContentAllowed:
    def test_module_default_is_disallowed(self):
        # Reload rather than patch: patching the value under test would assert
        # the fixture, not the default a regression would change.
        reloaded = importlib.reload(util)
        try:
            assert reloaded.is_content_allowed() is False
        finally:
            reloaded.set_global_content_tracing(False)

    @pytest.mark.parametrize("enabled", [True, False])
    def test_tracks_the_global_content_tracing_decision(self, enabled, monkeypatch):
        monkeypatch.setenv("TRACELOOP_TRACE_CONTENT", "unset")
        util.set_global_content_tracing(enabled)

        assert util.is_content_allowed() is enabled
        assert os.environ["TRACELOOP_TRACE_CONTENT"] == str(enabled).lower()
