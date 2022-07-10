FROM python:3.8
WORKDIR /app
COPY . .
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes build-essential python3-dev libldap2-dev libsasl2-dev slapd ldap-utils tox lcov valgrind &&\
    python3 -m venv && \
    . venv/bin/activate
RUN pip install -r requirements.txt
ENTRYPOINT ["python"]
CMD ["ADWebmanager.py"]