FROM tiangolo/uwsgi-nginx-flask:python3.8-alpine
RUN apk --update add bash nano
RUN apk add build-base openldap-dev python2-dev python3-dev
ENV STATIC_URL /static
ENV STATIC_PATH /var/www/app/static
COPY ./requirements.txt /var/www/requirements.txt
RUN apk add  python3-dev valgrind