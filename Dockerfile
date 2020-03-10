FROM alpine@sha256:c40c013324aa73f430d33724d8030c34b1881e96b23f44ec616f1caf8dbf445f

ENV RUBY_PACKAGES ruby ruby-io-console ruby-irb ruby-rake ruby-bundler ruby-bigdecimal ruby-json
ENV RUBY_DEPS libstdc++ tzdata bash ca-certificates openssl sqlite sqlite-dev

RUN addgroup -g 1000 ionosphere \
  && adduser -u 1000 -D -G ionosphere ionosphere

RUN apk update && \
    apk upgrade && \
    apk --update add $RUBY_PACKAGES $RUBY_DEPS && \
    echo 'gem: --no-document' > /etc/gemrc

RUN mkdir /app && \
    mkdir -p /data/ionosphere

COPY . /app
WORKDIR /app

# install packages needed for building compiled gems; install gems; then delete build dependencies to keep Docker image small
ENV BUILD_PACKAGES sudo build-base ruby-dev libc-dev linux-headers openssl-dev git
RUN apk --update add --virtual build_deps $BUILD_PACKAGES && \
    bundle update --bundler && \
    bundle install && \
    apk del build_deps && \
    rm -rf /var/cache/apk/*

RUN chown -R ionosphere:ionosphere /app
USER ionosphere

CMD ./docker_entrypoint.sh
