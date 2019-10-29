#!/bin/sh

# remove geoip
rm -r db/geoip
rm db/geoip

# remove neo4j data
rm -r db/neo4j/data

# remove pcap
rm -r db/pcap
mkdir db/pcap

# remove logs
rm -r log
mkdir log