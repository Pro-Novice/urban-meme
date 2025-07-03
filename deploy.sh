#!/bin/bash

if [[ $1 == "stop" ]]; then
    echo "####################################################################"
    echo "                  Stopping and Removing Containers"
    echo "####################################################################"
    docker compose down
else
  if [[ $1 == "dev" ]]; then
    echo "####################################################################"
    echo "                  Connecting to Development Server"
    echo "####################################################################"
    export AUTH_PORT=8080
  else
    echo "####################################################################"
    echo "                  Connecting to Staging Server"
    echo "####################################################################"
    export AUTH_PORT=8080
  fi

    echo "####################################################################"
    echo "                  Stopping Existing Containers"
    echo "####################################################################"
    docker compose down

    echo "####################################################################"
    echo "                  Building and Starting Containers"
    echo "####################################################################"
    docker compose build || { echo "Docker Compose Build Failed"; exit 1; }
    docker compose up -d || { echo "Docker Compose Up Failed"; exit 1; }

    echo "####################################################################"
    echo "                  Configuring Redis ACL"
    echo "####################################################################"
    docker exec -it redis_local redis-cli -a password ACL SETUSER root on +@all ~* >password || {
      echo "Redis ACL Configuration Failed";
      exit 1;
    }

    echo "####################################################################"
    echo "                        Successfully Deployed"
    echo "####################################################################"
    docker ps -a
fi
