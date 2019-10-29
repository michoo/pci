#!/bin/sh

docker run --publish=7474:7474 --publish=7687:7687 --volume=$PWD/../db/neo4j/data:/data pci-neo4j