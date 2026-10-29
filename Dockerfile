FROM python:3.12-slim
WORKDIR /app
COPY ron.py roncli.py ronlib.py rondata.py ronfiles.py ronsecurity.py ronstarter.py ./
COPY examples ./examples
RUN useradd --create-home ron && mkdir /data && chown ron:ron /data
USER ron
ENV HOST=0.0.0.0 PORT=8000 RON_DATABASE=/data/startup.sqlite3 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "ron.py", "examples/site/main.ron"]
