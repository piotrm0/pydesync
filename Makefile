CONDA_ACTIVATE:= \
	source $$(conda info --base)/etc/profile.d/conda.sh; \
	conda activate; \
	conda activate

dist: LICENSE Makefile README.md pyproject.toml src tests
	python3 -m build

upload: dist
	python3 -m twine upload \
		--repository testpypi dist/* \
		--config-file=~/.pypirc

all_tests:
	make test3.8
	make test3.9
	make test3.10
	make test3.11
	make test3.12

conda/py%:
	conda create -p ./conda/py$* -y python=$*
	$(CONDA_ACTIVATE) ./conda/py$*; \
		pip install pytest pytest-asyncio
	
test%: conda/py%
	$(CONDA_ACTIVATE) ./conda/py$*; \
		PYTHONPATH=src \
			python -m pytest \
			tests/test_all.py
