import unittest
import sys
import os

# Ensure project root is in path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# Add `src` directory so project modules can be imported as top-level modules
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _run_tests_with_coverage():
    try:
        import coverage
    except Exception:
        coverage = None

    cov = None
    if coverage is not None:
        cov = coverage.Coverage(source=[SRC])
        cov.start()

    loader = unittest.TestLoader()
    runner = unittest.TextTestRunner(verbosity=2)

    # Run pytest-based UI tests first (if pytest is available) while coverage is active
    try:
        import pytest
        test_dir = os.path.dirname(__file__)
        ui_tests = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.startswith('test_ui_') and f.endswith('.py')]
        if ui_tests:
            pytest_args = ['-q'] + ui_tests
            pytest_rc = pytest.main(pytest_args)
            if pytest_rc != 0:
                print(f'pytest reported failures (rc={pytest_rc})')
                # Treat pytest failures as test failures
                if cov is not None:
                    cov.stop()
                    cov.save()
                sys.exit(pytest_rc)
        else:
            pytest_rc = None
    except Exception:
        pytest_rc = None

    # Discover unittest tests but skip pytest UI test files to avoid double-running
    test_dir = os.path.dirname(__file__)
    # ui_tests (pytest files) were collected earlier into ui_tests; if not set, compute it
    try:
        ui_tests
    except NameError:
        ui_tests = [f for f in os.listdir(test_dir) if f.startswith('test_ui_') and f.endswith('.py')]
    test_files = [f for f in os.listdir(test_dir) if f.startswith('test_') and f.endswith('.py') and f not in ui_tests]
    suite = unittest.TestSuite()
    for tf in test_files:
        modname = tf[:-3]
        try:
            suite.addTests(loader.loadTestsFromName(modname))
        except Exception as e:
            print(f'Error loading tests from {modname}: {e}')

    result = runner.run(suite)

    if cov is not None:
        cov.stop()
        cov.save()
        print('\nCoverage report:')
        cov.report(show_missing=True)
    else:
        print('\nCoverage not measured (install the "coverage" package to enable).')

    if not result.wasSuccessful():
        sys.exit(1)

        # If pytest is available, also run pytest-based UI tests so coverage includes them
        try:
            import pytest
            # Run only pytest tests in test/ that follow our pytest files pattern
            pytest_args = ['-q', 'test/test_ui_*.py']
            pytest_rc = pytest.main(pytest_args)
            if pytest_rc != 0:
                # Treat pytest failures as test failures
                result.failures.append(('pytest', pytest_rc))
        except Exception:
            # pytest not available or failed to import — skip
            pass

if __name__ == '__main__':
    _run_tests_with_coverage()
