FROM python:3.9-slim-bullseye

RUN pip install slack_bolt \
        openai python-dotenv sqlalchemy

WORKDIR /gpt-slack-bot

CMD ["python", "main.py"]
