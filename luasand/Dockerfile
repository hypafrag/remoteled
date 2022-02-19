FROM alpine:3.13.6 as builder

RUN apk add --no-cache cmake make g++ libwebsockets-dev lua5.3-dev openssl-dev
ADD init.lua /srv
ADD front /srv/front
ADD examples /srv/examples
ADD main.cpp perlin.cpp perlin.h CMakeLists.txt ./
RUN mkdir build && cd build && cmake .. && make && cp luasand /srv/luasand

FROM alpine:3.13.6

WORKDIR /srv
RUN apk add --no-cache libwebsockets lua5.3 libstdc++
COPY --from=builder /srv ./
ENTRYPOINT ["/srv/luasand"]
