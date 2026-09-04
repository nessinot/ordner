ARG BUILD_FROM
FROM $BUILD_FROM
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv ocrmypdf tesseract-ocr-nld tesseract-ocr-eng poppler-utils libheif1 \
 && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /app
COPY ordner/ /app/ordner/
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
