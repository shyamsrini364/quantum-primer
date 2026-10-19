from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from urllib3.exceptions import MaxRetryError

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from quantum_primer.config import Settings  # noqa: E402
from quantum_primer.service import create_graph  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_chat_sources_refusal_and_clear():
    settings = Settings(_env_file=None, mode="demo")
    with (
        patch("quantum_primer.config.Settings", return_value=settings),
        patch("quantum_primer.service.create_graph", return_value=create_graph(settings)),
    ):
        app = AppTest.from_file(str(APP)).run()
        app.chat_input[0].set_value("What is Quantum Primer?").run()
        assert not app.exception
        assert app.expander[0].label == "Sources"
        assert any("[1]" in m.value for m in app.markdown)
        app.chat_input[0].set_value("How do I configure Kubernetes ingress?").run()
        assert "couldn't find enough information" in app.info[0].value
        app.sidebar.button[0].click().run()
        assert not app.chat_message


def test_provider_errors_do_not_expose_details():
    graph = Mock()
    graph.invoke.side_effect = RuntimeError("secret-provider-detail")
    with patch("quantum_primer.service.create_graph", return_value=graph):
        app = AppTest.from_file(str(APP)).run()
        app.chat_input[0].set_value("What happened?").run()
        assert not app.exception
        assert "could not be completed" in app.error[0].value
        assert "secret-provider-detail" not in app.error[0].value


def test_startup_errors_do_not_expose_details():
    with patch("quantum_primer.service.create_graph", side_effect=ValueError("secret-detail")):
        app = AppTest.from_file(str(APP)).run()
        assert not app.exception
        assert "Could not open the library" in app.error[0].value
        assert "secret-detail" not in app.error[0].value
        assert not app.chat_input


def test_network_startup_error_and_retry():
    settings = Settings(_env_file=None, mode="demo")
    graph = create_graph(settings)
    with patch(
        "quantum_primer.service.create_graph",
        side_effect=[MaxRetryError(None, "secret-provider-url"), graph],
    ):
        app = AppTest.from_file(str(APP)).run()
        assert "Could not connect to Pinecone" in app.error[0].value
        assert "secret-provider-url" not in app.error[0].value
        next(b for b in app.button if b.label == "Retry connection").click().run()
        assert not app.error
        assert not app.exception
        assert app.chat_input
