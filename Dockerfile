FROM python:3.6.4-stretch

WORKDIR /app

ADD . .

RUN pip install -r requirements.txt

EXPOSE 80

CMD gunicorn -w 4 -b 0.0.0.0:80 coastal.wsgi
