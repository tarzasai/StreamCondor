Test helpers and fixtures

This project provides centralized helpers for mocking Streamlink (`sls`) and the
`is_stream_live` helper used by monitor and UI code.

Files
- `test/test_helpers.py` — Context managers:
  - `mock_sls(streams_return=None, resolve_return=None, resolve_side_effect=None)`
    to patch `streamcondor.slhelper.sls`.
  - `mock_is_stream_live(return_value=None, side_effect=None)`
    to patch `streamcondor.monitor.is_stream_live` and
    `streamcondor.ui.trayicon.is_stream_live` together.

- `test/conftest.py` — Pytest fixtures:
  - `mock_sls` fixture: factory returning the `mock_sls` context manager.
  - `mock_is_stream_live` fixture: factory returning the `mock_is_stream_live` context manager.

Usage examples

Unittest-style (context manager directly):

```python
from test.test_helpers import mock_is_stream_live

with mock_is_stream_live(return_value=('youtube', True)):
    # run code that calls is_stream_live
    ...
```

Pytest-style (fixture):

```python
def test_example(mock_is_stream_live):
    with mock_is_stream_live(return_value=('youtube', True)):
        # test code
        ...
```

Rationale

Centralizing these mocks avoids duplication and keeps tests stable even if the
internal location of `sls` or `is_stream_live` changes. Update the helpers if the
project structure changes; tests will keep using the same API.
