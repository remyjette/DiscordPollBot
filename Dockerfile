FROM python:3.9
RUN pip install discord.py
ADD *.py /
ENV DISCORD_TOKEN=
CMD ["python", "bot.py"]
