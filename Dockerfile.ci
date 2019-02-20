FROM docker@sha256:453c52a7a7200677f9effa3acc8498a2f71af77c2951ac5e1ac1391053573374 AS docker
FROM alpine:latest

COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker

RUN apk --no-cache add curl python py-crcmod bash libc6-compat openssh-client git gnupg

ENV RUBY_PACKAGES ruby ruby-io-console ruby-irb ruby-rake ruby-bundler ruby-bigdecimal ruby-json
ENV RUBY_DEPS libstdc++ tzdata bash ca-certificates openssl sqlite sqlite-dev

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
ENV BUILD_PACKAGES sudo build-base ruby-dev libc-dev linux-headers openssl-dev
RUN apk --update add --virtual build_deps $BUILD_PACKAGES && \
    bundle install && \
    apk del build_deps && \
    rm -rf /var/cache/apk/*

COPY . /app
