dist: LICENSE Makefile README.md pyproject.toml src
	python3 -m build

upload: dist
	python3 -m twine upload --repository testpypi dist/* --config-file=~/.pypirc

test:
	python3 -m pytest src/pydesync/all.py
