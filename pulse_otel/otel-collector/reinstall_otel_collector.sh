#!/bin/bash
set -e

docker compose build && docker compose down && docker compose up -d

