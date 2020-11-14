FROM python:3.9
RUN pip install discord.py
ADD *.py /
CMD ["python", "bot.py"]
