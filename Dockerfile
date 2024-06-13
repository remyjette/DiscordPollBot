FROM python:3.12

WORKDIR /bot

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN pip install discord.py==2.3.2

COPY . .

ENV DISCORD_TOKEN=

ENTRYPOINT ["python3"]
CMD ["-m", "bot"]
