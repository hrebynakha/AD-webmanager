FROM python:3.8
WORKDIR /app
COPY . .
CMD ["apt-get install libsasl2-dev python-dev libldap2-dev libssl-dev"]
RUN pip install -r requirements.txt
ENTRYPOINT ["python"]
CMD ["ADWebmanager.py"]