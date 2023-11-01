ARG BASE_IMAGE

FROM ${BASE_IMAGE}

COPY ./src /app

WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT [ "python" ]

CMD [ "view.py" ]