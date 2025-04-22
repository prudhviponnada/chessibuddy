FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install flask random chess
RUN apt-get update
CMD ["python", "chessy.py"]
EXPOSE 5000
# docker build -t chessibuddy .