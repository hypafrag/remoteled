FROM alpine as builder

WORKDIR /srv
RUN apk add --no-cache cmake make g++ libwebsockets-dev lua5.3-dev openssl-dev
COPY main.cpp CMakeLists.txt init.lua index.html ./
RUN mkdir build && cd build && cmake .. && make

FROM alpine

WORKDIR /srv
RUN apk add --no-cache libwebsockets lua5.3 libstdc++
COPY --from=builder /srv/init.lua /srv/index.html /srv/build/luasand ./
ENTRYPOINT ["/srv/luasand"]
