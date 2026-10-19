FROM python@sha256:4bbf5ef9ce4b273299d394de268ad6018e10a9375d7efc7c2ce9501a6eb6b86c
COPY schema-runner.requirements.txt /tmp/requirements.txt
COPY wheels/ /tmp/wheels/
RUN python -m pip install --no-cache-dir --no-index --find-links=/tmp/wheels --require-hashes -r /tmp/requirements.txt && rm -rf /tmp/wheels /tmp/requirements.txt
ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "pytest"]
