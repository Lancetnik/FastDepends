echo "Running mypy..."
mypy fast_depends

echo "Running ruff linter (isort, flake, pyupgrade, etc. replacement)..."
ruff fast_depends tests --fix

echo "Running ruff formatter (black replacement)..."
ruff format tests

echo "Running codespell to find typos..."
codespell
