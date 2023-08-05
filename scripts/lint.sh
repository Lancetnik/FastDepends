pyup_dirs --py37-plus --recursive propan tests
mypy fast_depends
ruff fast_depends tests --fix
black fast_depends tests
isort fast_depends tests