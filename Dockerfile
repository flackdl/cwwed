FROM python:3.6.4-stretch

ENV PYTHONUNBUFFERED 1

RUN echo "Installing dependencies" \
    && wget -qO- https://deb.nodesource.com/setup_8.x | bash - \
    && apt-get update && apt-get install -y \
        libgdal-dev \
        postgresql-client \
        nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
ADD . /app
WORKDIR /app

RUN pip install -r requirements.txt

# provide dummy values for required env variables
ENV CWWED_ARCHIVES_ACCESS_KEY_ID ''
ENV CWWED_ARCHIVES_SECRET_ACCESS_KEY ''
ENV SLACK_BOT_TOKEN ''

# build front-end angular app
RUN npm --prefix frontend run build-prod

# collect static assets
RUN python manage.py collectstatic --no-input

EXPOSE 80

VOLUME /media/bucket/cwwed

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:80", "cwwed.wsgi"]
