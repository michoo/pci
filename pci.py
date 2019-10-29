#!/usr/bin/env python3
import pyshark
import socket
from py2neo import Graph, Node, Relationship, NodeMatcher
import geoip2.database
import re
from datetime import datetime, timezone
import sys
import signal
import argparse
import logging.config

import yaml

# logging settings
with open('logging.yml', 'rt') as f:
    config = yaml.safe_load(f.read())
    f.close()

logging.config.dictConfig(config)
logger = logging.getLogger(__name__)

# check databases
try:
    _graph_db = Graph('http://localhost:7474', user="neo4j", password="password1")
    _matcher = NodeMatcher(_graph_db)
    _reader = geoip2.database.Reader('./db/geoip/GeoLite2-City.mmdb',
                                     mode=geoip2.database.MODE_MMAP)
except:
    logger.info("neo4j of geoip not available")
    sys.exit(1)


def packet_analysis_live(cap):
    cap.set_debug()
    logger.debug(cap.get_parameters())
    cap.sniff(timeout=50)
    signal.signal(signal.SIGINT, signal_handler)
    for pkt in cap.sniff_continuously():
        do_the_job(pkt)
    stop()


def packet_analysis(cap):
    cap.set_debug()
    logger.debug(cap.get_parameters())
    signal.signal(signal.SIGINT, signal_handler)
    for pkt in cap:
        do_the_job(pkt)
    stop()


def stop():
    cap.close()
    _reader.close()
    logger.info("Analysis ending ...")
    sys.exit(0)


def signal_handler(sig, frame):
    logger.info('You pressed Ctrl+C!')
    stop()


def get_host_name(ip):
    host_name = "Unknown"
    try:
        host_name = socket.gethostbyaddr(ip)[0]
    except Exception:
        logger.error("Can't resolve host name: " + ip)
    return host_name


def create_node(arg, existing_node):
    logger.debug("New node: " + arg)
    try:
        _graph_db.create(existing_node)
    except Exception:
        logger.error("Neo4j not available")


def get_node(arg):
    pat = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    ipv4 = pat.match(arg)
    if ipv4:
        if arg.startswith('192.168') or arg.startswith('172.16') or arg.startswith('10.0'):
            existing_node = _matcher.match("local_machine", ipv4=arg).first()
            if existing_node:
                existing_node['count'] += 1
                existing_node['last_update'] = datetime.now(timezone.utc).isoformat()
                _graph_db.push(existing_node)
            else:
                existing_node = Node("local_machine", ipv4=arg, local=True, count=1,
                                     creation_date=datetime.now(timezone.utc).isoformat(),
                                     last_update=datetime.now(timezone.utc).isoformat())
                create_node(arg, existing_node)
        else:
            existing_node = _matcher.match("machine", ipv4=arg).first()
            if existing_node:
                existing_node['count'] += 1
                existing_node['last_update'] = datetime.now(timezone.utc).isoformat()
                _graph_db.push(existing_node)
            else:
                domain_name = "Unknown"
                country_name = "Unknown"
                sub_name = "Unknown"
                city_name = "Unknown"
                domain_name = get_host_name(arg)

                try:
                    response = _reader.city(arg)
                    if response:
                        country_name = response.country.iso_code
                        sub_name = response.subdivisions.most_specific.iso_code
                        city_name = response.city.name
                except Exception:
                    pass
                existing_node = Node("machine", ipv4=arg, domain=domain_name, country=country_name,
                                     sub=sub_name, city=city_name, count=1,
                                     creation_date=datetime.now(timezone.utc).isoformat(),
                                     last_update=datetime.now(timezone.utc).isoformat())
                create_node(arg, existing_node)
    else:
        pat_mac = re.compile('((?:[\da-fA-F]{2}[:\-]){5}[\da-fA-F]{2})')
        mac_address = pat_mac.match(arg)

        if mac_address:
            existing_node = _matcher.match("network", mac_address=arg).first()
            if existing_node:
                existing_node['count'] += 1
                existing_node['last_update'] = datetime.now(timezone.utc).isoformat()
                _graph_db.push(existing_node)
            else:
                existing_node = Node("network", mac_address=arg, count=1,
                                     creation_date=datetime.now(timezone.utc).isoformat(),
                                     last_update=datetime.now(timezone.utc).isoformat())
                create_node(arg, existing_node)
        else:
            existing_node = _matcher.match("machine_ipv6", ipv6=arg).first()
            if existing_node:
                existing_node['count'] += 1
                existing_node['last_update'] = datetime.now(timezone.utc).isoformat()
                _graph_db.push(existing_node)
            else:
                existing_node = Node("machine_ipv6", ipv6=arg, count=1,
                                     creation_date=datetime.now(timezone.utc).isoformat(),
                                     last_update=datetime.now(timezone.utc).isoformat())

                create_node(arg, existing_node)
    return existing_node


def do_the_job(pkt):
    src = pkt.source
    dst = pkt.destination
    typ = pkt.protocol
    info = pkt.info
    length = pkt.length
    # print(pkt)
    # print('%s  %s --> %s (%s) - %s' % (typ, src, dst, length, info))
    logger.debug("Protocol: " + typ + ", Source: " + src + ", Destination: " + dst)

    a = get_node(arg=src)
    b = get_node(arg=dst)

    PACKET_TO = Relationship.type(typ)
    _graph_db.merge(PACKET_TO(a, b))


if __name__ == "__main__":
    # args parser
    parser = argparse.ArgumentParser(description='Packet communications investigator')
    parser.add_argument("-f", '--file',
                        help='directory to clean  if not declared use of current dir',
                        action='store', dest='filepath')
    parser.add_argument("-i", "--interface", help="chose interface", action="store", dest='interface')
    parser.add_argument("-r", "--ring", help="activate ring buffer", action="store_true",
                        default=False)

    args = parser.parse_args()

    # live ring capture
    if args.ring:
        logger.info("Starting Live Ring Capture on " + args.interface)
        cap = pyshark.LiveRingCapture(interface=args.interface, only_summaries=True, ring_file_size=4096,
                                      num_ring_files=50, ring_file_name='./db/pcap/pci.pcapng')
        packet_analysis_live(cap)
    # live capture
    elif args.interface:
        logger.info("Starting Live Capture on " + args.interface)
        cap = pyshark.LiveCapture(interface=args.interface, only_summaries=True)
        packet_analysis_live(cap)

    # pcap
    elif args.filepath:
        logger.info("Starting pcap analysis on " + args.filepath)
        cap = pyshark.FileCapture(input_file=args.filepath, only_summaries=True)
        packet_analysis(cap)

    else:
        parser.print_help()
    sys.exit()
