FROM ndn_microservice/base:latest
COPY CS_ST /CS_ST
COPY Prometheus /Prometheus

RUN cd /CS_ST && cmake . && make -j2 && mv bin/CS / && cd / && rm -r /CS_ST

RUN apt update  && apt install -y nano build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev wget && wget https://www.python.org/ftp/python/3.6.9/Python-3.6.9.tgz && tar xzf Python-3.6.9.tgz && cd Python-3.6.9 && ./configure && make && make install

RUN pip3 install Twisted && pip3 install simplejson && pip3 install prometheus-client
