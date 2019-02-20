FROM alpine@sha256:b3dbf31b77fd99d9c08f780ce6f5282aba076d70a513a8be859d8d3a4d0c92b8

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

COPY Gemfile /app
COPY Gemfile.lock /app
WORKDIR /app

# install packages needed for building compiled gems; install gems; then delete build dependencies to keep Docker image small
ENV BUILD_PACKAGES sudo build-base ruby-dev libc-dev linux-headers openssl-dev git
RUN apk --update add --virtual build_deps $BUILD_PACKAGES && \
    bundle install && \
    apk del build_deps && \
    rm -rf /var/cache/apk/*

COPY . /app
RUN chown -R ionosphere:ionosphere /app
USER ionosphere

CMD ./docker_entrypoint.sh
