from pathlib import Path
from unittest.mock import patch

from pushikoo_interface import get_adapter_test_env, run_pusher_basic_flow


def test_basic_flow():
    pusher, ctx = get_adapter_test_env(Path(__file__).parents[1] / "pyproject.toml")
    pusher.adapter_name = pusher.meta.name
    pusher.adapter_storage_path = ctx.storage_base_path / pusher.adapter_name

    with patch("pushikoo_pusher_email.main.EmailClient.send") as send:
        run_pusher_basic_flow(pusher, ctx)

    send.assert_called_once()
