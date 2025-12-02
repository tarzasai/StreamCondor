"""Test helpers for StreamCondor unit tests.

Provides helpers to mock Streamlink (`sls`) behavior and `is_stream_live`.
"""
from unittest.mock import patch
from contextlib import contextmanager

@contextmanager
def mock_sls(streams_return=None, resolve_return=None, resolve_side_effect=None):
  """Context manager that patches `streamcondor.slhelper.sls`.

  Parameters:
  - streams_return: value to return for `sls.streams()`
  - resolve_return: value to return for `sls.resolve_url(...)`
  - resolve_side_effect: exception to raise from `sls.resolve_url(...)`
  """
  # Patch both the source `sls` and any modules that imported it early
  patches = [patch('streamcondor.slhelper.sls'), patch('streamcondor.ui.stream.sls')]
  with patches[0] as mock_sls, patches[1] as mock_sls_ui:
    if streams_return is not None:
      mock_sls.streams.return_value = streams_return
    if resolve_return is not None:
      mock_sls.resolve_url.return_value = resolve_return
    if resolve_side_effect is not None:
      mock_sls.resolve_url.side_effect = resolve_side_effect
    # Mirror settings to ui import so downstream modules see the same mock
    if streams_return is not None:
      mock_sls_ui.streams.return_value = streams_return
    if resolve_return is not None:
      mock_sls_ui.resolve_url.return_value = resolve_return
    if resolve_side_effect is not None:
      mock_sls_ui.resolve_url.side_effect = resolve_side_effect
    yield mock_sls

@contextmanager
def mock_is_stream_live(return_value=None, side_effect=None):
  """Context manager that patches module-local `is_stream_live` used by monitor/tray.

  Patches `streamcondor.monitor.is_stream_live` and `streamcondor.ui.trayicon.is_stream_live` to
  ensure tests mocking one place are consistent.
  """
  patches = [patch('streamcondor.monitor.is_stream_live'), patch('streamcondor.ui.trayicon.is_stream_live')]
  with patches[0] as m1, patches[1] as m2:
    if return_value is not None:
      m1.return_value = return_value
      m2.return_value = return_value
    if side_effect is not None:
      m1.side_effect = side_effect
      m2.side_effect = side_effect
    yield (m1, m2)
