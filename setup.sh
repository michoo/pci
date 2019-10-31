#!/bin/sh

# download geoip database
rm -r db/geoip
rm db/geoip
wget http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.tar.gz
tar -xzf GeoLite2-City.tar.gz -C ./db/
mv db/GeoLite2* db/geoip
rm GeoLite2-City.tar.gz
