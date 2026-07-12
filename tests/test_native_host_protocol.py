import io
import json
import unittest
from unittest.mock import patch

from scripts import native_host


class _BinaryStream:
    def __init__(self, data=b""):
        self.buffer = io.BytesIO(data)


def _native_input(message):
    payload = json.dumps(message).encode("utf-8")
    return len(payload).to_bytes(4, byteorder="little") + payload


def _native_output(raw):
    payload_size = int.from_bytes(raw[:4], byteorder="little")
    return json.loads(raw[4 : 4 + payload_size].decode("utf-8"))


class NativeHostProtocolTests(unittest.TestCase):
    def test_rejects_unsupported_action_over_native_protocol(self):
        stdin = _BinaryStream(_native_input({"action": "unsupported"}))
        stdout = _BinaryStream()

        with patch("scripts.native_host.sys.stdin", stdin), patch(
            "scripts.native_host.sys.stdout", stdout
        ):
            native_host.main()

        self.assertEqual(
            _native_output(stdout.buffer.getvalue()),
            {"ok": False, "error": "Unsupported native action."},
        )


if __name__ == "__main__":
    unittest.main()
