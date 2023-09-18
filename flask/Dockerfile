FROM python:3.11.1

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt  


RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

# Modify the flask_uploads.py file because there is a mistake in that library
RUN sed -i '26d' /usr/local/lib/python3.11/site-packages/flask_uploads.py && \
    awk 'NR==25{print; print "from werkzeug.utils import secure_filename\nfrom werkzeug.datastructures import FileStorage"} NR!=25' /usr/local/lib/python3.11/site-packages/flask_uploads.py > /usr/local/lib/python3.11/site-packages/flask_uploads_modified.py && \
    mv /usr/local/lib/python3.11/site-packages/flask_uploads_modified.py /usr/local/lib/python3.11/site-packages/flask_uploads.py

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app;app"]

gunicorn -w 4 -b 0.0.0.0:5000 app:app