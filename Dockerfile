FROM python:3.8
WORKDIR /app
COPY . .
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes libsasl2-dev python-ldap libldap2-dev libssl-dev
RUN pip install -r requirements.txt
ENTRYPOINT ["python"]
CMD ["ADWebmanager.py"]